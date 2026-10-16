"""Pruebas discriminantes RED/GREEN para scripts/bootstrap_compose_v2.py (Directiva 26 / Astra Final).

Metodología obligatoria por hallazgo:
1. Crear prueba que reproduzca el fallo existente (RED).
2. Implementar la corrección.
3. Demostrar que la misma prueba pasa (GREEN).

Hallazgos cubiertos:
- P1-ENV: Carrera entre comprobar existencia y publicar .env (O_CREAT|O_EXCL sin os.replace).
- P1-VOL: Distinguir volumen inexistente / existente / Docker inaccesible.
- P1-COMPOSE: Entorno hermético (COMPOSE_ENV_FILES, COMPOSE_DISABLE_ENV_FILE, etc.).
- P2-SECRETS: Redacción de stderr externo con secretos.
- P2-ACL: Verificación real de icacls y FAIL CLOSED si no funciona.
- P2-HEALTH: Detección de unhealthy y servicios no autorizados.
- P2-PERSIST: Correlación con ranking JSON, no fingerprint fijo.
- P2-PARTIAL: Sin limpieza destructiva automática.
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

from scripts.bootstrap_compose_v2 import (
    COMPOSE_HOSTILE_VARS,
    SERVICES_V2_EXPLICIT,
    build_compose_up_command,
    build_env_content,
    check_existing_configuration,
    check_existing_docker_volume,
    check_health,
    generate_secure_password,
    main,
    redact_stderr,
    sanitize_compose_env,
    validate_ports,
    validate_project_name,
    write_env_file_exclusive,
)


class TestP1EnvRaceCondition(unittest.TestCase):
    """P1: Eliminar carrera entre comprobación y publicación de .env."""

    def test_concurrent_creation_preserves_existing_content(self):
        """RED/GREEN: Simula creación concurrente del archivo entre check y publish.

        Si otro proceso crea .env después de check_existing_configuration pero antes
        de write_env_file_exclusive, el contenido concurrente debe permanecer intacto
        y el bootstrap debe abortar con FileExistsError.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            concurrent_content = "CONCURRENT_PASSWORD=do_not_overwrite_me\n"

            # Simular la carrera: crear el archivo justo antes de write_env_file_exclusive
            # (esto reproduce el gap que existía con os.replace)
            env_path.write_text(concurrent_content, encoding="utf-8")

            # write_env_file_exclusive usa O_CREAT|O_EXCL, así que debe fallar
            with self.assertRaises(FileExistsError) as ctx:
                write_env_file_exclusive(env_path, "NEW_CONTENT=should_not_appear\n")

            self.assertIn("concurrente", str(ctx.exception).lower())
            # Contenido concurrente intacto
            self.assertEqual(env_path.read_text(encoding="utf-8"), concurrent_content)

    def test_threaded_race_only_one_wins(self):
        """RED/GREEN: Dos hilos intentan crear .env simultáneamente; solo uno debe ganar."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            results = {"success": 0, "fail": 0}
            lock = threading.Lock()

            def attempt(content_id):
                try:
                    write_env_file_exclusive(env_path, f"WRITER={content_id}\n")
                    with lock:
                        results["success"] += 1
                except FileExistsError:
                    with lock:
                        results["fail"] += 1

            t1 = threading.Thread(target=attempt, args=("A",))
            t2 = threading.Thread(target=attempt, args=("B",))
            t1.start()
            t2.start()
            t1.join()
            t2.join()

            self.assertEqual(results["success"], 1, "Solo un escritor debe ganar.")
            self.assertEqual(results["fail"], 1, "El otro debe fallar con FileExistsError.")
            content = env_path.read_text(encoding="utf-8")
            self.assertIn("WRITER=", content)

    def test_no_os_replace_in_source(self):
        """RED/GREEN: Verificar que write_env_file_exclusive no use os.replace() sobre el destino."""
        import inspect
        source = inspect.getsource(write_env_file_exclusive)
        self.assertNotIn("os.replace", source, "No debe usar os.replace() sobre el .env de destino.")

    def test_exclusive_write_creates_valid_file(self):
        """GREEN: Escritura exclusiva crea archivo con contenido correcto."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            content = build_env_content("test_secret_123", 5432, 8000, 8080, 8501)
            write_env_file_exclusive(env_path, content)

            self.assertTrue(env_path.exists())
            self.assertEqual(env_path.read_text(encoding="utf-8"), content)


