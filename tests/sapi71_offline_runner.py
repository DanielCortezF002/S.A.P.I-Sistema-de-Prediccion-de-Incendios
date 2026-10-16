"""Offline Block A runner; use python -I -B tests/sapi71_offline_runner.py GROUP OUT.

Groups are separate processes. No inherited PYTHONPATH, pytest plugins, shared
conftest (legacy SMOTE fixture), coverage writes, .env, or provider credentials.
This runner performs synthetic refreshes only. It does not run freeze_check.
"""
from __future__ import annotations

import contextlib
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
GROUPS = {
    "pass": "test_refresh_adversarial.py",
    "red": "test_remediation_red_defects.py",
    "adv05": "test_adv05_characterization.py",
}


def main():
    group, destination = sys.argv[1:]
    if group not in GROUPS or not sys.flags.isolated or not sys.dont_write_bytecode:
        raise SystemExit("Require -I -B and group pass/red/adv05")
    out = Path(destination).resolve()
    out.mkdir(parents=True, exist_ok=True)
    retained = {k: os.environ[k] for k in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP")
                if k in os.environ}
    os.environ.clear()
    os.environ.update(retained)
    os.environ.update(PYTHON_DOTENV_DISABLED="1", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
                      PYTHONDONTWRITEBYTECODE="1")
    sys.path[:] = [p for p in sys.path if p and (
        "site-packages" not in p.lower()
        or Path(p).resolve().is_relative_to(Path(sys.prefix))
    )]
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "tests"))

    def refuse(*_args, **_kwargs):
        raise AssertionError("red deshabilitada por runner offline SAPI-71")

    for name in ("connect", "connect_ex", "sendto"):
        setattr(socket.socket, name, refuse)
    for name in ("create_connection", "getaddrinfo", "gethostbyname", "gethostbyname_ex"):
        setattr(socket, name, refuse)

    def audit(event, args):
        if event in {"socket.connect", "socket.getaddrinfo", "socket.gethostbyname",
                     "socket.gethostbyaddr", "socket.sendto", "subprocess.Popen",
                     "os.system"}:
            refuse()
        if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
            name = os.fsdecode(args[0])
            if Path(name).name == ".env" or Path(name).name.startswith(".env."):
                raise AssertionError("Lectura .env prohibida en runner offline")

    sys.addaudithook(audit)
    import dotenv
    dotenv.load_dotenv = lambda *_a, **_k: False
    import pytest

    class Results:
        def __init__(self):
            self.reports = []
            self.collection = []

        def pytest_runtest_logreport(self, report):
            self.reports.append({"nodeid": report.nodeid, "phase": report.when,
                                 "outcome": report.outcome, "duration": report.duration,
                                 "failure": str(report.longrepr) if report.failed else None})

        def pytest_collectreport(self, report):
            if report.failed:
                self.collection.append(str(report.longrepr))

    results = Results()
    temp = tempfile.mkdtemp(prefix="sapi71-" + group + "-")
    args = [str(ROOT / "tests" / GROUPS[group]), "-c", str(ROOT / "pytest.ini"),
            "--noconftest", "-o", "addopts=", "-p", "no:cacheprovider",
            "--basetemp", str(Path(temp) / "pytest"), "-vv", "--tb=long", "--color=no"]
    manifest = {
        "utc": datetime.now(timezone.utc).isoformat(), "group": group,
        "python": sys.executable, "version": sys.version, "prefix": sys.prefix,
        "base_prefix": sys.base_prefix, "cwd": str(Path.cwd()), "args": args,
        "isolated": sys.flags.isolated, "bytecode_disabled": sys.dont_write_bytecode,
        "dotenv_disabled": True, "environment_cleared": True,
        "network_guard_before_pytest_import": True, "sys_path": sys.path,
        "conftest_excluded_reason": "Only unrelated legacy FeatureEngineer fixtures; local fixtures used",
        "packages": sorted(f"{d.metadata['Name']}=={d.version}"
                           for d in importlib.metadata.distributions()),
        "sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in sorted((ROOT / "tests").glob("*"))
                   if p.name in {*GROUPS.values(), "sapi71_offline_runner.py"}},
        "capture_body_source_sha256": hashlib.sha256(
            (ROOT / "src/inference/prototype_service.py").read_bytes()).hexdigest(),
    }
    with (out / f"{group}.log").open("w", encoding="utf-8") as log:
        with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            print(json.dumps(manifest, indent=2))
            code = int(pytest.main(args, plugins=[results]))
            print("PYTEST_EXIT_CODE", code)
    manifest["loaded_product_modules"] = {
        name: str(Path(module.__file__).resolve())
        for name, module in sorted(sys.modules.items())
        if name.startswith("src.") and getattr(module, "__file__", None)
    }
    manifest.update(exit_code=code, reports=results.reports, collection_errors=results.collection)
    (out / f"{group}.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(group, "exit", code, "log", out / f"{group}.log")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
