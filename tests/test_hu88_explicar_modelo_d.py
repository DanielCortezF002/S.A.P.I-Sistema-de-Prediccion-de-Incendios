"""HU-88 -- pruebas de scripts/explicar_modelo_d.py.

FIXTURES SINTETICOS: los modelos de estas pruebas se entrenan sobre datos
aleatorios generados con numpy (semilla fija). NO son datos reales de S.A.P.I.,
no representan incendios ni meteorologia, y no usan el dataset 14b36ad8.
La unica prueba que toca el artefacto real (models/prototype_model_d.pkl) lo
lee en solo lectura y se omite si el archivo no esta presente.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import HistGradientBoostingClassifier

from scripts import explicar_modelo_d as emd

SYNTH_FEATURES = ["sint_a", "sint_b", "sint_c", "sint_constante"]
SYNTH_TREES = 5


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def synthetic_artifact(tmp_path: Path) -> Path:
    """Ensamble SINTETICO pequeno (5 arboles, 4 variables), empaquetado igual que el Modelo D."""
    rng = np.random.default_rng(0)
    n = 400
    x = pd.DataFrame(
        {
            "sint_a": rng.normal(size=n),
            "sint_b": rng.normal(size=n),
            "sint_c": rng.normal(size=n),
            "sint_constante": np.zeros(n),  # constante: ningun arbol puede usarla
        }
    )
    y = (x["sint_a"] + 0.3 * x["sint_b"] > 0).astype(int)
    model = HistGradientBoostingClassifier(
        max_iter=SYNTH_TREES, max_depth=2, early_stopping=False, random_state=0
    ).fit(x, y)
    path = tmp_path / "modelo_sintetico.pkl"
    joblib.dump(
        {
            "model": model,
            "metadata": {
                "model_version": "SINTETICO_TEST",
                "feature_columns": SYNTH_FEATURES,
            },
        },
        path,
    )
    return path


def _run(path: Path, out: Path, **kw):
    params = dict(
        expected_sha256=_sha(path),
        expected_trees=SYNTH_TREES,
        expected_features=len(SYNTH_FEATURES),
        generated_at="2026-11-22T00:00:00+00:00",
    )
    params.update(kw)
    return emd.run(path, out, **params)


def test_sintetico_estructura_e_importancias(
    synthetic_artifact: Path, tmp_path: Path
) -> None:
    out = tmp_path / "out"
    payload = _run(synthetic_artifact, out)
    exp = payload["explicacion"]

    assert exp["n_arboles"] == SYNTH_TREES
    assert exp["n_variables"] == len(SYNTH_FEATURES)
    assert payload["artefacto"]["feature_columns_coinciden_con_modelo"] is True
    assert payload["scientific_model_validation"] is False
    assert payload["datos_usados"].startswith("ninguno")

    imps = exp["importancias"]
    assert sum(r["importancia_ganancia"] for r in imps) == pytest.approx(1.0)
    assert (
        imps[0]["variable"] == "sint_a"
    )  # la variable que genera la etiqueta sintetica
    assert "sint_constante" in exp["variables_no_usadas"]
    assert [r["rank"] for r in imps] == list(range(1, len(SYNTH_FEATURES) + 1))

    for t in exp["arboles"]:
        assert t["profundidad_max"] <= 2
        assert t["n_hojas"] == t["n_particiones"] + 1  # arbol binario
    assert sum(r["n_veces_en_raiz"] for r in imps) == SYNTH_TREES

    assert {p.name for p in out.iterdir()} == {emd.JSON_NAME, emd.MD_NAME, emd.SVG_NAME}
    assert (
        json.loads((out / emd.JSON_NAME).read_text(encoding="utf-8"))["verificacion"][
            "resultado"
        ]
        == "OK"
    )
    svg = (out / emd.SVG_NAME).read_text(encoding="utf-8")
    assert (
        svg.startswith("<svg") and "sint_a" in svg and f"({SYNTH_TREES} arboles)" in svg
    )


def test_ganancia_coincide_con_recorrido_manual(
    synthetic_artifact: Path, tmp_path: Path
) -> None:
    model = joblib.load(synthetic_artifact)["model"]
    manual = np.zeros(len(SYNTH_FEATURES))
    for it in model._predictors:
        for tree in it:
            nodes = tree.nodes
            internal = ~nodes["is_leaf"].astype(bool)
            np.add.at(manual, nodes["feature_idx"][internal], nodes["gain"][internal])
    exp = _run(synthetic_artifact, tmp_path / "out")["explicacion"]
    by_name = {r["variable"]: r["ganancia_total"] for r in exp["importancias"]}
    for i, name in enumerate(SYNTH_FEATURES):
        assert by_name[name] == pytest.approx(manual[i])


def test_hash_alterado_hace_fallar_sin_deserializar(
    synthetic_artifact: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _no_cargar(*_a, **_k):
        raise AssertionError("no debe deserializar un artefacto con hash distinto")

    monkeypatch.setattr(emd, "load_artifact", _no_cargar)
    real = _sha(synthetic_artifact)
    alterado = ("0" if real[0] != "0" else "1") + real[1:]
    out = tmp_path / "out"
    code = emd.main(
        [
            "--model",
            str(synthetic_artifact),
            "--out-dir",
            str(out),
            "--expected-sha256",
            alterado,
            "--expected-trees",
            str(SYNTH_TREES),
            "--expected-features",
            str(len(SYNTH_FEATURES)),
        ]
    )
    assert code == emd.EXIT_HASH_MISMATCH
    assert not out.exists()


def test_archivo_alterado_hace_fallar(synthetic_artifact: Path, tmp_path: Path) -> None:
    esperado = _sha(synthetic_artifact)
    with synthetic_artifact.open("ab") as fh:
        fh.write(b"\x00")  # altera el archivo sintetico (no el real)
    with pytest.raises(emd.ExplicacionError) as err:
        _run(synthetic_artifact, tmp_path / "out", expected_sha256=esperado)
    assert err.value.exit_code == emd.EXIT_HASH_MISMATCH


@pytest.mark.parametrize(
    ("trees", "features"),
    [(SYNTH_TREES + 1, len(SYNTH_FEATURES)), (SYNTH_TREES, len(SYNTH_FEATURES) + 1)],
)
def test_estructura_distinta_hace_fallar(
    synthetic_artifact: Path, tmp_path: Path, trees: int, features: int
) -> None:
    out = tmp_path / "out"
    with pytest.raises(emd.ExplicacionError) as err:
        _run(synthetic_artifact, out, expected_trees=trees, expected_features=features)
    assert err.value.exit_code == emd.EXIT_STRUCTURE_MISMATCH
    assert not out.exists()


def test_formato_no_soportado(tmp_path: Path) -> None:
    path = tmp_path / "no_modelo.pkl"
    joblib.dump({"model": {"no": "es un ensamble"}}, path)  # SINTETICO
    with pytest.raises(emd.ExplicacionError) as err:
        _run(path, tmp_path / "out")
    assert err.value.exit_code == emd.EXIT_UNSUPPORTED


def test_artefacto_real_22_arboles_25_variables(tmp_path: Path) -> None:
    """Lee el Modelo D real en solo lectura (sin datos). Se omite si no esta."""
    if not emd.DEFAULT_MODEL.exists():
        pytest.skip("models/prototype_model_d.pkl no presente")
    before = _sha(emd.DEFAULT_MODEL)
    assert before == emd.EXPECTED_SHA256
    payload = emd.run(
        emd.DEFAULT_MODEL, tmp_path / "out", generated_at="2026-11-22T00:00:00+00:00"
    )
    exp = payload["explicacion"]
    assert (exp["n_arboles"], exp["n_variables"]) == (22, 25)
    assert payload["artefacto"]["feature_columns_coinciden_con_modelo"] is True
    assert payload["artefacto"]["sha256_despues_de_ejecutar"] == emd.EXPECTED_SHA256
    assert _sha(emd.DEFAULT_MODEL) == before