class TestP1VolumeVerification(unittest.TestCase):
    """P1: Verificación de volúmenes distingue inexistente / existente / Docker inaccesible."""

    def test_case_a_volume_inexistent_allows_continue(self):
        """GREEN: Volumen inexistente → no lanza excepción."""
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = "\n"  # Sin resultados

        with patch("subprocess.run", return_value=mock_res):
            # No debe lanzar excepción
            check_existing_docker_volume("new-project")

    def test_case_b_volume_exists_blocks(self):
        """RED/GREEN: Volumen existente → RuntimeError."""
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = "existing-project_sapi_v2_pgdata\n"

        with patch("subprocess.run", return_value=mock_res):
            with self.assertRaises(RuntimeError) as ctx:
                check_existing_docker_volume("existing-project")
            self.assertIn("ya existe", str(ctx.exception))

    def test_case_c_docker_inaccessible_blocks(self):
        """RED/GREEN: Docker inaccesible (returncode != 0) → RuntimeError, NOT silently continue."""
        mock_res = MagicMock()
        mock_res.returncode = 1
        mock_res.stdout = ""
        mock_res.stderr = "Cannot connect to the Docker daemon"

        with patch("subprocess.run", return_value=mock_res):
            with self.assertRaises(RuntimeError) as ctx:
                check_existing_docker_volume("any-project")
            self.assertIn("FAIL CLOSED", str(ctx.exception))

    def test_case_c_docker_not_found_blocks(self):
        """RED/GREEN: Docker CLI not found → RuntimeError, NOT silently continue."""
        with patch("subprocess.run", side_effect=FileNotFoundError("docker not found")):
            with self.assertRaises(RuntimeError) as ctx:
                check_existing_docker_volume("any-project")
            self.assertIn("FAIL CLOSED", str(ctx.exception))

    def test_case_c_docker_timeout_blocks(self):
        """RED/GREEN: Docker timeout → RuntimeError, NOT silently continue."""
        import subprocess as sp
        with patch("subprocess.run", side_effect=sp.TimeoutExpired(cmd="docker", timeout=15)):
            with self.assertRaises(RuntimeError) as ctx:
                check_existing_docker_volume("any-project")
            self.assertIn("FAIL CLOSED", str(ctx.exception))


class TestP1ComposeHermeticEnv(unittest.TestCase):
    """P1: Entorno Compose hermético contra todos los vectores heredados."""

    def test_all_hostile_vars_neutralized(self):
        """RED/GREEN: Verifica que TODOS los vectores de Astra se neutralizan."""
        hostile_env = {
            "COMPOSE_ENV_FILES": ".env.example,.env.production",
            "COMPOSE_DISABLE_ENV_FILE": "true",
            "COMPOSE_PROFILES": "legacy,ops,presentation",
            "COMPOSE_FILE": "docker-compose.operational.yml",
            "COMPOSE_PROJECT_NAME": "hostile_project",
            "SAPI_DB_PASSWORD": "leaked_external_password",
            "SAPI_DB_PORT": "9999",
            "SAPI_ML_PORT": "9998",
            "SAPI_BACKEND_PORT": "9997",
            "SAPI_WEB_PORT": "9996",
            "POSTGRES_PASSWORD": "leaked_postgres_password",
            "POSTGRES_USER": "attacker",
            "PATH": "/usr/bin",
            "SYSTEMROOT": "C:\\Windows",
        }
        with patch.dict("os.environ", hostile_env, clear=True):
            clean = sanitize_compose_env()

            # ALL hostile Compose vars must be gone except COMPOSE_PROFILES which is overwritten
            self.assertNotIn("COMPOSE_ENV_FILES", clean)
            self.assertNotIn("COMPOSE_DISABLE_ENV_FILE", clean)
            self.assertNotIn("COMPOSE_FILE", clean)
            self.assertNotIn("COMPOSE_PROJECT_NAME", clean)
            # COMPOSE_PROFILES must be exactly "presentation", not the hostile value
            self.assertEqual(clean["COMPOSE_PROFILES"], "presentation")

            # ALL SAPI_* and POSTGRES_* must be gone
            self.assertNotIn("SAPI_DB_PASSWORD", clean)
            self.assertNotIn("SAPI_DB_PORT", clean)
            self.assertNotIn("SAPI_ML_PORT", clean)
            self.assertNotIn("SAPI_BACKEND_PORT", clean)
            self.assertNotIn("SAPI_WEB_PORT", clean)
            self.assertNotIn("POSTGRES_PASSWORD", clean)
            self.assertNotIn("POSTGRES_USER", clean)

            # System vars preserved
            self.assertEqual(clean["PATH"], "/usr/bin")
            self.assertEqual(clean["SYSTEMROOT"], "C:\\Windows")

    def test_compose_command_includes_env_file(self):
        """GREEN: Comando Compose incluye --env-file explícito."""
        cmd = build_compose_up_command("sapi-test", env_file="/path/to/.env")
        self.assertIn("--env-file", cmd)
        self.assertIn("/path/to/.env", cmd)
        # Also verify explicit file and services
        self.assertIn("-f", cmd)
        self.assertIn("docker-compose.yml", cmd)
        services_in_cmd = cmd[cmd.index("--build") + 1:]
        self.assertEqual(list(services_in_cmd), list(SERVICES_V2_EXPLICIT))


