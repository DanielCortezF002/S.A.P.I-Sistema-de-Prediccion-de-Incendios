"""SAPI-66: owned Compose + real browser + HTTP/SQL evidence.

Uses only the frozen reproducibility snapshot. No operational refresh.
Run with Python (PyYAML, jsonschema) and Node (playwright; Edge or Chromium).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
import traceback
import urllib.error
import urllib.request
from datetime import datetime

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
SERVICES = {"db-v2", "ml-api", "backend", "web-v2"}


def http(method, url, body=None):
    request = urllib.request.Request(url, method=method,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    start = time.monotonic()
    try:
        response = opener.open(request, timeout=90)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        payload = response.read()
        return response.code, payload, time.monotonic() - start


def resolve(node, root):
    if isinstance(node, dict):
        if "$ref" in node:
            ref = node["$ref"]
            if not ref.startswith("#/"):
                raise ValueError("Unexpected external schema reference")
            target = root
            for part in ref[2:].split("/"):
                target = target[part]
            return resolve(target, root)
        return {k: resolve(v, root) for k, v in node.items()}
    if isinstance(node, list):
        return [resolve(x, root) for x in node]
    return node


def compare_rows(rows, ranking):
    """Compare all persisted fields, including scores and ties, not just cell IDs."""
    def instant(s):
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    if len(rows) != 50 or len(ranking["cells"]) != 50:
        return False
    for row, cell in zip(rows, ranking["cells"]):
        if len(row) != 14:
            return False
        if not (instant(row[1]) == instant(ranking["forecast_time"])
            and row[2:6] == [ranking[k] for k in
                ("model_version", "inputs_fingerprint", "schema_version", "score_semantics")]
            and row[6] == "f" and ranking["scientific_model_validation"] is False
            and (int(row[7]) if row[7] else None) == ranking.get("horizon_hours")
            and row[9] == cell["cell_id"] and float(row[10]) == cell["score"]
            and [int(x) for x in row[11:14]] ==
                [cell[k] for k in ("rank", "display_rank", "tie_group_size")]):
            return False
    return len({row[0] for row in rows}) == 1


class Runner:
    def __init__(self, args):
        self.args = args
        self.project = args.project_name
        self.out = Path(args.out_dir).resolve()
        self.out.mkdir(parents=True, exist_ok=False)
        self.owned = False
        self.checks, self.timings, self.facts = [], [], {}
        self.password = secrets.token_hex(24)
        self.env_file = self.out / "compose.env"
        self.env_file.write_text("# Empty: never load a local .env\n")
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith(("SAPI_", "COMPOSE_", "POSTGRES_"))}
        self.env.update({"SAPI_DB_PASSWORD": self.password, "SAPI_DB_USER": "sapi",
                         "SAPI_DB_NAME": "sapi_v2"})
        for key in ("backend", "ml", "db", "web"):
            self.env[f"SAPI_{key.upper()}_PORT"] = str(getattr(args, key + "_port"))
        self.backend = f"http://127.0.0.1:{args.backend_port}"
        self.ml = f"http://127.0.0.1:{args.ml_port}"
        self.web = f"http://127.0.0.1:{args.web_port}"

    def save(self, name, value):
        text = value if isinstance(value, str) else json.dumps(value, indent=2)
        text = text.replace(self.password, "[redacted]").replace(str(Path.home()), "[home]")
        (self.out / name).write_text(text, encoding="utf-8")

    def check(self, name, passed, ca, detail=None):
        self.checks.append(dict(name=name, passed=bool(passed), ca=ca, detail=detail))
        print(f"{'PASS' if passed else 'FAIL'} {name}", flush=True)
        if not passed:
            raise RuntimeError(name)

    def compose(self, *args, sql=None, timeout=180):
        result = subprocess.run(["docker", "compose", "--env-file", str(self.env_file),
            "--project-name", self.project, *args], cwd=ROOT, env=self.env,
            input=sql, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout)
        if result.returncode:
            self.save("compose-error.log", result.stdout + result.stderr)
            raise RuntimeError(f"Compose failed: {args}; see compose-error.log")
        return result.stdout + (result.stderr if args[0] == "--profile" else "")

    def sql(self, query):
        return self.compose("exec", "-T", "db-v2", "psql", "-U", "sapi", "-d",
            "sapi_v2", "-v", "ON_ERROR_STOP=1", "-At", "-F", "|", sql=query).strip()

    def counts(self):
        return self.sql("SELECT (SELECT count(*) FROM ejecuciones),"
                        "(SELECT count(*) FROM predicciones_celda);")

    def start(self):
        for kind in ("container", "volume", "network"):
            result = subprocess.run(["docker", kind, "ls", "-q", "--filter",
                f"label=com.docker.compose.project={self.project}"],
                capture_output=True, text=True, check=True)
            if result.stdout.strip():
                raise RuntimeError(f"Refusing to adopt existing {kind} resources")
        self.owned = True
        self.save("build.log", self.compose("--profile", "presentation", "up",
            "--build", "-d", "--wait", timeout=1800))
        raw = self.compose("ps", "--format", "json").strip()
        rows = json.loads(raw) if raw.startswith("[") else [json.loads(x) for x in raw.splitlines()]
        self.save("compose_ps.json", rows)
        services = {r["Service"]: r for r in rows}
        self.check("exact_services", set(services) == SERVICES, "CA5")
        for name, row in services.items():
            self.check("health." + name, row["State"] == "running" and
                (name == "web-v2" or row["Health"] == "healthy"), "CA5")
        status, body, _ = http("GET", self.backend + "/health")
        self.check("backend.UP", status == 200 and json.loads(body)["status"] == "UP", "CA5")
        # Inspect only image IDs, never container environment (credentials).
        ids = self.compose("ps", "-q").split()
        self.facts["image_ids"] = subprocess.run(
            ["docker", "inspect", "--format", "{{.Name}} {{.Image}}", *ids],
            capture_output=True, text=True, check=True).stdout.splitlines()

    def browser(self, scenario):
        result = subprocess.run([self.args.node, str(ROOT / "scripts/e2e_browser.cjs"),
            self.web, str(self.out), scenario], capture_output=True, text=True,
            encoding="utf-8", timeout=240)
        self.save(f"browser-{scenario}.log", result.stdout + result.stderr)
        self.check("browser." + scenario, result.returncode == 0,
                   "CA1" if scenario == "ranking" else "CA2")
        evidence = json.loads((self.out / f"browser-{scenario}.json").read_text(encoding="utf-8"))
        if scenario == "ranking":
            self.timings.append(dict(hop="browser-render", sample="first_browser_session",
                seconds=evidence["seconds"], status=200))
        return evidence

    def contracts(self):
        spec = yaml.safe_load((ROOT / "contracts/openapi/ml-service.v0.yaml").read_text(encoding="utf-8"))
        backend = yaml.safe_load((ROOT / "contracts/openapi/backend.v0.yaml").read_text(encoding="utf-8"))
        self.check("backend.contract.reference", backend["paths"]["/api/v1/ranking"]["get"]
            ["responses"]["200"]["content"]["application/json"]["schema"]["$ref"] ==
            "./ml-service.v0.yaml#/components/schemas/RankingResult", "CA2")
        for name, method, url, data, expected, schema in [
            ("backend", "GET", self.backend + "/api/v1/ranking", None, 200, "RankingResult"),
            ("ml", "POST", self.ml + "/predict", {}, 200, "RankingResult"),
            ("backend.invalid", "GET", self.backend + "/api/v1/ranking?forecast_time=bad", None, 422, "Error"),
            ("ml.invalid", "POST", self.ml + "/predict", {"invalid": True}, 422, "Error")]:
            status, raw, _ = http(method, url, data)
            self.check(name + ".status", status == expected, "CA2")
            payload = json.loads(raw)
            jsonschema.validate(payload, resolve(spec["components"]["schemas"][schema], spec))
            self.check(name + ".schema", True, "CA2")
            if name == "backend":
                self.ranking = payload
                self.save("ranking.json", payload)
        # Exercise actual downstream failure, not a mocked HTTP response.
        self.compose("stop", "ml-api")
        try:
            status, raw, _ = http("GET", self.backend + "/api/v1/ranking")
            jsonschema.validate(json.loads(raw), resolve(spec["components"]["schemas"]["Error"], spec))
            self.check("ml.down.fail_closed", status in (503, 504) and self.counts() == "1|50", "CA2",
                {"http_status": status, "error_type": json.loads(raw).get("error_type")})
        finally:
            self.compose("up", "-d", "--wait", "ml-api")
        self.compose("stop", "backend")
        # Restart this test-only web container to invalidate the server-side cache.
        self.compose("restart", "web-v2")
        try:
            self.browser("down")
        finally:
            self.compose("up", "-d", "--wait", "backend")
        self.compose("restart", "web-v2")
        self.browser("recovery")

    def persistence(self):
        raw = self.sql((ROOT / "db/queries/latest_ranking.sql").read_text(encoding="utf-8"))
        self.save("latest_ranking_psql.txt", raw)
        self.check("sql.exact_http_ranking", compare_rows([x.split("|") for x in raw.splitlines()], self.ranking), "CA3")
        self.check("counts.before_replay", self.counts() == "1|50", "CA3")
        status, raw, _ = http("GET", self.backend + "/api/v1/ranking")
        replay = json.loads(raw)
        self.check("replay.same_cells", status == 200 and replay["cells"] == self.ranking["cells"], "CA3")
        self.check("counts.after_replay", self.counts() == "1|50", "CA3")
        spatial = self.sql("SELECT count(*), count(*) FILTER (WHERE ST_IsValid(geom) AND "
            "ST_SRID(geom)=4326 AND ST_GeometryType(geom)='ST_Polygon') FROM celdas_geom cg "
            "JOIN predicciones_celda pc USING(cell_id) WHERE pc.ejecucion_id="
            "(SELECT id FROM ejecuciones ORDER BY created_at DESC,id DESC LIMIT 1);")
        self.check("postgis.geometry", spatial == "50|50", "CA3")

    def run(self):
        completed = False
        try:
            self.facts = {"head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                capture_output=True, text=True, check=True).stdout.strip(),
                "python": sys.version, "project": self.project,
                "data_scope": "frozen snapshot; NOT operational CURRENT",
                "source_sha256": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
                    for p in ("scripts/e2e_slice.py", "scripts/e2e_browser.cjs", "docker-compose.yml",
                              "Dockerfile.ml-api", "Dockerfile.web", "services/backend/Dockerfile")}}
            self.start()
            self.check("database.initially_empty", self.counts() == "0|0", "CA1")
            browser = self.browser("ranking")
            self.check("browser.persisted_execution", self.counts() == "1|50", "CA1")
            self.contracts()
            self.check("browser.same_fingerprint", self.ranking["inputs_fingerprint"] in browser["text"], "CA1")
            self.check("browser.same_cells", browser["cell_ids"] == [c["cell_id"] for c in self.ranking["cells"]], "CA1")
            self.persistence()
            for hop, method, url, body in [("backend", "GET", self.backend + "/api/v1/ranking", None),
                    ("ml", "POST", self.ml + "/predict", {})]:
                for sample in range(1, 3):
                    status, _, elapsed = http(method, url, body)
                    self.check(f"timing.{hop}.{sample}", status == 200, "CA4")
                    self.timings.append(dict(hop=hop, sample=sample, seconds=elapsed, status=status))
            self.check("total_browser_time.recorded", browser["seconds"] > 0, "CA4")
            completed = True
        except Exception:
            self.save("execution-error.txt", traceback.format_exc())
            self.checks.append(dict(name="runner.exception", ca="RUN", passed=False))
        finally:
            if self.owned and not self.args.keep:
                try:
                    self.compose("--profile", "presentation", "down", "-v")
                except Exception:
                    self.save("cleanup-error.txt", traceback.format_exc())
                    self.checks.append(dict(name="cleanup", ca="RUN", passed=False))
            passed = completed and all(c["passed"] for c in self.checks)
            self.save("e2e_report.json", dict(facts=self.facts, completed=completed,
                verdict="PASS" if passed else "FAIL", checks=self.checks, timings=self.timings))
            with (self.out / "timings.csv").open("w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["hop", "sample", "seconds", "status"])
                writer.writeheader()
                writer.writerows(self.timings)
        return 0 if passed else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", required=True, help="New evidence directory (must not exist)")
    parser.add_argument("--project-name", default="sapi66-" + secrets.token_hex(6))
    for name, port in [("backend", 28080), ("ml", 28000), ("db", 25432), ("web", 28501)]:
        parser.add_argument("--" + name + "-port", type=int, default=port)
    parser.add_argument("--node", default="node")
    parser.add_argument("--keep", action="store_true")
    return Runner(parser.parse_args()).run()


if __name__ == "__main__":
    sys.exit(main())
