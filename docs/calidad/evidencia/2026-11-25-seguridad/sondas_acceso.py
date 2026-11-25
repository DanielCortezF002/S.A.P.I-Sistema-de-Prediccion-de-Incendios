"""Sondas de acceso denegado contra el stack local `sapi-h3-518c0b5` (C4 · Seguridad).

Uso: py -I sondas_acceso.py <salida.json>

Solo biblioteca estándar. Solo apunta a 127.0.0.1 en los puertos del proyecto
`sapi-h3-518c0b5` (18501 web, 18080 backend, 18000 ml-api, 15432 db); aborta si
se le pide otro puerto. No envía credenciales, no prueba contraseñas y no llama
a GET /api/v1/ranking ni a POST /predict con un cuerpo válido (no dispara el
scoring). El escenario y el criterio están en ../../seguridad-c4-2026-11-25.md,
commiteados antes de la corrida.
"""

import hashlib
import json
import socket
import struct
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

WEB, BACKEND, ML, DB = 18501, 18080, 18000, 15432
ALLOWED_PORTS = {WEB, BACKEND, ML, DB}
DENIED = {401, 403, 404, 405}

# Cadenas que no deben aparecer en ningún cuerpo de respuesta de las sondas A y C.
SENTINELS = [
    "jdbc:", "password", "db_password", "sapi_secret", "POSTGRES_", "SPRING_DATASOURCE",
    "ejecuciones", "predicciones_celda", "celdas_geom", "inputs_fingerprint",
    "Exception", "Traceback", "at cl.sapi", "at org.springframework", "root:x:0:0",
]