class TestP2SecretRedaction(unittest.TestCase):
    """P2: Redacción de stderr externo que contenga secretos."""

    def test_stderr_with_password_is_redacted(self):
        """RED/GREEN: stderr simulado con contraseña debe ser sanitizado."""
        secret = "super_secret_db_password_xyz"
        stderr_text = f"FATAL: password authentication failed for user 'sapi' (password was '{secret}')"
        sanitized = redact_stderr(stderr_text, known_secrets=[secret])
        self.assertNotIn(secret, sanitized)
        self.assertIn("[REDACTED]", sanitized)

    def test_stderr_without_secret_passes_through(self):
        """GREEN: stderr sin secretos pasa filtrado pero legible."""
        stderr_text = "Error: service 'backend' failed to build"
        sanitized = redact_stderr(stderr_text, known_secrets=["unrelated_secret"])
        self.assertEqual(sanitized, stderr_text)

    def test_empty_stderr(self):
        """GREEN: stderr vacío no falla."""
        self.assertEqual(redact_stderr("", known_secrets=["secret"]), "")
        self.assertEqual(redact_stderr("", known_secrets=None), "")


class TestP2HealthChecks(unittest.TestCase):
    """P2: Validación estricta de healthy/unhealthy."""

    def test_unhealthy_container_detected(self):
        """RED/GREEN: check_health debe fallar si un contenedor reporta UNHEALTHY."""
        mock_output = [
            {"Service": "db-v2", "State": "running", "Health": "healthy"},
            {"Service": "ml-api", "State": "running", "Health": "unhealthy"},
            {"Service": "backend", "State": "running", "Health": "healthy"},
            {"Service": "web-v2", "State": "running", "Health": "no check"},
        ]
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = json.dumps(mock_output)

        with patch("subprocess.run", return_value=mock_res):
            result = check_health("test-proj")
            self.assertFalse(result)

    def test_unauthorized_service_detected(self):
        """RED/GREEN: check_health debe fallar si se detecta un servicio legacy."""
        mock_output = [
            {"Service": "db-v2", "State": "running", "Health": "healthy"},
            {"Service": "ml-api", "State": "running", "Health": "healthy"},
            {"Service": "backend", "State": "running", "Health": "healthy"},
            {"Service": "web-v2", "State": "running", "Health": "no check"},
            {"Service": "db-postgis", "State": "running", "Health": "healthy"},
        ]
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = json.dumps(mock_output)

        with patch("subprocess.run", return_value=mock_res):
            result = check_health("test-proj")
            self.assertFalse(result)


