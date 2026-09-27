"""Bounded workers executed in the candidate's isolated Python environment."""

import hashlib
import importlib
import importlib.metadata
import inspect
import json
from pathlib import Path
import subprocess
import sys


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def quality(root):
    command = [
        sys.executable,
        "-m",
        "black",
        "--check",
        "--diff",
        "src",
        "app",
        "tests",
    ]
    black = subprocess.run(
        command,
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    lint = subprocess.run(
        [
            sys.executable,
            "-m",
            "flake8",
            "src",
            "app",
            "tests",
            "--max-line-length=100",
            "--extend-ignore=E203,W503",
            "--format=%(path)s|%(row)d|%(col)d|%(code)s|%(text)s",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    if black.returncode not in (0, 1) or lint.returncode not in (0, 1):
        raise ValueError("Static analysis failed to execute")
    black_findings, files, path, changes = [], set(), None, []

    def flush():
        if changes:
            black_findings.append(path + "|" + digest("\n".join(changes)))
            changes.clear()

    for line in black.stdout.splitlines():
        if line.startswith("--- "):
            flush()
            raw = line[4:].split("\t", 1)[0]
            file = Path(raw)
            path = (
                (file if file.is_absolute() else root / file)
                .resolve()
                .relative_to(root.resolve())
                .as_posix()
            )
            files.add(path)
        elif line.startswith("@@"):
            flush()
        elif line.startswith(("+", "-")) and not line.startswith("+++ "):
            changes.append(line)
    flush()
    if black.returncode and not black_findings:
        raise ValueError("Unparsed Black output")
    flake_findings = []
    for line in lint.stdout.splitlines():
        filename, row, col, code, message = line.split("|", 4)
        file = Path(filename)
        path = (
            file.as_posix()
            if not file.is_absolute()
            else file.relative_to(root).as_posix()
        )
        source = (root / path).read_text(encoding="utf-8").splitlines()
        token = source[int(row) - 1] if int(row) <= len(source) else "EOF"
        flake_findings.append(
            path + "|" + code + "|" + digest(col + "|" + message + "|" + token)
        )
    return {
        "black": sorted(black_findings),
        "black_files": sorted(files),
        "flake8": sorted(flake_findings),
        "black_exit": black.returncode,
        "flake8_exit": lint.returncode,
        "tools": {
            tool: importlib.metadata.version(tool) for tool in ("black", "flake8")
        },
    }


def imports(root):
    sys.path.insert(0, str(root))
    names = [
        "pytest",
        "pytest_cov",
        "black",
        "flake8",
        "src.inference.prototype_service",
        "src.procesamiento.raw_parser",
    ]
    if (root / "app/control_center.py").is_file():
        names.append("app.control_center")
    return {name: bool(importlib.import_module(name)) for name in names}


def ranking(root):
    import os

    os.environ["SAPI_REPRODUCIBILITY_MODE"] = "1"
    sys.path.insert(0, str(root))
    from src.inference.prototype_service import score_current_grid

    result = score_current_grid()
    return {
        "ranking": digest(
            "\n".join(f"{c.cell_id},{c.score!r},{c.rank}" for c in result.cells)
        ),
        "cells": len(result.cells),
    }


def handshake(root, manifest):
    sys.path.insert(0, str(root))
    module = root / "src/ops/attempt2_operator/data_plane_manifest.py"
    if not module.is_file():
        return {"status": "NOT_APPLICABLE"}
    from src.ops.attempt2_operator.data_plane_manifest import verify_data_plane_manifest

    document = json.loads(manifest.read_bytes())
    kwargs = {}
    if "expected_code_sha" in inspect.signature(verify_data_plane_manifest).parameters:
        kwargs["expected_code_sha"] = (
            document.get("identity", {}).get("code_identity", {}).get("sha")
        )
    result = verify_data_plane_manifest(manifest, **kwargs)
    return {
        "status": result.get("status", "UNKNOWN"),
        "prepared": result.get("prepared"),
        "ready": result.get("ready"),
        "writers_authorized": result.get("writers_authorized"),
        "attempt2_authorized": result.get("attempt2_authorized"),
        "finding_ids": sorted(
            {f.get("id", "UNKNOWN") for f in result.get("findings", [])}
        ),
    }


if __name__ == "__main__":
    mode, location, output, *extra = sys.argv[1:]
    root = Path(location).resolve()
    try:
        result = (
            handshake(root, Path(extra[0]))
            if mode == "handshake"
            else globals()[mode](root)
        )
        Path(output).write_text(
            json.dumps(result, sort_keys=True, indent=2), encoding="utf-8"
        )
    except Exception as error:
        Path(output).write_text(
            json.dumps({"error_class": type(error).__name__}), encoding="utf-8"
        )
        raise SystemExit(1)
