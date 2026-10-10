"""Preflight de la arquitectura v2 en Docker Compose (SAPI-60).

Levanta el `docker-compose.yml` por defecto (db-v2, ml-api, backend) en un
proyecto Compose aislado y verifica cada criterio de SAPI-60 con el comando
que lo prueba y su resultado observado:

  CA1  `config --services`, `up -d --wait` y `ps`: los tres servicios en
       127.0.0.1:8080/8000/5432.
  CA2  estado `healthy` de cada servicio y GET /health = 200 (backend y ML);
       pg_isready por TCP en la base.
  CA4  `down` sin -v y `up` de nuevo: las ejecuciones persistidas siguen ahí.
  CA6  build de las imágenes desde el checkout (el operador usa un clon limpio).

Verifica además la integración real de la cadena:
  Flyway V001-V003 aplicadas por el backend (`flyway_schema_history`), 50
  celdas en `celdas_geom`; `GET /api/v1/ranking` = 200 con 50 celdas,
  `relative_rank` y `scientific_model_validation=false`, con los mismos bytes
  que `POST /predict` del ML (SAPI-57); la ejecución y sus 50 filas
  persistidas, sin duplicarse al repetir la evaluación (SAPI-59); y
  `db/queries/latest_ranking.sql` por psql dentro del contenedor (50 filas, el
  mismo orden que la respuesta).

El proyecto Compose tiene nombre propio (`sapi60-preflight` por defecto), así
que no toca los contenedores ni los volúmenes del proyecto de desarrollo. Al
terminar ejecuta `down -v` solo sobre ese proyecto (salvo `--keep`) y se niega
a hacerlo si el nombre no empieza por `sapi60-preflight`.

Lee la configuración de `.env` del checkout (copiado de `.env.example`, como
indica el README) y nunca imprime ni guarda su contenido. La evidencia se
escribe en `--out-dir` con rutas, usuario y equipo redactados.

Uso:
    python scripts/compose_v2_preflight.py --out-dir ../sapi60-evidence
    python scripts/compose_v2_preflight.py --out-dir DIR --skip-build --keep

Requiere Docker y Docker Compose v2; solo usa la librería estándar.
Códigos de salida: 0 = todo PASS, 1 = algún FAIL.
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import platform
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PROJECT_PREFIX = "sapi60-preflight"
V2_SERVICES = ("db-v2", "ml-api", "backend")
CA1_PORTS = {"backend": 8080, "ml-api": 8000, "db-v2": 5432}
# flyway_schema_history guarda la versión tal como va en el archivo (V001 -> "001").
EXPECTED_MIGRATIONS = ["001", "002", "003"]
CELL_COUNT = 50
REQUEST_ID = "sapi60-preflight-1"
LATEST_RANKING_SQL = REPO_ROOT / "db" / "queries" / "latest_ranking.sql"
# Salida real de POST /predict en modo reproducible (SAPI-57, forecast_time
# 2026-09-01T00:00Z): el ranking del Compose por defecto debe ser byte a byte este.
REPRODUCIBLE_FIXTURE = (
    REPO_ROOT
    / "services/backend/src/test/resources/ml/predict-reproducible-2026-09-01.json"
)
PSQL = 'psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"'

PASS = "PASS"
FAIL = "FAIL"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def redaction_pairs() -> list[tuple[str, str]]:
    """Valores locales que nunca deben quedar en la evidencia."""
    pairs = [(str(REPO_ROOT), "[repo]"), (str(Path.home()), "[home]")]
    for value, marker in ((socket.gethostname(), "[host]"), (_user(), "[user]")):
        if value and len(value) >= 3 and value != "localhost":
            pairs.append((value, marker))
    return sorted(pairs, key=lambda pair: len(pair[0]), reverse=True)


def _user() -> str:
    try:
        return getpass.getuser()
    except Exception:  # noqa: BLE001 - sin usuario resoluble no hay nada que redactar
        return ""


def redact(text: str, pairs: list[tuple[str, str]]) -> str:
    for value, marker in pairs:
        text = text.replace(value, marker)
    return text


def parse_ps(output: str) -> dict[str, dict]:
    """`docker compose ps --format json`: un arreglo o un objeto por línea."""
    output = output.strip()
    if not output:
        return {}
    if output.startswith("["):
        rows = json.loads(output)
    else:
        rows = [json.loads(line) for line in output.splitlines() if line.strip()]
    return {row["Service"]: row for row in rows}


def published_port(row: dict, target: int) -> tuple[str, int] | None:
    for publisher in row.get("Publishers") or []:
        if publisher.get("TargetPort") == target and publisher.get("PublishedPort"):
            return publisher.get("URL", ""), int(publisher["PublishedPort"])
    return None


def parse_rows(output: str) -> list[list[str]]:
    """Salida de `psql -At -F '|'`: una fila por línea."""
    return [line.split("|") for line in output.splitlines() if line.strip()]


def check_latest_ranking(
    rows: list[list[str]], expected_cells: list[str], ejecucion_id: str
):
    """Filas de latest_ranking.sql frente a la respuesta del backend.

    Columnas: 0 ejecucion_id, 5 score_semantics, 6 scientific_model_validation,
    9 cell_id, 10 score, 11 rank (de las 14 que selecciona la consulta).
    """
    problems = []
    if len(rows) != CELL_COUNT:
        problems.append(f"{len(rows)} filas, se esperaban {CELL_COUNT}")
        return problems
    if any(len(row) != 14 for row in rows):
        return ["la consulta no devolvió 14 columnas por fila"]
    if {row[0] for row in rows} != {ejecucion_id}:
        problems.append("las filas no son de la ejecución persistida por el ranking")
    if [int(row[11]) for row in rows] != list(range(1, CELL_COUNT + 1)):
        problems.append("rank no es 1..50 en orden ascendente")
    scores = [float(row[10]) for row in rows]
    if any(later > earlier for earlier, later in zip(scores, scores[1:])):
        problems.append("el score crece al avanzar el rank")
    if [row[9] for row in rows] != expected_cells:
        problems.append("el orden de cell_id difiere de la respuesta del backend")
    if {row[5] for row in rows} != {"relative_rank"} or {row[6] for row in rows} != {
        "f"
    }:
        problems.append("score_semantics / scientific_model_validation inesperados")
    return problems


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


class Preflight:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.out_dir: Path = args.out_dir
        self.pairs = redaction_pairs()
        self.checks: list[dict] = []
        self.commands: list[dict] = []
        self.ports = dict(CA1_PORTS)
        self.facts: dict = {}
        self.compose = [
            "docker",
            "compose",
            "--project-directory",
            str(REPO_ROOT),
            "-p",
            args.project_name,
        ]

    # --- infraestructura -----------------------------------------------------

    def run(
        self,
        command: list[str],
        *,
        stdin: str | None = None,
        timeout: int = 900,
        log=None,
    ):
        started = time.monotonic()
        try:
            result = subprocess.run(
                command,
                input=stdin,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                cwd=REPO_ROOT,
            )
            code, out, err = result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired as exc:
            code, out, err = 124, exc.stdout or "", f"timeout tras {timeout} s"
        except FileNotFoundError as exc:
            code, out, err = 127, "", str(exc)
        shown = redact(" ".join(command), self.pairs)
        self.commands.append(
            {
                "command": shown,
                "exit": code,
                "seconds": round(time.monotonic() - started, 1),
            }
        )
        if log:
            self.write(log, f"$ {shown}\n(exit {code})\n{out}{err}")
        return code, out, err

    def compose_run(self, *args: str, **kwargs):
        return self.run([*self.compose, *args], **kwargs)

    def psql(self, sql: str, *, unaligned: bool = True):
        flags = "-At -F '|'" if unaligned else "-P pager=off"
        return self.compose_run(
            "exec", "-T", "db-v2", "sh", "-c", f"{PSQL} {flags}", stdin=sql
        )

    def scalar(self, sql: str) -> str:
        code, out, err = self.psql(sql)
        return out.strip() if code == 0 else f"ERROR: {err.strip()[:200]}"

    def write(self, name: str, text: str) -> None:
        (self.out_dir / name).write_text(redact(text, self.pairs), encoding="utf-8")

    def check(
        self, check_id: str, ca: str, command: str, expected, observed, ok: bool
    ) -> bool:
        self.checks.append(
            {
                "id": check_id,
                "ca": ca,
                "command": redact(command, self.pairs),
                "expected": expected,
                "observed": observed,
                "status": PASS if ok else FAIL,
            }
        )
        print(f"{PASS if ok else FAIL:4}  {check_id:32} {ca}", flush=True)
        return ok

    def http(self, method: str, port: int, path: str, *, body: bytes | None = None):
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}{path}",
            data=body,
            method=method,
            headers={"X-Request-Id": REQUEST_ID, "Content-Type": "application/json"},
        )
        started = time.monotonic()
        try:
            with urllib.request.urlopen(
                request, timeout=self.args.http_timeout
            ) as response:
                status, headers, payload = (
                    response.status,
                    dict(response.headers),
                    response.read(),
                )
        except urllib.error.HTTPError as exc:
            status, headers, payload = exc.code, dict(exc.headers), exc.read()
        except (urllib.error.URLError, OSError) as exc:
            status, headers, payload = 0, {}, str(exc).encode()
        return status, headers, payload, round(time.monotonic() - started, 2)

    # --- pasos ---------------------------------------------------------------

    def environment(self) -> None:
        _, docker, _ = self.run(
            ["docker", "version", "--format", "{{.Server.Version}}"]
        )
        _, compose, _ = self.run(["docker", "compose", "version", "--short"])
        _, head, _ = self.run(["git", "rev-parse", "HEAD"])
        _, status, _ = self.run(["git", "status", "--porcelain"])
        _, ignored, _ = self.run(["git", "status", "--porcelain", "--ignored"])
        self.facts = {
            "utc": utc_now(),
            "head": head.strip(),
            "worktree_changes": len(status.splitlines()),
            "ignored_entries": sorted(
                line[3:] for line in ignored.splitlines() if line.startswith("!!")
            ),
            "docker_server": docker.strip(),
            "docker_compose": compose.strip(),
            "platform": f"{platform.system()} {platform.machine()}",
            "project": self.args.project_name,
        }

    def config(self) -> None:
        command = "docker compose config --services"
        code, out, err = self.compose_run("config", "--services")
        services = sorted(out.split()) if code == 0 else [err.strip()[:300]]
        self.check(
            "compose.config.default_services",
            "CA1",
            command,
            sorted(V2_SERVICES),
            services,
            services == sorted(V2_SERVICES),
        )

    def build(self) -> bool:
        if self.args.skip_build:
            self.facts["build"] = (
                "omitido (--skip-build): se usan las imágenes ya construidas"
            )
            return True
        code, _, _ = self.compose_run("build", timeout=3600, log="compose_build.log")
        return self.check(
            "compose.build",
            "CA6",
            "docker compose build",
            "exit 0",
            f"exit {code}",
            code == 0,
        )

    def up(self, check_id: str) -> bool:
        code, _, _ = self.compose_run(
            "up",
            "-d",
            "--wait",
            "--wait-timeout",
            "600",
            timeout=900,
            log=f"{check_id}.log",
        )
        return self.check(
            check_id,
            "CA1, CA2",
            "docker compose up -d --wait --wait-timeout 600",
            "exit 0 (todos los servicios healthy)",
            f"exit {code}",
            code == 0,
        )

    def ps(self, check_id: str) -> None:
        code, out, err = self.compose_run("ps", "--format", "json")
        rows = parse_ps(out) if code == 0 else {}
        self.write(f"{check_id}.json", out or err)
        for service in V2_SERVICES:
            row = rows.get(service, {})
            observed = {"state": row.get("State"), "health": row.get("Health")}
            self.check(
                f"{check_id}.{service}.healthy",
                "CA2",
                "docker compose ps --format json",
                {"state": "running", "health": "healthy"},
                observed,
                observed == {"state": "running", "health": "healthy"},
            )
            port = published_port(row, CA1_PORTS[service])
            if port:
                self.ports[service] = port[1]
            self.check(
                f"{check_id}.{service}.port",
                "CA1",
                "docker compose ps --format json (Publishers)",
                f"127.0.0.1:{CA1_PORTS[service]} -> {CA1_PORTS[service]}",
                f"{port[0]}:{port[1]} -> {CA1_PORTS[service]}" if port else None,
                port == ("127.0.0.1", CA1_PORTS[service]),
            )

    def health(self, check_id: str) -> None:
        status, _, payload, _ = self.http("GET", self.ports["backend"], "/health")
        body = _json(payload)
        self.check(
            f"{check_id}.backend",
            "CA2",
            f"GET http://127.0.0.1:{self.ports['backend']}/health",
            {"status_code": 200, "body": {"status": "UP"}},
            {"status_code": status, "body": body},
            status == 200 and body == {"status": "UP"},
        )
        status, _, payload, _ = self.http("GET", self.ports["ml-api"], "/health")
        body = _json(payload)
        self.check(
            f"{check_id}.ml",
            "CA2",
            f"GET http://127.0.0.1:{self.ports['ml-api']}/health",
            {"status_code": 200, "status": "ok", "model_version": "no vacío"},
            {"status_code": status, "body": body},
            status == 200
            and isinstance(body, dict)
            and body.get("status") == "ok"
            and bool(body.get("model_version")),
        )
        code, out, err = self.compose_run(
            "exec",
            "-T",
            "db-v2",
            "sh",
            "-c",
            'pg_isready -h 127.0.0.1 -p 5432 -U "$POSTGRES_USER" -d "$POSTGRES_DB"',
        )
        self.check(
            f"{check_id}.db",
            "CA2",
            "docker compose exec -T db-v2 pg_isready -h 127.0.0.1 -p 5432",
            "exit 0, accepting connections",
            f"exit {code}: {(out or err).strip()}",
            code == 0 and "accepting connections" in out,
        )

    def flyway(self, check_id: str) -> list[str]:
        sql = (
            "SELECT version || ':' || success FROM flyway_schema_history "
            "WHERE version IS NOT NULL ORDER BY installed_rank;"
        )
        code, out, err = self.psql(sql)
        history = out.split() if code == 0 else [err.strip()[:200]]
        self.check(
            check_id,
            "CA6 (Flyway del backend, ADR-008)",
            "psql: flyway_schema_history",
            [f"{version}:true" for version in EXPECTED_MIGRATIONS],
            history,
            history == [f"{version}:true" for version in EXPECTED_MIGRATIONS],
        )
        return history

    def cells(self) -> None:
        observed = self.scalar(
            "SELECT count(*) || '|' || bool_and(ST_IsValid(geom)) || '|' "
            "|| min(ST_SRID(geom)) || '|' || max(ST_SRID(geom)) FROM celdas_geom;"
        )
        self.check(
            "db.celdas_geom",
            "SAPI-59.CA2 (V003)",
            "psql: count, ST_IsValid y SRID de celdas_geom",
            "50|true|4326|4326",
            observed,
            observed == "50|true|4326|4326",
        )

    def counts(self) -> tuple[str, str]:
        return (
            self.scalar("SELECT count(*) FROM ejecuciones;"),
            self.scalar("SELECT count(*) FROM predicciones_celda;"),
        )

    def ranking(self) -> dict | None:
        status, headers, payload, seconds = self.http(
            "GET", self.ports["backend"], "/api/v1/ranking"
        )
        ranking = _json(payload)
        # Bytes tal cual (datos del servicio, sin información local): su sha256
        # es el body_sha256 registrado abajo.
        (self.out_dir / "ranking_response.json").write_bytes(payload)
        cells = ranking.get("cells", []) if isinstance(ranking, dict) else []
        observed = {
            "status_code": status,
            "x_request_id": headers.get("X-Request-Id"),
            "cells": len(cells),
            "ranks": [cell.get("rank") for cell in cells]
            == list(range(1, CELL_COUNT + 1)),
            "score_semantics": (ranking or {}).get("score_semantics"),
            "scientific_model_validation": (ranking or {}).get(
                "scientific_model_validation"
            ),
            "forecast_time": (ranking or {}).get("forecast_time"),
            "model_version": (ranking or {}).get("model_version"),
            "inputs_fingerprint": (ranking or {}).get("inputs_fingerprint"),
            "body_sha256": hashlib.sha256(payload).hexdigest(),
            "seconds": seconds,
        }
        ok = (
            status == 200
            and observed["x_request_id"] == REQUEST_ID
            and observed["cells"] == CELL_COUNT
            and observed["ranks"]
            and observed["score_semantics"] == "relative_rank"
            and observed["scientific_model_validation"] is False
        )
        self.check(
            "ranking.backend",
            "CA1 (Spring Boot -> FastAPI)",
            f"GET http://127.0.0.1:{self.ports['backend']}/api/v1/ranking",
            {
                "status_code": 200,
                "cells": CELL_COUNT,
                "ranks": "1..50",
                "score_semantics": "relative_rank",
                "scientific_model_validation": False,
            },
            observed,
            ok,
        )
        status, _, ml_payload, ml_seconds = self.http(
            "POST", self.ports["ml-api"], "/predict", body=b"{}"
        )
        ml_sha = hashlib.sha256(ml_payload).hexdigest()
        self.check(
            "ranking.passthrough",
            "SAPI-57 (mismos bytes)",
            f"POST http://127.0.0.1:{self.ports['ml-api']}/predict {{}}",
            {"status_code": 200, "body_sha256": observed["body_sha256"]},
            {"status_code": status, "body_sha256": ml_sha, "seconds": ml_seconds},
            status == 200 and ml_sha == observed["body_sha256"],
        )
        fixture_sha = hashlib.sha256(REPRODUCIBLE_FIXTURE.read_bytes()).hexdigest()
        self.check(
            "ranking.reproducible_fixture",
            "ADR-009 (modo reproducible determinista)",
            "sha256 de la respuesta vs "
            + REPRODUCIBLE_FIXTURE.relative_to(REPO_ROOT).as_posix(),
            fixture_sha,
            observed["body_sha256"],
            observed["body_sha256"] == fixture_sha,
        )
        return ranking if ok else None

    def persisted(self, ranking: dict, before: tuple[str, str]) -> str | None:
        key = (
            f"forecast_time = {sql_literal(ranking['forecast_time'])}::timestamptz "
            f"AND model_version = {sql_literal(ranking['model_version'])} "
            f"AND inputs_fingerprint = {sql_literal(ranking['inputs_fingerprint'])}"
        )
        ejecucion_id = self.scalar(f"SELECT id FROM ejecuciones WHERE {key};")
        rows = self.scalar(
            "SELECT count(*) FROM predicciones_celda "
            f"WHERE ejecucion_id = {ejecucion_id or 0};"
            if ejecucion_id.isdigit()
            else "SELECT 0;"
        )
        order = self.scalar(
            "SELECT string_agg(cell_id, ',' ORDER BY rank) FROM predicciones_celda "
            f"WHERE ejecucion_id = {ejecucion_id};"
            if ejecucion_id.isdigit()
            else "SELECT '';"
        )
        expected_order = ",".join(cell["cell_id"] for cell in ranking["cells"])
        after = self.counts()
        observed = {
            "ejecucion_id": ejecucion_id,
            "predicciones_de_la_ejecucion": rows,
            "orden_igual_a_la_respuesta": order == expected_order,
            "ejecuciones_antes_despues": [before[0], after[0]],
            "predicciones_antes_despues": [before[1], after[1]],
        }
        self.check(
            "persistence.write_through",
            "SAPI-59 en Compose (Spring Boot -> PostGIS)",
            "psql: ejecuciones / predicciones_celda por la clave natural",
            {
                "ejecucion": "existe",
                "predicciones": "50",
                "orden": "igual a la respuesta",
            },
            observed,
            ejecucion_id.isdigit() and rows == "50" and order == expected_order,
        )
        return ejecucion_id if ejecucion_id.isdigit() else None

    def idempotent(self, ranking: dict) -> None:
        before = self.counts()
        status, _, payload, _ = self.http(
            "GET", self.ports["backend"], "/api/v1/ranking"
        )
        after = self.counts()
        same = _json(payload) == ranking
        self.check(
            "persistence.idempotent_replay",
            "SAPI-59.CA4 (no duplica)",
            "GET /api/v1/ranking por segunda vez + conteos",
            {"status_code": 200, "misma_respuesta": True, "conteos": "sin cambio"},
            {
                "status_code": status,
                "misma_respuesta": same,
                "ejecuciones_antes_despues": [before[0], after[0]],
                "predicciones_antes_despues": [before[1], after[1]],
            },
            status == 200 and same and before == after,
        )

    def latest_ranking(self, ranking: dict, ejecucion_id: str) -> None:
        sql = LATEST_RANKING_SQL.read_text(encoding="utf-8")
        _, aligned, aligned_err = self.psql(sql, unaligned=False)
        self.write(
            "latest_ranking_psql.txt",
            '$ docker compose exec -T db-v2 sh -c \'psql -U "$POSTGRES_USER" '
            '-d "$POSTGRES_DB"\' < db/queries/latest_ranking.sql\n\n'
            + aligned
            + aligned_err,
        )
        code, out, err = self.psql(sql)
        rows = parse_rows(out) if code == 0 else []
        expected_cells = [cell["cell_id"] for cell in ranking["cells"]]
        problems = check_latest_ranking(rows, expected_cells, ejecucion_id)
        self.check(
            "sapi59.latest_ranking_psql",
            "SAPI-59 evidencia (psql)",
            "psql -f db/queries/latest_ranking.sql dentro de db-v2",
            "50 filas de la última ejecución, rank 1..50, mismo orden que la respuesta",
            {
                "filas": len(rows),
                "problemas": problems or (["psql: " + err] if code else []),
            },
            code == 0 and not problems,
        )

    def backend_logs(self) -> None:
        _, out, _ = self.compose_run("logs", "--no-color", "backend")
        keep = [
            line
            for line in out.splitlines()
            if "ml_predict" in line
            or "Flyway" in line
            or "Migrating schema" in line
            or "Successfully applied" in line
            or "Started BackendApplication" in line
        ]
        self.write("backend_log_excerpt.txt", "\n".join(keep) + "\n")
        migrated = any("Successfully applied 3 migrations" in line for line in keep)
        events = [line for line in keep if "ml_predict" in line]
        ranked = any(
            "outcome=ok" in line and "ml_http_status=200" in line for line in events
        )
        self.check(
            "backend.logs",
            "CA6 (Flyway) + SAPI-57.CA5",
            "docker compose logs backend",
            "Flyway aplicó 3 migraciones; ml_predict outcome=ok ml_http_status=200",
            {"flyway_3_migrations": migrated, "ml_predict_events": len(events)},
            migrated and ranked,
        )

    def restart_keeps_data(self, before: tuple[str, str], history: list[str]) -> None:
        code_down, _, _ = self.compose_run("down", log="ca4_down.log")
        ok_up = self.up("ca4.up_again")
        after = self.counts() if ok_up else ("?", "?")
        history_after = self.flyway("ca4.flyway_unchanged") if ok_up else []
        self.check(
            "ca4.data_survives_down_up",
            "CA4",
            "docker compose down (sin -v) + up -d --wait + conteos",
            {"ejecuciones": before[0], "predicciones": before[1]},
            {"down_exit": code_down, "ejecuciones": after[0], "predicciones": after[1]},
            code_down == 0 and after == before and history_after == history,
        )
        self.health("ca4.health")

    def cleanup(self) -> None:
        if self.args.keep:
            self.facts["cleanup"] = "omitido (--keep)"
            return
        if not self.args.project_name.startswith(PROJECT_PREFIX):
            self.facts["cleanup"] = "rechazado: el proyecto no es un preflight"
            return
        code, _, _ = self.compose_run(
            "down", "-v", "--remove-orphans", log="cleanup.log"
        )
        self.facts["cleanup"] = (
            f"docker compose down -v (solo {self.args.project_name}): exit {code}"
        )

    def execute(self) -> int:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.environment()
        self.config()
        try:
            if self.build() and self.up("compose.up"):
                self.ps("compose.ps")
                self.health("health")
                history = self.flyway("flyway.migrations")
                self.cells()
                before = self.counts()
                ranking = self.ranking()
                if ranking:
                    ejecucion_id = self.persisted(ranking, before)
                    self.idempotent(ranking)
                    if ejecucion_id:
                        self.latest_ranking(ranking, ejecucion_id)
                self.backend_logs()
                self.restart_keeps_data(self.counts(), history)
        finally:
            self.cleanup()
        return self.report()

    def report(self) -> int:
        verdict = (
            PASS
            if self.checks and all(c["status"] == PASS for c in self.checks)
            else FAIL
        )
        summary = {
            "tool": "scripts/compose_v2_preflight.py",
            "facts": self.facts,
            "verdict": verdict,
            "checks": self.checks,
            "commands": self.commands,
        }
        self.write(
            "preflight.json", json.dumps(summary, indent=2, ensure_ascii=False) + "\n"
        )
        print(
            f"\nPREFLIGHT {verdict}: {sum(c['status'] == PASS for c in self.checks)}"
            f"/{len(self.checks)} checks -> {redact(str(self.out_dir), self.pairs)}"
        )
        return 0 if verdict == PASS else 1


def _json(payload: bytes):
    try:
        return json.loads(payload)
    except (ValueError, UnicodeDecodeError):
        return None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--out-dir", type=Path, required=True, help="carpeta de evidencia"
    )
    parser.add_argument("--project-name", default=PROJECT_PREFIX)
    parser.add_argument(
        "--skip-build", action="store_true", help="usa imágenes ya construidas"
    )
    parser.add_argument(
        "--keep", action="store_true", help="no ejecuta down -v al final"
    )
    parser.add_argument("--http-timeout", type=int, default=180)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.project_name.startswith(PROJECT_PREFIX):
        print(f"--project-name debe empezar por {PROJECT_PREFIX}", file=sys.stderr)
        return 2
    return Preflight(args).execute()


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUTF8", "1")
    sys.exit(main())