class TestP2PartialFailure(unittest.TestCase):
    """P2: Sin limpieza destructiva automática ante fallos parciales."""

    def test_compose_failure_no_down_v(self):
        """RED/GREEN: Fallo de arranque de Compose no ejecuta 'docker compose down -v'."""
        mock_res = MagicMock()
        mock_res.returncode = 1
        mock_res.stderr = "Build error transitorio"

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("scripts.bootstrap_compose_v2.validate_project_name"), \
                 patch("scripts.bootstrap_compose_v2.validate_ports"), \
                 patch("scripts.bootstrap_compose_v2.check_existing_configuration"), \
                 patch("scripts.bootstrap_compose_v2.check_existing_docker_volume"), \
                 patch("scripts.bootstrap_compose_v2.write_env_file_exclusive"), \
                 patch("subprocess.run", return_value=mock_res) as mock_run:

                with patch("sys.argv", ["bootstrap_compose_v2.py", "--project-name", "sapi-test"]):
                    exit_code = main()
                    self.assertEqual(exit_code, 1)

                    for call_args in mock_run.call_args_list:
                        cmd = call_args[0][0]
                        self.assertNotIn("down", cmd)
                        self.assertNotIn("-v", cmd)


class TestP1NoForce(unittest.TestCase):
    """P1: --force retirado."""

    def test_force_flag_rejected(self):
        """RED/GREEN: --force debe ser rechazado por el parser."""
        with patch("sys.argv", ["bootstrap_compose_v2.py", "--force"]), \
             patch("sys.stderr", new_callable=io.StringIO):
            with self.assertRaises(SystemExit) as ctx:
                main()
            self.assertEqual(ctx.exception.code, 2)


class TestProjectNameAndPorts(unittest.TestCase):
    """P2: Validación de nombres de proyecto y puertos."""

    def test_project_name_validation(self):
        """GREEN: Nombres válidos aceptados, inválidos rechazados."""
        for name in ["sapi-v2", "sapi_test_01", "my-project-123"]:
            validate_project_name(name)

        for name in ["SAPI-UPPERCASE", "sapi project", "-invalid", "_under", "a" * 64, "sapi$"]:
            with self.assertRaises(ValueError):
                validate_project_name(name)

    def test_port_range_and_duplicates(self):
        """GREEN: Rango y duplicados validados correctamente."""
        with patch("scripts.bootstrap_compose_v2.check_port_in_use", return_value=False):
            validate_ports({"db": 15449, "ml": 18019, "backend": 18099, "web": 18509})

        with patch("scripts.bootstrap_compose_v2.check_port_in_use", return_value=False):
            with self.assertRaises(ValueError):
                validate_ports({"db": 80, "ml": 18019, "backend": 18099, "web": 18509})

        with patch("scripts.bootstrap_compose_v2.check_port_in_use", return_value=False):
            with self.assertRaises(ValueError):
                validate_ports({"db": 15449, "ml": 15449, "backend": 18099, "web": 18509})

    def test_port_collision(self):
        """GREEN: Colisión de puertos detectada."""
        def mock_in_use(port, host="127.0.0.1"):
            return port == 18099
        with patch("scripts.bootstrap_compose_v2.check_port_in_use", side_effect=mock_in_use):
            with self.assertRaises(RuntimeError) as ctx:
                validate_ports({"db": 15449, "ml": 18019, "backend": 18099, "web": 18509})
            self.assertIn("18099", str(ctx.exception))


class TestSecurePasswordEntropy(unittest.TestCase):
    """P2: Credenciales criptográficas impredecibles."""

    def test_passwords_unique_and_safe(self):
        """GREEN: 50 contraseñas generadas son únicas y sin caracteres problemáticos."""
        passwords = [generate_secure_password(24) for _ in range(50)]
        self.assertEqual(len(set(passwords)), 50)
        for p in passwords:
            self.assertGreaterEqual(len(p), 24)
            self.assertFalse(" " in p or "\n" in p)


