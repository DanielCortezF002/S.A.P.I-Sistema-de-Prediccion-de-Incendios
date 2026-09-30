"""Excepción humana auditable a MW-011 (SECRET_DETECTED por NOMBRE de archivo).

Cubre exclusivamente el mecanismo de waiver: sin excepción, MW-011 sigue
bloqueando exactamente como antes; con una excepción válida (mismo
finding_id, mismo path, mismo sha256 del blob commiteado, actor y motivo),
solo ESE hallazgo queda ACKNOWLEDGED y el resto del plan se sigue evaluando
normalmente. No usa datos reales ni stores no sintéticos.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import src.ops.operational_workspace as ow
from src.ops.operational_workspace import (
    FindingWaiver,
    WorkspaceRequest,
    load_waivers,
    materialize,
    plan,
)

GIT = [
    "git",
    "-c",
    "user.name=t",
    "-c",
    "user.email=t@example.invalid",
    "-c",
    "commit.gpgsign=false",
    "-c",
    "core.autocrlf=false",
]

# Contenido deliberadamente SIN secreto real; sirve también como marcador
# único para probar que nunca se imprime/registra el contenido del archivo.
CREDENTIALS_SOURCE = (
    "# Marker-unico-de-contenido-nunca-debe-aparecer-en-hallazgos-o-manifest\n"
    "def collect_credentials_presence():\n"
    '    return {"present": False}\n'
)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        [*GIT, "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def _write(path: Path, data: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def _no_store_overrides(monkeypatch):
    for name in ("DATA_RAW_DIR", "DATA_PROCESSED_DIR", "DATA_PREDICTIONS_DIR", "MODELS_DIR"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def repo_with_credentials_file(tmp_path):
    """Repo git mínimo con un único commit que incluye un archivo cuyo NOMBRE
    dispara MW-011 (`credentials.py`), sin secreto real en su contenido."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run([*GIT, "init", "-q", str(repo)], check=True)
    _write(repo / "src/collectors/credentials.py", CREDENTIALS_SOURCE)
    _write(repo / "src/app.py", "print('ok')\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "c1")
    sha = _git(repo, "rev-parse", "HEAD")
    stores = {}
    for name in ("raw", "processed", "models"):
        d = tmp_path / f"store_{name}"
        d.mkdir()
        stores[name] = d
    return {
        "repo": repo,
        "sha": sha,
        "path": "src/collectors/credentials.py",
        "stores": stores,
        "dest": tmp_path / "canonical",
    }


def _req(ctx: dict, *, sha: str | None = None, waivers=()) -> WorkspaceRequest:
    return WorkspaceRequest(
        repo_root=ctx["repo"],
        code_sha=sha or ctx["sha"],
        source_stores=ctx["stores"],
        destination=ctx["dest"],
        margin_bytes=0,
        waivers=waivers,
        environ={},
    )


def _mw011(result: dict) -> dict:
    hits = [f for f in result["findings"] if f["id"] == "MW-011"]
    assert len(hits) == 1, result["findings"]
    return hits[0]


def _real_blob_sha256(ctx: dict) -> str:
    digest = ow._blob_sha256(str(ctx["repo"]), ctx["sha"], ctx["path"])
    assert digest is not None
    return digest


# 1. Sin excepción, MW-011 sigue bloqueando.
def test_mw011_blocks_without_waiver(repo_with_credentials_file):
    result = plan(_req(repo_with_credentials_file))
    assert result["overall_status"] == "FAIL"
    finding = _mw011(result)
    assert "waived" not in finding
    assert result["waivers_applied"] == []


# 2. Excepción correcta (finding + path + hash exactos) permite continuar.
def test_valid_waiver_acknowledges_only_that_finding(repo_with_credentials_file):
    ctx = repo_with_credentials_file
    digest = _real_blob_sha256(ctx)
    waiver = FindingWaiver(
        finding_id="MW-011",
        path=ctx["path"],
        sha256=digest,
        actor="Daniel",
        reason="Revisado manualmente: colector sin secreto embebido.",
    )
    result = plan(_req(ctx, waivers=(waiver,)))
    assert result["overall_status"] == "PASS"
    finding = _mw011(result)
    assert finding["waived"]["actor"] == "Daniel"
    assert finding["severity"] == "FAIL"  # el hallazgo crudo nunca se reescribe
    assert len(result["waivers_applied"]) == 1
    assert result["waivers_applied"][0]["path"] == ctx["path"]

    # End-to-end: materialize también respeta la excepción (segundo scan, en staging).
    req = _req(ctx, waivers=(waiver,))
    plan_id = plan(req)["plan_id"]
    mat = materialize(req, confirm_plan_id=plan_id)
    assert mat["overall_status"] == "PASS", mat
    assert mat["promotion_status"] == "PROMOTED"
    assert len(mat["waivers_applied"]) == 1


# 3. Hash incorrecto -> bloquea.
def test_wrong_hash_still_blocks(repo_with_credentials_file):
    ctx = repo_with_credentials_file
    waiver = FindingWaiver(
        finding_id="MW-011",
        path=ctx["path"],
        sha256="0" * 64,
        actor="Daniel",
        reason="hash equivocado a propósito",
    )
    result = plan(_req(ctx, waivers=(waiver,)))
    assert result["overall_status"] == "FAIL"
    assert "waived" not in _mw011(result)
    assert result["waivers_applied"] == []


# 4. Path incorrecto -> bloquea.
def test_wrong_path_still_blocks(repo_with_credentials_file):
    ctx = repo_with_credentials_file
    digest = _real_blob_sha256(ctx)
    waiver = FindingWaiver(
        finding_id="MW-011",
        path="src/collectors/OTRO.py",
        sha256=digest,
        actor="Daniel",
        reason="path equivocado a propósito",
    )
    result = plan(_req(ctx, waivers=(waiver,)))
    assert result["overall_status"] == "FAIL"
    assert "waived" not in _mw011(result)


# 5. Finding distinto -> bloquea (el mecanismo solo acepta MW-011 al cargar,
# y una excepción de MW-011 nunca afecta un finding de otro id).
def test_non_mw011_finding_id_rejected_at_load(repo_with_credentials_file):
    with pytest.raises(ValueError):
        FindingWaiver.from_dict(
            {
                "finding_id": "MW-002",
                "path": "irrelevante",
                "sha256": "a" * 64,
                "actor": "Daniel",
                "reason": "intento de ampliar el alcance",
            }
        )


def test_other_findings_not_waived_by_mw011_waiver(repo_with_credentials_file, tmp_path):
    ctx = repo_with_credentials_file
    digest = _real_blob_sha256(ctx)
    waiver = FindingWaiver("MW-011", ctx["path"], digest, "Daniel", "ok")
    # Store obligatorio no declarado -> MW-018, no debe verse afectado.
    stores = dict(ctx["stores"])
    del stores["models"]
    req = WorkspaceRequest(
        repo_root=ctx["repo"],
        code_sha=ctx["sha"],
        source_stores=stores,
        destination=ctx["dest"],
        margin_bytes=0,
        waivers=(waiver,),
        environ={},
    )
    result = plan(req)
    assert result["overall_status"] == "FAIL"
    ids = {f["id"] for f in result["findings"]}
    assert "MW-018" in ids
    mw018 = next(f for f in result["findings"] if f["id"] == "MW-018")
    assert "waived" not in mw018


# 6. Modificar el archivo después invalida la excepción.
def test_file_change_invalidates_waiver(repo_with_credentials_file):
    ctx = repo_with_credentials_file
    digest = _real_blob_sha256(ctx)
    waiver = FindingWaiver("MW-011", ctx["path"], digest, "Daniel", "ok")

    _write(ctx["repo"] / ctx["path"], CREDENTIALS_SOURCE + "\n# cambio\n")
    _git(ctx["repo"], "commit", "-qam", "c2")
    new_sha = _git(ctx["repo"], "rev-parse", "HEAD")

    result = plan(_req(ctx, sha=new_sha, waivers=(waiver,)))
    assert result["overall_status"] == "FAIL"
    assert "waived" not in _mw011(result)
    assert result["waivers_applied"] == []


# 7. La excepción aplicada queda registrada en el manifiesto de materialización.
def test_waiver_recorded_in_manifest(repo_with_credentials_file):
    ctx = repo_with_credentials_file
    digest = _real_blob_sha256(ctx)
    waiver = FindingWaiver("MW-011", ctx["path"], digest, "Daniel", "Revisión manual OK")
    req = _req(ctx, waivers=(waiver,))
    plan_id = plan(req)["plan_id"]
    mat = materialize(req, confirm_plan_id=plan_id)
    assert mat["promotion_status"] == "PROMOTED"
    manifest_path = Path(mat["destination"]) / ow.MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["waivers_applied"] == [
        {
            "finding_id": "MW-011",
            "path": ctx["path"],
            "sha256": digest,
            "actor": "Daniel",
            "reason": "Revisión manual OK",
        }
    ]


# 8. Nunca se imprime/registra contenido sensible del archivo.
def test_no_file_content_leaks_into_findings_or_manifest(repo_with_credentials_file):
    ctx = repo_with_credentials_file
    digest = _real_blob_sha256(ctx)
    waiver = FindingWaiver("MW-011", ctx["path"], digest, "Daniel", "ok")
    req = _req(ctx, waivers=(waiver,))
    plan_result = plan(req)
    mat = materialize(req, confirm_plan_id=plan_result["plan_id"])
    marker = "Marker-unico-de-contenido-nunca-debe-aparecer-en-hallazgos-o-manifest"
    assert marker not in json.dumps(plan_result)
    assert marker not in json.dumps(mat, default=str)
    manifest_path = Path(mat["destination"]) / ow.MANIFEST_NAME
    assert marker not in manifest_path.read_text(encoding="utf-8")


def test_load_waivers_from_file(tmp_path, repo_with_credentials_file):
    ctx = repo_with_credentials_file
    digest = _real_blob_sha256(ctx)
    waiver_file = tmp_path / "waivers.json"
    waiver_file.write_text(
        json.dumps(
            [
                {
                    "finding_id": "MW-011",
                    "path": ctx["path"],
                    "sha256": digest,
                    "actor": "Daniel",
                    "reason": "via --waiver-file",
                }
            ]
        ),
        encoding="utf-8",
    )
    waivers = load_waivers(str(waiver_file))
    assert len(waivers) == 1
    result = plan(_req(ctx, waivers=waivers))
    assert result["overall_status"] == "PASS"


def test_load_waivers_none_path_returns_empty():
    assert load_waivers(None) == ()