# (grupo, id, puerto, método, ruta, cuerpo)
# A: rutas no publicadas que podrían exponer datos persistidos o configuración.
#    Esperado: 401/403/404/405 y 0 centinelas.
# B: superficie de documentación (observación declarada; sin criterio de cumplimiento).
# C: entrada maliciosa en la ruta pública. Esperado: 422 del contrato y 0 centinelas.
PROBES = [
    ("A", "A01", BACKEND, "GET", "/api/v1/ejecuciones", None),
    ("A", "A02", BACKEND, "GET", "/api/v1/predicciones", None),
    ("A", "A03", BACKEND, "GET", "/api/v1/celdas", None),
    ("A", "A04", BACKEND, "GET", "/api/v1/ranking/history", None),
    ("A", "A05", BACKEND, "GET", "/api/v1/admin", None),
    ("A", "A06", BACKEND, "GET", "/actuator", None),
    ("A", "A07", BACKEND, "GET", "/actuator/env", None),
    ("A", "A08", BACKEND, "GET", "/actuator/heapdump", None),
    ("A", "A09", BACKEND, "GET", "/actuator/configprops", None),
    ("A", "A10", BACKEND, "GET", "/application.properties", None),
    ("A", "A11", BACKEND, "GET", "/db/migration/V002__create_sapi_v2_schema.sql", None),
    ("A", "A12", BACKEND, "GET", "/..;/..;/etc/passwd", None),
    ("A", "A13", BACKEND, "GET", "/%2e%2e/%2e%2e/etc/passwd", None),
    ("A", "A14", BACKEND, "POST", "/api/v1/ranking", b"{}"),
    ("A", "A15", BACKEND, "PUT", "/api/v1/ranking", b"{}"),
    ("A", "A16", BACKEND, "DELETE", "/api/v1/ranking", None),
    ("A", "A17", ML, "GET", "/predict", None),
    ("A", "A18", ML, "GET", "/ejecuciones", None),
    ("A", "A19", ML, "GET", "/data/raw", None),
    ("A", "A20", ML, "GET", "/models", None),
    ("A", "A21", ML, "GET", "/%2e%2e/%2e%2e/etc/passwd", None),
    ("A", "A22", WEB, "GET", "/app/static/%2e%2e/%2e%2e/etc/passwd", None),
    ("A", "A23", WEB, "GET", "/.env", None),
    ("B", "B01", ML, "GET", "/docs", None),
    ("B", "B02", ML, "GET", "/openapi.json", None),
    ("B", "B03", ML, "GET", "/redoc", None),
    ("B", "B04", BACKEND, "GET", "/v3/api-docs", None),
    ("B", "B05", BACKEND, "GET", "/swagger-ui.html", None),
    ("C", "C01", BACKEND, "GET", "/api/v1/ranking?forecast_time=%27%20OR%201%3D1--", None),
    ("C", "C02", BACKEND, "GET", "/api/v1/ranking?forecast_time=%ZZ", None),
    ("C", "C03", BACKEND, "GET", "/api/v1/ranking?forecast_time=2026-09-01T00:00:00Z%3BDROP%20TABLE%20ejecuciones", None),
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def http_probe(group, pid, port, method, path, body):
    assert port in ALLOWED_PORTS, port
    url = f"http://127.0.0.1:{port}{path}"
    req = urllib.request.Request(url, data=body, method=method)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    started = now()
    try:
        resp = opener.open(req, timeout=20)
        status, raw, headers = resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as err:
        status, raw, headers = err.code, err.read(), dict(err.headers)
    except Exception as err:  # conexión rechazada, timeout, etc.
        return {"grupo": group, "id": pid, "puerto": port, "metodo": method, "ruta": path,
                "inicio_utc": started, "estado": None, "error": repr(err)}
    text = raw.decode("utf-8", "replace")
    hits = [s for s in SENTINELS if s.lower() in text.lower()]
    return {
        "grupo": group, "id": pid, "puerto": port, "metodo": method, "ruta": path,
        "inicio_utc": started, "estado": status,
        "content_type": headers.get("Content-Type"),
        "bytes": len(raw), "sha256_cuerpo": hashlib.sha256(raw).hexdigest(),
        "cuerpo_200c": text[:200], "centinelas": hits,
    }


def pg_probe():
    """Mensaje de arranque PostgreSQL sin contraseña: registra qué autenticación exige."""
    started = now()
    params = b"user\x00sapi\x00database\x00sapi_v2\x00\x00"
    msg = struct.pack("!II", 8 + len(params), 196608) + params
    try:
        with socket.create_connection(("127.0.0.1", DB), timeout=10) as s:
            s.sendall(msg)
            head = s.recv(5)
            kind, length = head[:1], struct.unpack("!I", head[1:5])[0]
            payload = s.recv(length - 4)
            s.sendall(b"X\x00\x00\x00\x04")  # Terminate
    except Exception as err:
        return {"id": "D01", "inicio_utc": started, "error": repr(err)}
    out = {"id": "D01", "inicio_utc": started, "tipo_mensaje": kind.decode()}
    if kind == b"R":
        code = struct.unpack("!I", payload[:4])[0]
        out["codigo_auth"] = code
        out["mecanismos"] = [m for m in payload[4:].decode("ascii", "replace").split("\x00") if m]
        out["exige_credencial"] = code != 0  # 0 = AuthenticationOk sin contraseña
    elif kind == b"E":
        out["error_servidor"] = payload.decode("utf-8", "replace")[:200]
        out["exige_credencial"] = True
    return out


def main() -> None:
    results = [http_probe(*p) for p in PROBES]
    db = pg_probe()
    a = [r for r in results if r["grupo"] == "A"]
    c = [r for r in results if r["grupo"] == "C"]
    summary = {
        "A_total": len(a),
        "A_denegadas": sum(r.get("estado") in DENIED for r in a),
        "C_total": len(c),
        "C_422": sum(r.get("estado") == 422 for r in c),
        "centinelas_AC": sum(len(r.get("centinelas", [])) for r in a + c),
        "D01_exige_credencial": db.get("exige_credencial"),
    }
    out = {"inicio_utc": results[0]["inicio_utc"], "fin_utc": now(), "resumen": summary,
           "http": results, "db": db}
    with open(sys.argv[1], "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
