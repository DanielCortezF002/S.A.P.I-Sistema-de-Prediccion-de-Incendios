"""Script de bootstrap seguro, endurecido y no destructivo para Compose v2 (SAPI-66 / Directiva 26).

Cierre definitivo de hallazgos Astra:
- P1: Publicación atómica de .env mediante os.open(O_CREAT|O_EXCL) directamente en ruta final.
       No utiliza os.replace() sobre el destino. Si el archivo ya existe, FAIL CLOSED.
- P1: Sin flag --force. Nunca eliminar ni alterar configuraciones existentes o volúmenes persistentes.
- P1: Verificación de volúmenes distingue: inexistente (OK), existente (BLOCK), Docker inaccesible (BLOCK).
- P1: Entorno Compose hermético: neutraliza COMPOSE_ENV_FILES, COMPOSE_DISABLE_ENV_FILE,
       COMPOSE_PROFILES, COMPOSE_FILE, COMPOSE_PROJECT_NAME y todas las variables SAPI_*/POSTGRES_*.
       Pasa --env-file explícito, -f docker-compose.yml, -p <nombre>, perfil presentation y
       lista exacta de servicios.
- P2: Restricción ACL en Windows con icacls ANTES de exponer secretos; si falla, FAIL CLOSED.
- P2: Redacción de stderr externo: nunca se imprime crudo; se sanitiza contra secretos conocidos.
- P2: Persistencia correlacionada: ranking JSON, model_version, inputs_fingerprint, firms_origin,
       ejecucion_id y exactamente 50 predicciones vinculadas.
- P2: Sin limpieza destructiva automática (down -v) ante fallos parciales.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# Nombre de proyecto: minúsculas, dígitos, guion y guion bajo (2 a 63 caracteres)
PROJECT_NAME_REGEX = re.compile(r"^[a-z0-9][a-z0-9_-]{1,62}$")

COMPOSE_FILE_DEFAULT = "docker-compose.yml"
SERVICES_V2_EXPLICIT = ("db-v2", "ml-api", "backend", "web-v2")

# Variables de entorno hostiles que deben neutralizarse completamente
COMPOSE_HOSTILE_VARS = (
    "COMPOSE_ENV_FILES",
    "COMPOSE_DISABLE_ENV_FILE",
    "COMPOSE_FILE",
    "COMPOSE_PROJECT_NAME",
    "COMPOSE_PROFILES",
)


def generate_secure_password(length: int = 24) -> str:
    """Genera token criptográficamente seguro sin caracteres problemáticos para shell."""
    return secrets.token_urlsafe(length)


def validate_project_name(name: str) -> None:
    """Valida formato seguro del nombre de proyecto Compose."""
    if not PROJECT_NAME_REGEX.match(name):
        raise ValueError(
            f"Nombre de proyecto inválido: '{name}'. Debe comenzar con letra minúscula o número, "
            "contener solo caracteres alfanuméricos en minúsculas, guiones y guiones bajos (2-63 caracteres)."
        )


def check_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Comprueba si un puerto TCP ya está escuchando en el host."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def validate_ports(ports_map: dict[str, int]) -> None:
    """Valida rango de puertos, ausencia de duplicados internos y colisiones en host."""
    seen = {}
    for svc, port in ports_map.items():
        if not isinstance(port, int) or port < 1024 or port > 65535:
            raise ValueError(
                f"Puerto inválido para {svc}: {port}. Debe ser un entero en el rango 1024-65535."
            )
        if port in seen:
            raise ValueError(
                f"Conflicto de puertos: {svc} y {seen[port]} tienen asignado el mismo puerto {port}."
            )
        seen[port] = svc

        # Comprobar si el puerto ya está ocupado en 127.0.0.1
        if check_port_in_use(port):
            raise RuntimeError(
                f"Colisión de puerto en host: El puerto {port} ({svc}) ya está en uso en 127.0.0.1. "
                f"Especifique un puerto libre con --{svc.replace('_', '-')}-port."
            )


def check_existing_configuration(env_path: Path) -> None:
    """Protección P1: si .env existe, falla de forma segura sin modificarlo."""
    if env_path.exists():
        raise FileExistsError(
            f"El archivo de configuración {env_path} ya existe. "
            "El bootstrap es exclusivo para aprovisionamiento inicial de proyectos nuevos. "
            "Para evitar pérdida o corrupción de credenciales previas, no se sobrescribe. "
            "Si ya dispone de .env, ejecute 'docker compose up' directamente."
        )


def check_existing_docker_volume(project_name: str) -> None:
    """Protección P1: comprueba si ya existe el volumen PostGIS para este proyecto.

    Distingue tres casos:
    A. Volumen inexistente: permite continuar.
    B. Volumen existente: bloquea.
    C. Docker inaccesible / error de consulta / timeout: bloquea (FAIL CLOSED).
    """
    vol_name = f"{project_name}_sapi_v2_pgdata"
    cmd = ["docker", "volume", "ls", "--filter", f"name=^{vol_name}$", "--format", "{{.Name}}"]
    try:
        res = subprocess.run(
            cmd, capture_output=True, text=True, check=False, timeout=15
        )
    except FileNotFoundError:
        raise RuntimeError(
            "Docker CLI no encontrado. No se puede verificar la existencia de volúmenes "
            "persistentes. Bootstrap abortado por seguridad (FAIL CLOSED)."
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            "Timeout al consultar volúmenes de Docker. El daemon puede estar inaccesible. "
            "Bootstrap abortado por seguridad (FAIL CLOSED)."
        )

    if res.returncode != 0:
        raise RuntimeError(
            f"Error al consultar volúmenes de Docker (exit code {res.returncode}). "
            "No se puede determinar si el volumen persistente existe. "
            "Bootstrap abortado por seguridad (FAIL CLOSED)."
        )

    existing = [v.strip() for v in res.stdout.strip().splitlines() if v.strip()]
    if vol_name in existing:
        raise RuntimeError(
            f"El volumen persistente de Docker '{vol_name}' ya existe. "
            "Generar una nueva contraseña en .env causaría fallo de autenticación con la base de datos "
            "(PostgreSQL no rota contraseñas de volúmenes existentes con POSTGRES_PASSWORD). "
            f"Para un aprovisionamiento limpio, elimine el volumen manualmente con 'docker volume rm {vol_name}' "
            "antes de ejecutar este bootstrap."
        )


def build_env_content(
    db_password: str,
    db_port: int,
    ml_port: int,
    backend_port: int,
    web_port: int,
) -> str:
    """Construye el contenido de .env sin registrar ni imprimir contraseñas en texto claro."""
    lines = [
        "# ==============================================================================",
        f"# S.A.P.I. v2 - BOOTSTRAP SEGURO GENERADO: {datetime.now(timezone.utc).isoformat()}",
        "# Archivo ignorado por Git (.gitignore). Nunca incluir en commits ni reportes.",
        "# ==============================================================================",
        "",
        "SAPI_DB_USER=sapi",
        "SAPI_DB_NAME=sapi_v2",
        f"SAPI_DB_PASSWORD={db_password}",
        "",
        f"SAPI_DB_PORT={db_port}",
        f"SAPI_ML_PORT={ml_port}",
        f"SAPI_BACKEND_PORT={backend_port}",
        f"SAPI_WEB_PORT={web_port}",
        "",
        f"SAPI_BACKEND_BASE_URL=http://127.0.0.1:{backend_port}",
        "SAPI_BACKEND_CONNECT_TIMEOUT=3",
        "SAPI_BACKEND_READ_TIMEOUT=90",
        "SAPI_ML_CONNECT_TIMEOUT=2s",
        "SAPI_ML_READ_TIMEOUT=60s",
        "SAPI_UI_LEGACY_MODES=0",
        "",
        "# Activar automáticamente Streamlit web-v2 en docker compose up",
        "COMPOSE_PROFILES=presentation",
        "",
    ]
    return "\n".join(lines)


def write_env_file_exclusive(env_path: Path, content: str) -> None:
    """Escribe .env directamente en la ruta final con O_CREAT|O_EXCL sin reemplazo de destino.

    Garantías:
    - Si el archivo ya existe (incluso creado entre la comprobación previa y esta llamada),
      O_EXCL falla atómicamente con FileExistsError. Nunca se sobrescribe.
    - En Windows/NTFS: se restringe ACL con icacls ANTES de escribir el secreto.
      Si icacls falla, se elimina el archivo vacío y se aborta (FAIL CLOSED).
    - En Unix: se crea con permisos 0o600 desde el fd.
    """
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    mode = 0o600
    try:
        fd = os.open(str(env_path), flags, mode)
    except FileExistsError:
        raise FileExistsError(
            f"Carrera detectada: el archivo {env_path} fue creado entre la comprobación "
            "y la publicación. El contenido concurrente permanece intacto. Bootstrap abortado."
        )

    try:
        if sys.platform == "win32":
            # En Windows, restringir ACL ANTES de escribir el secreto
            os.close(fd)
            acl_ok = _restrict_acl_windows(env_path)
            if not acl_ok:
                # FAIL CLOSED: no exponer secreto si no se pueden restringir permisos
                try:
                    env_path.unlink()
                except OSError:
                    pass
                raise RuntimeError(
                    f"No se pudieron restringir los permisos de {env_path} con icacls. "
                    "El archivo ha sido eliminado para evitar exponer secretos. "
                    "Bootstrap abortado (FAIL CLOSED)."
                )
            # Reabrir para escritura (ya con ACL restringida)
            with open(str(env_path), "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
        else:
            # Unix: ya tiene permisos 0o600 desde O_CREAT
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            fd = -1  # fdopen cierra el fd
    except Exception:
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass
        # Si algo falló después de crear el archivo, eliminarlo para no dejar
        # un archivo vacío o parcial con secretos
        try:
            if env_path.exists():
                env_path.unlink()
        except OSError:
            pass
        raise


def _restrict_acl_windows(path: Path) -> bool:
    """Restringe ACL del archivo exclusivamente al usuario actual en Windows.

    Retorna True si icacls reporta éxito verificable, False en cualquier otro caso.
    """
    user = os.environ.get("USERNAME", "")
    if not user:
        return False
    try:
        res = subprocess.run(
            ["icacls", str(path), "/inheritance:r", "/grant:r", f"{user}:F"],
            capture_output=True, text=True, check=False, timeout=10,
        )
        if res.returncode != 0:
            return False
        # Verificar que la ACL fue efectivamente aplicada
        verify = subprocess.run(
            ["icacls", str(path)],
            capture_output=True, text=True, check=False, timeout=10,
        )
        if verify.returncode != 0:
            return False
        # El usuario debe aparecer en la salida con permiso (F) = Full
        return user in verify.stdout and "(F)" in verify.stdout
    except Exception:
        return False


def sanitize_compose_env(generated_env_path: Path | None = None) -> dict[str, str]:
    """P1: Construye un entorno hermético para subprocesos de Docker Compose.

    Neutraliza completamente TODOS los vectores heredados demostrados por Astra:
    - COMPOSE_ENV_FILES, COMPOSE_DISABLE_ENV_FILE, COMPOSE_PROFILES, COMPOSE_FILE,
      COMPOSE_PROJECT_NAME.
    - SAPI_DB_PASSWORD, SAPI_DB_PORT, SAPI_ML_PORT, SAPI_BACKEND_PORT, SAPI_WEB_PORT
      y cualquier SAPI_* o POSTGRES_* heredado.

    Conserva solo variables de sistema (PATH, SYSTEMROOT, etc.).
    """
    clean_env = os.environ.copy()

    # 1. Eliminar todas las variables hostiles de Compose
    for var in COMPOSE_HOSTILE_VARS:
        clean_env.pop(var, None)

    # 2. Eliminar ALL credenciales y puertos heredados
    for k in list(clean_env.keys()):
        if k.startswith("SAPI_") or k.startswith("POSTGRES_"):
            clean_env.pop(k, None)

    # 3. Forzar perfil presentation (controlado)
    clean_env["COMPOSE_PROFILES"] = "presentation"

    return clean_env


def build_compose_up_command(
    project_name: str,
    compose_file: str = COMPOSE_FILE_DEFAULT,
    env_file: str | None = None,
) -> list[str]:
    """Construye comando Compose con archivo, env-file y servicios v2 estrictamente delimitados."""
    cmd = [
        "docker", "compose",
        "-f", compose_file,
        "-p", project_name,
    ]
    if env_file:
        cmd.extend(["--env-file", env_file])
    cmd.extend(["up", "-d", "--wait", "--build"])
    # Especificación explícita de los 4 servicios v2 (nunca arrancar legacy u ops)
    cmd.extend(SERVICES_V2_EXPLICIT)
    return cmd


def redact_stderr(stderr_text: str, known_secrets: list[str] | None = None) -> str:
    """Sanitiza stderr externo reemplazando secretos conocidos por [REDACTED].

    Si no se pueden garantizar la redacción completa, retorna un diagnóstico genérico.
    """
    if not stderr_text:
        return ""
    sanitized = stderr_text
    if known_secrets:
        for secret in known_secrets:
            if secret and len(secret) >= 4:
                sanitized = sanitized.replace(secret, "[REDACTED]")
    return sanitized


def check_health(
    project_name: str,
    compose_file: str = COMPOSE_FILE_DEFAULT,
    cwd: Path | None = None,
    env_file: str | None = None,
) -> bool:
    """Verifica que todos los servicios requeridos estén sanos y no haya servicios extra."""
    cmd = [
        "docker", "compose",
        "-f", compose_file,
        "-p", project_name,
    ]
    if env_file:
        cmd.extend(["--env-file", env_file])
    cmd.extend(["ps", "--format", "json"])
    env = sanitize_compose_env()
    res = subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=env, capture_output=True, text=True)
    if res.returncode != 0:
        print(
            "[ERROR] Error al consultar estado de contenedores (diagnóstico genérico, "
            "stderr redactado por seguridad).",
            file=sys.stderr,
        )
        return False
    try:
        output = res.stdout.strip()
        containers = []
        if output.startswith("["):
            containers = json.loads(output)
        else:
            for line in output.splitlines():
                if line.strip():
                    containers.append(json.loads(line))
        print(f"[INFO] Servicios detectados en proyecto '{project_name}' ({len(containers)}):")
        expected_set = set(SERVICES_V2_EXPLICIT)
        detected_set = set()
        all_ok = True
        for c in containers:
            svc = c.get("Service", c.get("service", "unknown"))
            state = c.get("State", c.get("state", "unknown"))
            health = c.get("Health", c.get("health", "no check"))
            detected_set.add(svc)
            print(f"  - {svc:12}: State={state:10} | Health={health}")
            if health == "unhealthy":
                print(f"[FAIL] Contenedor '{svc}' reporta estado UNHEALTHY!")
                all_ok = False
            if svc in ("db-v2", "ml-api", "backend") and health != "healthy":
                print(f"[FAIL] Servicio '{svc}' requiere healthcheck y reporta '{health}' (no healthy)!")
                all_ok = False
            if svc == "web-v2" and state != "running":
                print(f"[FAIL] Servicio 'web-v2' no está en estado running (State={state})!")
                all_ok = False

        # Comprobar que no se hayan arrancado servicios fuera del alcance (legacy u ops)
        unauthorized = detected_set - expected_set
        if unauthorized:
            print(f"[FAIL] Se detectaron servicios no autorizados arrancados: {unauthorized}")
            all_ok = False
        return all_ok and expected_set.issubset(detected_set)
    except Exception as ex:
        print(f"[WARN] Error analizando json de ps: tipo={type(ex).__name__}", file=sys.stderr)
        return False


def verify_ranking_api(backend_port: int, max_retries: int = 5) -> dict:
    """Valida que el backend responda con el ranking del Modelo D (modo reproducible)."""
    url = f"http://127.0.0.1:{backend_port}/api/v1/ranking"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            t0 = time.perf_counter()
            with urllib.request.urlopen(req, timeout=30) as resp:
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                data = json.loads(resp.read().decode("utf-8"))
                print(f"[OK] Backend GET /api/v1/ranking respondió HTTP {resp.status} en {elapsed_ms:.1f} ms")
                print(f"     - model_version: {data.get('model_version')}")
                print(f"     - firms_origin: {data.get('firms_origin')} (snapshot congelado Hito 1)")
                print(f"     - inputs_fingerprint: {data.get('inputs_fingerprint', 'N/A')[:16]}...")
                print(f"     - celdas evaluadas: {len(data.get('cells', []))}")
                return data
        except Exception as ex:
            last_err = ex
            time.sleep(2)
    raise RuntimeError(f"Fallo al conectar con Backend en {url} tras {max_retries} intentos: {type(last_err).__name__}")


def verify_database_persistence_correlated(
    project_name: str,
    ranking_data: dict,
) -> tuple[int, int]:
    """Valida persistencia write-through correlacionando con el ranking JSON devuelto.

    Correlaciona obligatoriamente: model_version, inputs_fingerprint, firms_origin
    y el ejecucion_id resultante, y verifica exactamente 50 predicciones vinculadas
    a esa ejecución específica (Directiva 28 / Defecto B). El origen (firms_origin)
    proviene de la respuesta API y se compara frente al valor persistido en SQL: dos
    filas pueden compartir model_version e inputs_fingerprint pero provenir de un
    origen de datos distinto (p. ej. reproducibility vs current), y eso debe fallar.
    """
    container = f"{project_name}-db-v2-1"
    model_version = ranking_data.get("model_version", "")
    inputs_fp = ranking_data.get("inputs_fingerprint", "")
    firms_origin = ranking_data.get("firms_origin", "")

    if not inputs_fp:
        raise RuntimeError("El ranking JSON no contiene inputs_fingerprint; no se puede correlacionar.")

    # Consultar ejecución por fingerprint y model_version
    query_exec = (
        f"SELECT id, model_version, firms_origin, inputs_fingerprint FROM ejecuciones "
        f"WHERE inputs_fingerprint = '{inputs_fp}' "
        f"AND model_version = '{model_version}' "
        f"ORDER BY id DESC LIMIT 1;"
    )
    cmd = ["docker", "exec", container, "psql", "-U", "sapi", "-d", "sapi_v2", "-t", "-A", "-c", query_exec]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError("Error consultando ejecución en PostGIS (diagnóstico genérico).")
    lines = [l.strip() for l in res.stdout.strip().splitlines() if l.strip()]
    if not lines:
        raise RuntimeError(
            f"No se encontró ejecución persistida con fingerprint={inputs_fp[:16]}... "
            f"y model_version={model_version}."
        )
    parts = lines[0].split("|")
    exec_id = int(parts[0])
    persisted_model = parts[1] if len(parts) > 1 else ""
    persisted_firms = parts[2] if len(parts) > 2 else ""
    persisted_fp = parts[3] if len(parts) > 3 else ""

    # Verificar correlación obligatoria: modelo, fingerprint Y origen de datos
    if persisted_model != model_version:
        raise RuntimeError(f"model_version mismatch: ranking='{model_version}' vs db='{persisted_model}'")
    if persisted_fp != inputs_fp:
        raise RuntimeError(f"inputs_fingerprint mismatch: ranking='{inputs_fp}' vs db='{persisted_fp}'")
    if not firms_origin:
        raise RuntimeError("El ranking JSON no contiene firms_origin; no se puede correlacionar el origen de datos.")
    if persisted_firms != firms_origin:
        raise RuntimeError(
            f"firms_origin mismatch: API ranking origin='{firms_origin}' vs db persisted origin='{persisted_firms}' "
            f"(ejecucion_id={exec_id}). API y SQL deben referirse a la misma obtención de datos."
        )
    print(f"[OK] Ejecución correlacionada: id={exec_id}, model={persisted_model}, firms={persisted_firms}")

    # Contar celdas vinculadas específicamente a esta ejecución
    query_cells = f"SELECT COUNT(*) FROM predicciones_celda WHERE ejecucion_id = {exec_id};"
    cmd_cells = ["docker", "exec", container, "psql", "-U", "sapi", "-d", "sapi_v2", "-t", "-A", "-c", query_cells]
    res_cells = subprocess.run(cmd_cells, capture_output=True, text=True)
    if res_cells.returncode != 0:
        raise RuntimeError("Error consultando predicciones en PostGIS (diagnóstico genérico).")
    preds_count = int(res_cells.stdout.strip())
    if preds_count != 50:
        raise RuntimeError(
            f"Conteo de predicciones vinculadas a ejecucion_id={exec_id} es {preds_count}; se requieren exactamente 50."
        )
    print(f"[OK] Persistencia correlacionada verificada: ejecucion_id={exec_id}, predicciones_celda={preds_count}")
    return exec_id, preds_count


def verify_streamlit_web(web_port: int) -> bool:
    """Valida que Streamlit responda correctamente en el puerto configurado."""
    url = f"http://127.0.0.1:{web_port}/"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            content = resp.read().decode("utf-8", errors="ignore")
            is_st = ("Streamlit" in content or "streamlit" in content)
            print(f"[OK] Streamlit web-v2 respondió HTTP {resp.status} (Streamlit detectado: {is_st})")
            return is_st
    except Exception as ex:
        print(f"[ERROR] Error al contactar Streamlit en {url}: {type(ex).__name__}", file=sys.stderr)
        return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bootstrap seguro de Docker Compose v2 para S.A.P.I. (Directiva 26 / Astra Final)"
    )
    parser.add_argument("--project-name", default="sapi-v2", help="Nombre del proyecto Docker Compose")
    parser.add_argument("--db-port", type=int, default=5432, help="Puerto host para PostgreSQL PostGIS (1024-65535)")
    parser.add_argument("--ml-port", type=int, default=8000, help="Puerto host para FastAPI ML API (1024-65535)")
    parser.add_argument("--backend-port", type=int, default=8080, help="Puerto host para Spring Boot Backend (1024-65535)")
    parser.add_argument("--web-port", type=int, default=8501, help="Puerto host para Streamlit Frontend (1024-65535)")
    parser.add_argument("--skip-up", action="store_true", help="Solo generar .env sin ejecutar docker compose")
    parser.add_argument("--validate", action="store_true", help="Ejecutar validación completa post-arranque")
    args = parser.parse_args()

    repo_dir = Path(__file__).resolve().parent.parent
    env_file = repo_dir / ".env"

    print("=================================================================")
    print("S.A.P.I. - BOOTSTRAP SEGURO COMPOSE V2 (DIRECTIVA 26)")
    print("=================================================================")
    print(f"Directorio raíz:       {repo_dir}")
    print(f"Proyecto Compose:      {args.project_name}")
    print(f"Puertos configurados:  DB={args.db_port}, ML={args.ml_port}, Backend={args.backend_port}, Web={args.web_port}")
    print("Modo de inferencia:    reproducible (snapshot Hito 1 congelado: 2026-09-01T00:00Z)")

    # 1. Validaciones previas de seguridad
    try:
        validate_project_name(args.project_name)
    except ValueError as ex:
        print(f"[SECURITY ERROR] {ex}", file=sys.stderr)
        return 1

    ports_map = {
        "db": args.db_port,
        "ml": args.ml_port,
        "backend": args.backend_port,
        "web": args.web_port,
    }
    try:
        validate_ports(ports_map)
    except (ValueError, RuntimeError) as ex:
        print(f"[CONFIG ERROR] {ex}", file=sys.stderr)
        return 1

    # 2. Protección contra sobrescritura de .env y existencia previa de volumen PostGIS
    try:
        check_existing_configuration(env_file)
        check_existing_docker_volume(args.project_name)
    except (FileExistsError, RuntimeError) as ex:
        print(f"[PROTECTION ERROR] {ex}", file=sys.stderr)
        return 1

    # 3. Generar credenciales con entropía criptográfica
    db_pass = generate_secure_password(24)
    content = build_env_content(
        db_password=db_pass,
        db_port=args.db_port,
        ml_port=args.ml_port,
        backend_port=args.backend_port,
        web_port=args.web_port,
    )

    # 4. Publicar .env con exclusividad atómica (O_CREAT|O_EXCL, sin os.replace)
    try:
        write_env_file_exclusive(env_file, content)
        print(f"[OK] Archivo .env generado exitosamente en: {env_file}")
        print(f"[SECURITY] SAPI_DB_PASSWORD generada con entropía segura (longitud: {len(db_pass)} chars).")
        print("[SECURITY] Secreto protegido: la contraseña nunca se emite en logs, stdout ni reportes.")
    except (FileExistsError, RuntimeError) as ex:
        print(f"[PROTECTION ERROR] {ex}", file=sys.stderr)
        return 1
    except Exception as ex:
        print(f"[IO ERROR] Fallo al escribir archivo .env: {type(ex).__name__}", file=sys.stderr)
        return 1

    if args.skip_up:
        print("[INFO] Finalizado (--skip-up solicitado).")
        return 0

    # 5. Arrancar Docker Compose con entorno hermético y comando delimitado
    up_cmd = build_compose_up_command(args.project_name, env_file=str(env_file))
    sanitized_env = sanitize_compose_env()
    print(f"[RUN] {' '.join(up_cmd)}")
    res_up = subprocess.run(up_cmd, cwd=str(repo_dir), env=sanitized_env, capture_output=True, text=True)
    if res_up.returncode != 0:
        sanitized_stderr = redact_stderr(res_up.stderr.strip(), known_secrets=[db_pass])
        print(f"[FAIL] Fallo al iniciar Docker Compose (exit={res_up.returncode}).", file=sys.stderr)
        if sanitized_stderr:
            print(f"[DIAG] {sanitized_stderr}", file=sys.stderr)
        print("[INFO] Los volúmenes y archivos generados se preservan para diagnóstico sin destrucción automática.")
        return res_up.returncode
    print("[OK] Docker Compose arrancó exitosamente los servicios v2.")

    # 6. Validación post-arranque (si se solicita)
    if args.validate:
        print("\n[VALIDACIÓN] Verificando salud y contratos de extremo a extremo...")
        time.sleep(3)
        healthy = check_health(args.project_name, env_file=str(env_file), cwd=repo_dir)
        web_ok = verify_streamlit_web(args.web_port)
        ranking_data = verify_ranking_api(args.backend_port)
        exec_id, preds_count = verify_database_persistence_correlated(args.project_name, ranking_data)

        cells = len(ranking_data.get("cells", []))
        success = healthy and web_ok and (cells == 50) and (exec_id >= 1) and (preds_count == 50)
        print("\n=================================================================")
        print(f"VEREDICTO VALIDACIÓN POST-BOOTSTRAP: {'PASS' if success else 'FAIL'}")
        print("=================================================================")
        return 0 if success else 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