class TestWindowsAclFailClosed(unittest.TestCase):
    """P1/P2: Si icacls falla o no se pueden verificar ACL, FAIL CLOSED."""

    def test_acl_failure_fails_closed_and_deletes_file(self):
        """RED/GREEN: Si _restrict_acl_windows retorna False, write_env_file_exclusive
        debe fallar (RuntimeError) y eliminar el archivo para no exponer secretos.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            with patch("sys.platform", "win32"), \
                 patch("scripts.bootstrap_compose_v2._restrict_acl_windows", return_value=False):
                with self.assertRaises(RuntimeError) as ctx:
                    write_env_file_exclusive(env_path, "SECRET=should_be_deleted\n")
                self.assertIn("FAIL CLOSED", str(ctx.exception))
                self.assertFalse(env_path.exists(), "El archivo debe haber sido eliminado (FAIL CLOSED).")


class TestP2CorrelatedPersistence(unittest.TestCase):
    """P2: Persistencia correlacionada con el ranking JSON."""

    def test_correlated_persistence_success(self):
        """GREEN: Correlaciona model_version, inputs_fingerprint y 50 celdas."""
        from scripts.bootstrap_compose_v2 import verify_database_persistence_correlated
        ranking_data = {
            "model_version": "prototype_model_d_v1",
            "inputs_fingerprint": "09482d6b3a8b4ab210c32cdddaec352c8eca8be25bbf76592799c1702096c5a3",
            "firms_origin": "reproducibility",
            "cells": [{"cell_id": f"VP-{i:03d}"} for i in range(1, 51)],
        }
        # Mock de ejecución en DB
        mock_exec_res = MagicMock()
        mock_exec_res.returncode = 0
        mock_exec_res.stdout = "1|prototype_model_d_v1|reproducibility|09482d6b3a8b4ab210c32cdddaec352c8eca8be25bbf76592799c1702096c5a3\n"

        # Mock de celdas vinculadas
        mock_cells_res = MagicMock()
        mock_cells_res.returncode = 0
        mock_cells_res.stdout = "50\n"

        with patch("subprocess.run", side_effect=[mock_exec_res, mock_cells_res]):
            exec_id, count = verify_database_persistence_correlated("sapi-test", ranking_data)
            self.assertEqual(exec_id, 1)
            self.assertEqual(count, 50)

    def test_correlated_persistence_mismatch_fails(self):
        """RED/GREEN: Mismatch en model_version detectado y bloqueado."""
        from scripts.bootstrap_compose_v2 import verify_database_persistence_correlated
        ranking_data = {
            "model_version": "prototype_model_d_v1",
            "inputs_fingerprint": "09482d6b3a8b4ab210c32cdddaec352c8eca8be25bbf76592799c1702096c5a3",
            "cells": [{"cell_id": "VP-001"}],
        }
        mock_exec_res = MagicMock()
        mock_exec_res.returncode = 0
        mock_exec_res.stdout = "1|DIFFERENT_MODEL|reproducibility|09482d6b3a8b4ab210c32cdddaec352c8eca8be25bbf76592799c1702096c5a3\n"

        with patch("subprocess.run", return_value=mock_exec_res):
            with self.assertRaises(RuntimeError) as ctx:
                verify_database_persistence_correlated("sapi-test", ranking_data)
            self.assertIn("mismatch", str(ctx.exception))


class TestDirective28DefectBFirmsOriginCorrelation(unittest.TestCase):
    """Directiva 28 / Defecto B: firms_origin debe comparase obligatoriamente, no solo
    model_version e inputs_fingerprint. Matriz RED/GREEN completa de 6 casos."""

    _MODEL = "prototype_model_d_v1"
    _FP = "09482d6b3a8b4ab210c32cdddaec352c8eca8be25bbf76592799c1702096c5a3"

    def _ranking(self, firms_origin=None, model=None, fp=None, n_cells=50):
        data = {
            "model_version": model or self._MODEL,
            "inputs_fingerprint": fp or self._FP,
            "cells": [{"cell_id": f"VP-{i:03d}"} for i in range(1, n_cells + 1)],
        }
        if firms_origin is not None:
            data["firms_origin"] = firms_origin
        return data

    def _mock_exec_res(self, exec_id=1, model=None, firms=None, fp=None):
        res = MagicMock()
        res.returncode = 0
        res.stdout = f"{exec_id}|{model or self._MODEL}|{firms}|{fp or self._FP}\n"
        return res

    def _mock_cells_res(self, count=50):
        res = MagicMock()
        res.returncode = 0
        res.stdout = f"{count}\n"
        return res

    def test_case1_api_reproducibility_sql_current_fails(self):
        """Caso 1: API firms_origin='reproducibility' / SQL persistido='current' -> FAIL."""
        from scripts.bootstrap_compose_v2 import verify_database_persistence_correlated
        ranking = self._ranking(firms_origin="reproducibility")
        with patch("subprocess.run", side_effect=[self._mock_exec_res(firms="current"), self._mock_cells_res()]):
            with self.assertRaises(RuntimeError) as ctx:
                verify_database_persistence_correlated("sapi-test", ranking)
            self.assertIn("firms_origin mismatch", str(ctx.exception))

    def test_case2_api_current_sql_reproducibility_fails(self):
        """Caso 2: API firms_origin='current' / SQL persistido='reproducibility' -> FAIL."""
        from scripts.bootstrap_compose_v2 import verify_database_persistence_correlated
        ranking = self._ranking(firms_origin="current")
        with patch("subprocess.run", side_effect=[self._mock_exec_res(firms="reproducibility"), self._mock_cells_res()]):
            with self.assertRaises(RuntimeError) as ctx:
                verify_database_persistence_correlated("sapi-test", ranking)
            self.assertIn("firms_origin mismatch", str(ctx.exception))

    def test_case3_different_model_fails(self):
        """Caso 3: model_version diferente -> FAIL (regresión del caso ya cubierto)."""
        from scripts.bootstrap_compose_v2 import verify_database_persistence_correlated
        ranking = self._ranking(firms_origin="current")
        with patch("subprocess.run", side_effect=[self._mock_exec_res(model="OTHER_MODEL", firms="current"), self._mock_cells_res()]):
            with self.assertRaises(RuntimeError) as ctx:
                verify_database_persistence_correlated("sapi-test", ranking)
            self.assertIn("model_version mismatch", str(ctx.exception))

    def test_case4_different_fingerprint_fails(self):
        """Caso 4: inputs_fingerprint diferente -> FAIL."""
        from scripts.bootstrap_compose_v2 import verify_database_persistence_correlated
        ranking = self._ranking(firms_origin="current")
        with patch("subprocess.run", side_effect=[self._mock_exec_res(firms="current", fp="0000deadbeef"), self._mock_cells_res()]):
            with self.assertRaises(RuntimeError) as ctx:
                verify_database_persistence_correlated("sapi-test", ranking)
            self.assertIn("inputs_fingerprint mismatch", str(ctx.exception))

    def test_case5_cell_count_not_50_fails(self):
        """Caso 5: cantidad de celdas vinculadas != 50 -> FAIL."""
        from scripts.bootstrap_compose_v2 import verify_database_persistence_correlated
        ranking = self._ranking(firms_origin="current")
        with patch("subprocess.run", side_effect=[self._mock_exec_res(firms="current"), self._mock_cells_res(count=37)]):
            with self.assertRaises(RuntimeError) as ctx:
                verify_database_persistence_correlated("sapi-test", ranking)
            self.assertIn("se requieren exactamente 50", str(ctx.exception))

    def test_case6_model_fingerprint_origin_and_50_cells_match_passes(self):
        """Caso 6: model_version, inputs_fingerprint, firms_origin y 50 celdas coinciden -> PASS."""
        from scripts.bootstrap_compose_v2 import verify_database_persistence_correlated
        ranking = self._ranking(firms_origin="current")
        with patch("subprocess.run", side_effect=[self._mock_exec_res(firms="current"), self._mock_cells_res(count=50)]):
            exec_id, count = verify_database_persistence_correlated("sapi-test", ranking)
            self.assertEqual(exec_id, 1)
            self.assertEqual(count, 50)

    def test_missing_firms_origin_in_ranking_fails(self):
        """Prohibido aceptar correlación si el ranking no trae firms_origin alguno."""
        from scripts.bootstrap_compose_v2 import verify_database_persistence_correlated
        ranking = self._ranking(firms_origin=None)
        with patch("subprocess.run", side_effect=[self._mock_exec_res(firms="current"), self._mock_cells_res()]):
            with self.assertRaises(RuntimeError) as ctx:
                verify_database_persistence_correlated("sapi-test", ranking)
            self.assertIn("firms_origin", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
