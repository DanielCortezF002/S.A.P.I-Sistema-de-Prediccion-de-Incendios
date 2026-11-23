"""Pruebas HU-83 (SAPI-83) de scripts/evaluacion_modelo_d.py.

TODOS LOS DATOS DE ESTE ARCHIVO SON SINTÉTICOS (fixtures `sintetico_*`),
construidos a mano solo para ejercitar la lógica. No son observaciones, no
provienen de FIRMS, DMC ni del dataset real, y no se usa ningún dato real.

Casos negativos CA5 (deben levantar error y detener la evaluación):
  (a) umbral calculado con datos del año de prueba  -> FugaDeUmbral
  (b) resultado de reproducción alterado             -> EvaluacionDetenida
"""

from __future__ import annotations

import copy
import json
import hashlib
from pathlib import Path
from datetime import date

import numpy as np
import pandas as pd
import pytest

from scripts import evaluacion_modelo_d as ev
from src.geo.grid import all_cells

# ── Fixtures SINTÉTICAS ────────────────────────────────────────────────────────

SINTETICO_ESTADO_LIMPIO = {
    "head": "0" * 40, "git_status_porcelain": "", "sha256_script": "a" * 64, "sha256_script_lf": "a" * 64,
}
SINTETICO_ESTADO_SUCIO = {**SINTETICO_ESTADO_LIMPIO, "git_status_porcelain": " M scripts/evaluacion_modelo_d.py\n"}



@pytest.fixture
def sintetico_referencia() -> dict:
    """Referencia walk-forward SINTÉTICA con la forma de experiment_abcd_h6_results.json."""

    def fold(bloque, n_test, n_pos, pr_auc):
        fila = {"error": "train con 1 ejemplo(s)"} if pr_auc is None else {"pr_auc": pr_auc}
        return {
            "test_bloque": bloque,
            "n_test": n_test,
            "n_positivos_test_filas": n_pos,
            "resultados": {"fila": {"modelo_D": fila}},
        }

    return {
        "folds": [
            fold("2022", 100, 3, None),
            fold("2023", 110, 4, 0.0123456789),
            fold("2024", 120, 9, 0.0456),
        ]
    }


@pytest.fixture
def sintetico_recalculado_identico(sintetico_referencia) -> dict:
    out = {}
    for f in sintetico_referencia["folds"]:
        d = f["resultados"]["fila"]["modelo_D"]
        out[f["test_bloque"]] = {
            "entrenado": "error" not in d,
            "pr_auc": d.get("pr_auc"),
            "n_test": f["n_test"],
            "n_positivos_test_filas": f["n_positivos_test_filas"],
        }
    return out


@pytest.fixture
def sintetico_scores_dia_entrenamiento() -> pd.Series:
    """Scores diarios SINTÉTICOS de años de entrenamiento 2021-2022."""
    fechas = list(pd.date_range("2021-09-01", "2022-12-31", freq="D").date)
    return pd.Series(np.linspace(0.0, 1.0, len(fechas)), index=fechas)


def _sintetico_punto_en_celda(n: int) -> tuple[float, float]:
    c = all_cells()[n]
    return ((c["min_lat"] + c["max_lat"]) / 2, (c["min_lon"] + c["max_lon"]) / 2)


@pytest.fixture
def sintetico_stats_firms() -> pd.DataFrame:
    """Estadísticas diarias SINTÉTICAS (no son detecciones reales)."""
    filas = [
        (date(2024, 2, 2), 10, 40), (date(2024, 2, 3), 12, 60), (date(2024, 3, 1), 30, 90),
        (date(2023, 1, 20), 5, 9), (date(2023, 2, 10), 7, 7), (date(2023, 3, 5), 1, 1),
        (date(2025, 1, 15), 4, 4), (date(2025, 1, 16), 4, 6), (date(2025, 6, 1), 2, 2),
        (date(2026, 2, 1), 3, 3), (date(2026, 2, 20), 3, 5), (date(2026, 7, 1), 1, 1),
    ]
    return pd.DataFrame(filas, columns=["fecha", "n_celdas", "n_det"])


# ── CA5 (a): umbral con datos del año de prueba ────────────────────────────────


def test_ca5a_umbral_con_dias_del_anio_de_prueba_levanta_error(sintetico_scores_dia_entrenamiento):
    sintetico_con_fuga = pd.concat(
        [sintetico_scores_dia_entrenamiento, pd.Series([0.99], index=[date(2023, 1, 5)])]
    )
    with pytest.raises(ev.FugaDeUmbral):
        ev.umbral_p90(sintetico_con_fuga, anio_prueba=2023)


def test_ca5a_umbral_con_anio_posterior_tambien_levanta_error(sintetico_scores_dia_entrenamiento):
    sintetico_con_fuga = pd.concat(
        [sintetico_scores_dia_entrenamiento, pd.Series([0.5], index=[date(2024, 6, 1)])]
    )
    with pytest.raises(ev.FugaDeUmbral):
        ev.umbral_p90(sintetico_con_fuga, anio_prueba=2023)


def test_umbral_p90_solo_entrenamiento_es_percentil_lineal(sintetico_scores_dia_entrenamiento):
    tau = ev.umbral_p90(sintetico_scores_dia_entrenamiento, anio_prueba=2023)
    assert tau == pytest.approx(np.percentile(sintetico_scores_dia_entrenamiento.to_numpy(), 90))
    assert issubclass(ev.FugaDeUmbral, ev.EvaluacionDetenida)


# ── CA5 (b): reproducción alterada ─────────────────────────────────────────────


def test_ca4_reproduccion_identica_da_si(sintetico_referencia, sintetico_recalculado_identico):
    control = ev.control_reproduccion(sintetico_recalculado_identico, sintetico_referencia)
    assert control["resultado"] == "SÍ", control["motivos"]
    ev.exigir_reproduccion(control)  # no levanta


def test_ca5b_pr_auc_alterada_detiene_la_evaluacion(sintetico_referencia, sintetico_recalculado_identico):
    sintetico_alterado = copy.deepcopy(sintetico_recalculado_identico)
    sintetico_alterado["2023"]["pr_auc"] += 1e-6
    control = ev.control_reproduccion(sintetico_alterado, sintetico_referencia)
    assert control["resultado"] == "NO"
    with pytest.raises(ev.EvaluacionDetenida):
        ev.exigir_reproduccion(control)


def test_ca5b_referencia_alterada_detiene_la_evaluacion(sintetico_referencia, sintetico_recalculado_identico):
    sintetico_ref_alterada = copy.deepcopy(sintetico_referencia)
    sintetico_ref_alterada["folds"][2]["resultados"]["fila"]["modelo_D"]["pr_auc"] = 0.9
    with pytest.raises(ev.EvaluacionDetenida):
        ev.exigir_reproduccion(ev.control_reproduccion(sintetico_recalculado_identico, sintetico_ref_alterada))


@pytest.mark.parametrize(
    "mutacion",
    [
        lambda r: r.pop("2024"),
        lambda r: r["2023"].update(n_test=111),
        lambda r: r["2024"].update(n_positivos_test_filas=8),
        lambda r: r["2022"].update(entrenado=True, pr_auc=0.5),
        lambda r: r["2023"].update(pr_auc=None),
        lambda r: r["2023"].update(pr_auc=float("nan")),
        lambda r: r.update({"2025": {"entrenado": True, "pr_auc": 0.1, "n_test": 1, "n_positivos_test_filas": 1}}),
    ],
)
def test_ca5b_cualquier_discrepancia_de_reproduccion_detiene(mutacion, sintetico_referencia, sintetico_recalculado_identico):
    sintetico_alterado = copy.deepcopy(sintetico_recalculado_identico)
    mutacion(sintetico_alterado)
    with pytest.raises(ev.EvaluacionDetenida):
        ev.exigir_reproduccion(ev.control_reproduccion(sintetico_alterado, sintetico_referencia))


def test_reproduccion_sin_folds_detiene(sintetico_recalculado_identico):
    with pytest.raises(ev.EvaluacionDetenida):
        ev.exigir_reproduccion(ev.control_reproduccion(sintetico_recalculado_identico, {"folds": []}))


# ── Hashes antes de todo ───────────────────────────────────────────────────────


def test_hash_distinto_detiene(tmp_path):
    p = tmp_path / "sintetico_artefacto.bin"
    p.write_bytes(b"contenido sintetico")
    with pytest.raises(ev.EvaluacionDetenida):
        ev.verificar_hashes([ev.ArtefactoEsperado("sintetico", p, "0" * 64)])


def test_artefacto_faltante_detiene(tmp_path):
    with pytest.raises(ev.EvaluacionDetenida):
        ev.verificar_hashes([ev.ArtefactoEsperado("sintetico", tmp_path / "no_existe", "0" * 64)])


def test_hash_con_normalizacion_de_fin_de_linea(tmp_path):
    p = tmp_path / "sintetico_crlf.json"
    p.write_bytes(b'{"sintetico": 1}\r\n')
    esperado = hashlib.sha256(b'{"sintetico": 1}\n').hexdigest()
    assert ev.verificar_hashes([ev.ArtefactoEsperado("s", p, esperado, normalizar_fin_de_linea=True)]) == {"s": esperado}
    with pytest.raises(ev.EvaluacionDetenida):
        ev.verificar_hashes([ev.ArtefactoEsperado("s", p, esperado)])


def test_main_sin_autorizacion_no_ejecuta_nada(tmp_path):
    with pytest.raises(ev.EvaluacionDetenida, match="no autorizada"):
        ev.main(["--dataset", str(tmp_path / "sintetico_no_existe.parquet")])


def test_main_verifica_hashes_antes_de_leer(tmp_path, monkeypatch):
    sintetico = tmp_path / "sintetico_dataset.parquet"
    sintetico.write_bytes(b"no es un parquet: fixture sintetica")
    monkeypatch.setattr(ev, "estado_codigo", lambda: dict(SINTETICO_ESTADO_LIMPIO))
    monkeypatch.setattr(pd, "read_parquet", lambda *a, **k: pytest.fail("leyó el dataset antes de verificar hashes"))
    with pytest.raises(ev.EvaluacionDetenida, match="hashes"):
        ev.main(["--dataset", str(sintetico), "--salida", str(tmp_path), "--confirmo-autorizacion-ejecucion"])


# ── Regla Top 5 de la pantalla ─────────────────────────────────────────────────


def test_top_n_coincide_con_score_contract():
    from app.utils.score_contract import TOP_N

    assert ev.TOP_N_PANTALLA == TOP_N == 5


def test_ranking_pantalla_igual_a_prototype_service_y_metadatos_de_empate():
    ids = [f"VP-{i:03d}" for i in range(1, 51)]
    sintetico_scores = pd.Series([0.1] * 50, index=ids)
    sintetico_scores.iloc[[3, 7]] = [0.9, 0.8]
    sintetico_scores.iloc[[10, 11, 12, 13]] = 0.5  # grupo empatado que cruza el corte (rank 3..6)
    rk = ev.ranking_pantalla(sintetico_scores.sample(frac=1, random_state=0))
    esperado = sintetico_scores.sort_values(ascending=False)  # misma llamada de prototype_service
    assert list(rk["cell_id"]) == list(esperado.index)
    assert list(rk["rank"]) == list(range(1, 51))
    vals = rk["score"].tolist()
    for _, r in rk.iterrows():  # misma regla que score_contract.validate (tie_metadata_inconsistent)
        assert r["display_rank"] == 1 + sum(s > r["score"] for s in vals)
        assert r["tie_group_size"] == vals.count(r["score"])
    assert rk["top5"].sum() == 5
    # quicksort (default de pandas, igual que producción) no preserva el orden de los empatados
    assert sorted(rk.loc[rk["en_grupo_empatado_del_corte"], "cell_id"]) == ["VP-011", "VP-012", "VP-013", "VP-014"]


def test_ranking_sin_empate_en_corte():
    sintetico = pd.Series(np.linspace(1.0, 0.0, 50), index=[f"VP-{i:03d}" for i in range(1, 51)])
    assert not ev.ranking_pantalla(sintetico)["en_grupo_empatado_del_corte"].any()


def test_matriz_zona_cuenta_vp_fp_fn_vn_y_empates():
    ids = [f"VP-{i:03d}" for i in range(1, 51)]
    filas = []
    for t, ts in enumerate(pd.to_datetime(["2023-01-01T00:00Z", "2023-01-01T06:00Z"])):
        for k, c in enumerate(ids):
            score = 1.0 - k / 100 if t == 0 else (0.5 if k < 7 else 0.1)  # T1: 7 empatados en el corte
            filas.append({"cell_id": c, "forecast_time": ts, "target": int(k in (0, 20)), "score": score})
    sintetico_test = pd.DataFrame(filas)
    m = ev.matriz_zona(sintetico_test)
    a = m["agregado"]
    assert (a["VP"], a["FP"], a["FN"], a["VN"]) == (2, 8, 2, 88)
    assert m["n_T"] == 2 and m["n_T_empate_en_corte"] == 1 and m["n_positivos_en_grupo_empatado_del_corte"] == 1
    assert m["n_T_con_menos_de_50_celdas"] == 0
    assert a["precision"] == pytest.approx(0.2) and a["sensibilidad"] == pytest.approx(0.5)


def test_matriz_zona_registra_T_con_celdas_en_cooldown():
    sintetico = pd.DataFrame(
        {"cell_id": [f"VP-{i:03d}" for i in range(1, 41)], "forecast_time": pd.Timestamp("2023-01-01T00:00Z"),
         "target": 0, "score": np.linspace(1, 0, 40)}
    )
    assert ev.matriz_zona(sintetico)["n_T_con_menos_de_50_celdas"] == 1


# ── Matriz por día ─────────────────────────────────────────────────────────────


def test_score_por_dia_es_maximo_por_fecha_utc():
    sintetico = pd.DataFrame(
        {"forecast_time": pd.to_datetime(["2023-01-01T00:00Z", "2023-01-01T18:00Z", "2023-01-02T00:00Z"]),
         "score": [0.2, 0.7, 0.1]}
    )
    s = ev.score_por_dia(sintetico)
    assert s.to_dict() == {date(2023, 1, 1): 0.7, date(2023, 1, 2): 0.1}


def test_matriz_dia_y_no_evaluables():
    sintetico_scores = pd.Series({date(2023, 1, 1): 0.9, date(2023, 1, 2): 0.1, date(2023, 1, 3): 0.95, date(2023, 1, 4): 0.2})
    sintetico_clases = {date(2023, 1, 1): True, date(2023, 1, 2): True, date(2023, 1, 3): False,
                        date(2023, 1, 4): False, date(2023, 1, 9): True}
    m = ev.matriz_dia(sintetico_scores, sintetico_clases, umbral=0.5)
    assert (m["VP"], m["FN"], m["FP"], m["VN"]) == (1, 1, 1, 1)
    assert m["NO_EVALUABLE"] == ["2023-01-09"]
    assert m["especificidad"] == pytest.approx(0.5)


def test_cocientes_con_denominador_cero_son_none():
    m = ev.matriz_dia(pd.Series(dtype=float), {}, umbral=0.5)
    assert m["precision"] is None and m["sensibilidad"] is None and m["especificidad"] is None


# ── Selección de días (criterio sección 6) ─────────────────────────────────────


def test_estadisticas_diarias_solo_cuentan_detecciones_en_la_grilla():
    lat0, lon0 = _sintetico_punto_en_celda(0)
    lat1, lon1 = _sintetico_punto_en_celda(1)
    sintetico_firms = pd.DataFrame(
        {"latitude": [lat0, lat0, lat1, -10.0], "longitude": [lon0, lon0, lon1, -60.0],
         "acq_date": ["2023-01-05", "2023-01-05", "2023-01-05", "2023-01-06"]}
    )
    s = ev.estadisticas_diarias_firms(sintetico_firms)
    assert s.to_dict("records") == [{"fecha": date(2023, 1, 5), "n_celdas": 2, "n_det": 3}]


def test_seleccion_forzados_cuotas_y_controles(sintetico_stats_firms):
    sel = ev.seleccionar_dias(sintetico_stats_firms)
    con = sel[sel["clase"] == "con_incendio"]
    sin = sel[sel["clase"] == "sin_incendio"]
    assert len(con) == 9 and len(sin) == 9
    fechas = set(con["fecha"])
    assert {"2024-02-02", "2024-02-03"} <= fechas
    assert "2024-03-01" in fechas  # mejor restante global (30 celdas) toma el cupo 9
    assert {"2023-02-10", "2023-01-20", "2025-01-16", "2025-01-15", "2026-02-20", "2026-02-01"} <= fechas
    det = set(sintetico_stats_firms["fecha"])
    for _, r in sin.iterrows():
        c = date.fromisoformat(r["fecha"])
        d = date.fromisoformat(r["dia_emparejado"])
        assert c.year == d.year
        assert all(date.fromordinal(c.toordinal() + k) not in det for k in range(-3, 4))
    assert sin["fecha"].is_unique


def test_seleccion_control_mas_cercano_y_empate_al_mas_temprano():
    sintetico = pd.DataFrame([(date(2024, 2, 2), 1, 1), (date(2024, 2, 3), 1, 1), (date(2023, 6, 1), 1, 1),
                              (date(2023, 7, 1), 1, 1), (date(2025, 6, 1), 1, 1), (date(2025, 7, 1), 1, 1),
                              (date(2026, 6, 1), 1, 1), (date(2026, 7, 1), 1, 1), (date(2026, 7, 20), 1, 1)],
                             columns=["fecha", "n_celdas", "n_det"])
    sel = ev.seleccionar_dias(sintetico)
    par = dict(zip(sel.loc[sel["clase"] == "con_incendio", "fecha"], sel.loc[sel["clase"] == "con_incendio", "dia_emparejado"]))
    assert par["2024-02-02"] == "2024-01-29"  # d-1..d-3 y d+1..d+3 tocan 02-02/03; d-4 queda libre
    assert par["2024-02-03"] == "2024-02-07"  # d-4 (01-30) toca 02-02; d+4 libre


def test_seleccion_sin_dia_forzado_detiene(sintetico_stats_firms):
    sintetico = sintetico_stats_firms[sintetico_stats_firms["fecha"] != date(2024, 2, 3)]
    with pytest.raises(ev.EvaluacionDetenida):
        ev.seleccionar_dias(sintetico)


def test_seleccion_sin_control_posible_detiene(sintetico_stats_firms):
    sintetico_saturado = pd.concat([
        sintetico_stats_firms,
        pd.DataFrame({"fecha": list(pd.date_range("2023-01-01", "2023-12-31").date), "n_celdas": 1, "n_det": 1}),
    ]).drop_duplicates("fecha")
    with pytest.raises(ev.EvaluacionDetenida, match="emparejar"):
        ev.seleccionar_dias(sintetico_saturado)


def test_seleccion_con_menos_de_9_candidatos_detiene():
    sintetico = pd.DataFrame([(date(2024, 2, 2), 1, 1), (date(2024, 2, 3), 1, 1)], columns=["fecha", "n_celdas", "n_det"])
    with pytest.raises(ev.EvaluacionDetenida):
        ev.seleccionar_dias(sintetico)


def test_csv_de_dias_alterado_detiene(sintetico_stats_firms):
    sel = ev.seleccionar_dias(sintetico_stats_firms)
    ev.verificar_csv_dias(sel.astype(str), sel)  # idéntico: no levanta
    sintetico_alterado = sel.copy()
    sintetico_alterado.loc[0, "fecha"] = "2023-12-31"
    with pytest.raises(ev.EvaluacionDetenida):
        ev.verificar_csv_dias(sintetico_alterado, sel)


# ── Protocolo de experiment_abcd.py ────────────────────────────────────────────


def test_fold_con_un_positivo_no_se_entrena_como_en_experiment_abcd():
    from scripts.experiment_abcd import FEATURES_D

    sintetico_train = pd.DataFrame(np.zeros((20, len(FEATURES_D))), columns=FEATURES_D)
    sintetico_train["target"] = [1] + [0] * 19
    assert ev.entrenar_fold_d(sintetico_train) is None


def test_curva_no_disponible_no_se_inventa():
    class SinteticoModeloSinCurva:
        pass

    assert ev.curva_entrenamiento(SinteticoModeloSinCurva())["disponible"] is False


# ── Integración: main() con CA4 = NO se detiene antes de las matrices ──────────
# Condición 1 del Auditor (ola1-parte5, 22-11-2026). TODO es SINTÉTICO: FIRMS,
# dataset, "modelo" y referencia se fabrican en tmp_path solo para esta prueba.
# No se entrena ningún modelo: `entrenar_fold_d` se sustituye por un
# clasificador sintético de score fijo.

_SINTETICO_FECHAS_FIRMS = [
    "2023-01-20", "2023-02-10", "2024-02-02", "2024-02-03", "2024-03-01",
    "2025-01-15", "2025-01-16", "2026-02-01", "2026-02-20",
]


class _SinteticoClasificador:
    """Clasificador SINTÉTICO: score determinista, sin entrenamiento."""

    def predict_proba(self, x):
        p = np.linspace(0.1, 0.9, len(x))
        return np.column_stack([1 - p, p])


def _sintetico_artefactos_main(tmp_path):
    from scripts.experiment_abcd import FEATURES_D

    lat, lon = _sintetico_punto_en_celda(0)
    firms = tmp_path / "sintetico_firms.csv"
    pd.DataFrame({"latitude": lat, "longitude": lon, "acq_date": _SINTETICO_FECHAS_FIRMS}).to_csv(firms, index=False)
    dias = tmp_path / "sintetico_dias.csv"
    ev.seleccionar_dias(ev.estadisticas_diarias_firms(ev.cargar_firms_fechas(firms))).to_csv(dias, index=False)

    filas = []
    for anio in range(2021, 2027):
        for k, ts in enumerate(pd.to_datetime([f"{anio}-02-02T00:00Z", f"{anio}-02-02T06:00Z"])):
            for j, cell in enumerate(("VP-001", "VP-002", "VP-003")):
                filas.append({"forecast_time": ts, "cell_id": cell, "eligible_for_training": True,
                              "target": int(k == 0 and j == 0), **{f: 0.0 for f in FEATURES_D}})
    dataset = tmp_path / "sintetico_dataset.parquet"
    pd.DataFrame(filas).to_parquet(dataset)

    modelo = tmp_path / "sintetico_modelo.pkl"
    modelo.write_bytes(b"modelo sintetico: no se carga si CA4 = NO")

    # Referencia SINTÉTICA con conteos correctos pero PR-AUC alterada -> CA4 = NO.
    referencia = tmp_path / "sintetico_referencia.json"
    referencia.write_text(json.dumps({"folds": [
        {"test_bloque": str(a), "n_test": 6, "n_positivos_test_filas": 1,
         "resultados": {"fila": {"modelo_D": {"pr_auc": 0.123456}}}}
        for a in range(2022, 2027)
    ]}), encoding="utf-8")
    return {"dataset": dataset, "firms": firms, "modelo": modelo, "referencia": referencia, "dias": dias}


def test_main_con_ca4_no_se_detiene_antes_de_matrices_y_figuras(tmp_path, monkeypatch):
    a = _sintetico_artefactos_main(tmp_path)
    for const, clave in (("SHA256_DATASET", "dataset"), ("SHA256_FIRMS", "firms"),
                         ("SHA256_MODELO_D", "modelo"), ("SHA256_REFERENCIA", "referencia")):
        monkeypatch.setattr(ev, const, ev.sha256_archivo(a[clave], normalizar_fin_de_linea=clave == "referencia"))
    monkeypatch.setattr(ev, "entrenar_fold_d", lambda train: _SinteticoClasificador())
    monkeypatch.setattr(ev, "estado_codigo", lambda: dict(SINTETICO_ESTADO_LIMPIO))

    llamadas = []
    for nombre in ("matriz_zona", "matriz_dia", "umbral_p90", "score_por_dia", "curva_entrenamiento", "_figuras"):
        monkeypatch.setattr(ev, nombre, lambda *args, _n=nombre, **kw: llamadas.append(_n))

    salida = tmp_path / "sintetico_salida"
    with pytest.raises(ev.EvaluacionDetenida, match="CA4 = NO"):
        ev.main([
            "--dataset", str(a["dataset"]), "--firms", str(a["firms"]), "--modelo", str(a["modelo"]),
            "--referencia", str(a["referencia"]), "--dias", str(a["dias"]), "--salida", str(salida),
            "--confirmo-autorizacion-ejecucion",
        ])

    assert llamadas == [], f"main() siguió después de CA4 = NO: {llamadas}"
    controles = list(salida.glob("evaluacion_modelo_d_control_ca4_*.json"))
    assert len(controles) == 1
    control = json.loads(controles[0].read_text(encoding="utf-8"))["control"]
    assert control["resultado"] == "NO" and control["motivos"]
    assert all("PR-AUC" in m for m in control["motivos"])
    escritos = {p.name for p in salida.iterdir()}
    assert escritos == {controles[0].name}, f"se escribieron salidas además del control: {escritos}"
    assert not (salida / "figuras_sapi83").exists()


# ── Defectos E1–E3 detectados en la ejecución R2–R6 (22-11-2026) ──────────────
# Fixtures SINTÉTICAS: ni el pkl real ni el JSON real de resultados se leen.


class _SinteticoEstimadorConCurva:
    """Estimador SINTÉTICO con los atributos que deja HistGradientBoostingClassifier."""

    train_score_ = np.array([-0.70, -0.40, -0.30])
    validation_score_ = np.array([-0.71, -0.45, -0.38])
    n_iter_ = 2


def test_e1_curva_rechaza_el_dict_entero_del_artefacto():
    sintetico_payload = {"model": _SinteticoEstimadorConCurva(), "metadata": {"sintetico": True}}
    with pytest.raises(TypeError, match="extraer_estimador"):
        ev.curva_entrenamiento(sintetico_payload)


def test_e1_extraer_estimador_desenvuelve_el_dict_como_produccion():
    sintetico_payload = {"model": _SinteticoEstimadorConCurva(), "metadata": {"sintetico": True}}
    curva = ev.curva_entrenamiento(ev.extraer_estimador(sintetico_payload))
    assert curva["disponible"] is True and curva["n_iter"] == 2
    assert curva["train_score"] == [-0.70, -0.40, -0.30]
    assert curva["validation_score"] == [-0.71, -0.45, -0.38]


def test_e1_artefacto_sin_clave_model_detiene():
    with pytest.raises(ev.EvaluacionDetenida):
        ev.extraer_estimador({"metadata": {"sintetico": True}})


def test_e2_cifra_de_celda_oscura_en_blanco():
    sintetico_vn, sintetico_fp = 239738, 26643
    assert ev._color_texto(sintetico_vn, sintetico_vn) == "white"
    assert ev._color_texto(sintetico_fp, sintetico_vn) == "black"
    assert ev._color_texto(0, 0) == "black"


def _sintetico_folds_empates() -> dict:
    """Conteos de empate SINTÉTICOS (no son los de la ejecución real)."""
    return {
        "2023": {"zona": {"n_T": 10, "n_T_empate_en_corte": 8, "n_positivos_en_grupo_empatado_del_corte": 1}},
        "2024": {"zona": {"n_T": 20, "n_T_empate_en_corte": 5, "n_positivos_en_grupo_empatado_del_corte": 2}},
    }


def _sintetico_json_resultados(tmp_path):
    m = {"VP": 1, "FP": 2, "FN": 3, "VN": 400, "precision": None, "sensibilidad": None, "especificidad": None}
    p = tmp_path / "sintetico_resultados.json"
    p.write_text(json.dumps({
        "sello": "SINTETICO commit 000000000000",
        "zona_agregado_2023_2026": m,
        "dia_seleccionados_agregado_2023_2026": m,
        "curva_entrenamiento_desplegado": ev.curva_entrenamiento(_SinteticoEstimadorConCurva()),
        "folds": _sintetico_folds_empates(),
    }), encoding="utf-8")
    return p


def test_e2_regenerar_figuras_desde_json_no_recalcula(tmp_path, monkeypatch):
    for nombre in ("matriz_zona", "matriz_dia", "umbral_p90", "score_por_dia", "entrenar_fold_d", "puntuar"):
        monkeypatch.setattr(ev, nombre, lambda *a, _n=nombre, **k: pytest.fail(f"{_n} no debe llamarse"))
    monkeypatch.setattr(pd, "read_parquet", lambda *a, **k: pytest.fail("no debe leer dataset"))
    salida = tmp_path / "sintetico_salida"
    rutas = ev.regenerar_figuras_desde_json(_sintetico_json_resultados(tmp_path), salida)
    assert rutas == [
        "figuras_sapi83/curva_entrenamiento_modelo_d.png",
        "figuras_sapi83/matriz_zona_top5_2023_2026.png",
        "figuras_sapi83/matriz_dia_con_sin_incendio.png",
    ]
    assert all((salida / r).is_file() for r in rutas)


def test_e2_modo_regenerar_por_cli_exige_autorizacion(tmp_path):
    with pytest.raises(ev.EvaluacionDetenida, match="no autorizada"):
        ev.main(["--regenerar-figuras-desde-json", str(_sintetico_json_resultados(tmp_path)), "--salida", str(tmp_path)])


def test_e3_rutas_de_figuras_son_relativas_al_json(tmp_path):
    m = {"VP": 0, "FP": 1, "FN": 0, "VN": 9}
    rutas = ev._figuras(tmp_path / "figuras_sapi83", {"disponible": False}, m, m, "SINTETICO", base=tmp_path,
                        nota_zona="nota SINTETICA")
    assert rutas == ["figuras_sapi83/matriz_zona_top5_2023_2026.png", "figuras_sapi83/matriz_dia_con_sin_incendio.png"]
    assert not any(Path(r).is_absolute() or "\\" in r for r in rutas)


# ── --solo-curva-ca1, M-1 (estado del código) y M-2 (empates) ──────────────────
# Fixtures SINTÉTICAS: el pkl es un joblib de un estimador sintético en tmp_path.


class SinteticoEstimadorSinCurva:
    """Estimador SINTÉTICO sin train_score_ (picklable: nivel de módulo)."""


def _sintetico_pkl(tmp_path, monkeypatch) -> Path:
    import joblib

    pkl = tmp_path / "sintetico_modelo.pkl"
    joblib.dump({"model": _SinteticoEstimadorConCurva(), "metadata": {"sintetico": True}}, pkl)
    monkeypatch.setattr(ev, "SHA256_MODELO_D", ev.sha256_archivo(pkl))
    return pkl


def _prohibir_datos_y_evaluacion(monkeypatch):
    monkeypatch.setattr(pd, "read_parquet", lambda *a, **k: pytest.fail("abrió el dataset"))
    for nombre in ("cargar_firms_fechas", "control_reproduccion", "entrenar_fold_d", "matriz_zona", "matriz_dia",
                   "umbral_p90", "regenerar_figuras_desde_json"):
        monkeypatch.setattr(ev, nombre, lambda *a, _n=nombre, **k: pytest.fail(f"{_n} no debe llamarse"))


def _cli_solo_curva(pkl, salida):
    return ["--solo-curva-ca1", "--modelo", str(pkl), "--salida", str(salida), "--confirmo-autorizacion-ejecucion"]


def test_solo_curva_genera_curva_y_json_con_rutas_relativas_sin_abrir_dataset(tmp_path, monkeypatch):
    pkl = _sintetico_pkl(tmp_path, monkeypatch)
    _prohibir_datos_y_evaluacion(monkeypatch)
    monkeypatch.setattr(ev, "estado_codigo", lambda: dict(SINTETICO_ESTADO_LIMPIO))
    salida = tmp_path / "sintetico_curva_nueva"
    assert ev.main(_cli_solo_curva(pkl, salida)) == 0
    r = json.loads((salida / "curva_ca1.json").read_text(encoding="utf-8"))
    assert r["modo"] == "solo_curva_ca1" and r["figuras"] == ["curva_entrenamiento_modelo_d.png"]
    assert r["curva_entrenamiento_desplegado"]["n_iter"] == 2
    assert r["estado_codigo"] == SINTETICO_ESTADO_LIMPIO
    assert sorted(x.name for x in salida.iterdir()) == ["curva_ca1.json", "curva_entrenamiento_modelo_d.png"]


def test_solo_curva_no_toca_los_json_existentes(tmp_path, monkeypatch):
    pkl = _sintetico_pkl(tmp_path, monkeypatch)
    monkeypatch.setattr(ev, "estado_codigo", lambda: dict(SINTETICO_ESTADO_LIMPIO))
    reportes = tmp_path / "sintetico_reports"
    reportes.mkdir()
    existentes = {
        reportes / "evaluacion_modelo_d_20261122.json": '{"sintetico": "resultados"}',
        reportes / "evaluacion_modelo_d_control_ca4_20261122.json": '{"sintetico": "control"}',
    }
    for ruta, texto in existentes.items():
        ruta.write_text(texto, encoding="utf-8")
    antes = {r: ev.sha256_archivo(r) for r in existentes}
    ev.main(_cli_solo_curva(pkl, reportes / "sapi83" / "curva_ca1_sintetica"))
    assert {r: ev.sha256_archivo(r) for r in existentes} == antes


def test_solo_curva_falla_si_el_destino_existe(tmp_path, monkeypatch):
    pkl = _sintetico_pkl(tmp_path, monkeypatch)
    monkeypatch.setattr(ev, "estado_codigo", lambda: dict(SINTETICO_ESTADO_LIMPIO))
    salida = tmp_path / "sintetico_existente"
    salida.mkdir()
    (salida / "previo.txt").write_text("sintetico", encoding="utf-8")
    with pytest.raises(ev.EvaluacionDetenida, match="ya existe"):
        ev.main(_cli_solo_curva(pkl, salida))
    assert [x.name for x in salida.iterdir()] == ["previo.txt"]


def test_solo_curva_falla_con_hash_de_pkl_alterado_antes_de_cargarlo(tmp_path, monkeypatch):
    import joblib

    pkl = _sintetico_pkl(tmp_path, monkeypatch)
    monkeypatch.setattr(ev, "SHA256_MODELO_D", "0" * 64)
    monkeypatch.setattr(ev, "estado_codigo", lambda: dict(SINTETICO_ESTADO_LIMPIO))
    monkeypatch.setattr(joblib, "load", lambda *a, **k: pytest.fail("cargó el pkl sin verificar el hash"))
    salida = tmp_path / "sintetico_no_creado"
    with pytest.raises(ev.EvaluacionDetenida, match="hashes"):
        ev.main(_cli_solo_curva(pkl, salida))
    assert not salida.exists()


def test_solo_curva_exige_autorizacion(tmp_path, monkeypatch):
    pkl = _sintetico_pkl(tmp_path, monkeypatch)
    with pytest.raises(ev.EvaluacionDetenida, match="no autorizada"):
        ev.main(["--solo-curva-ca1", "--modelo", str(pkl), "--salida", str(tmp_path / "x")])


def test_solo_curva_sin_curva_en_el_artefacto_no_inventa(tmp_path, monkeypatch):
    import joblib

    pkl = tmp_path / "sintetico_sin_curva.pkl"
    joblib.dump({"model": SinteticoEstimadorSinCurva(), "metadata": {}}, pkl)
    monkeypatch.setattr(ev, "SHA256_MODELO_D", ev.sha256_archivo(pkl))
    with pytest.raises(ev.EvaluacionDetenida, match="no se inventa"):
        ev.solo_curva_ca1(pkl, tmp_path / "sintetico_salida")
    assert not (tmp_path / "sintetico_salida").exists()


def test_m1_arbol_sucio_detiene_solo_curva_sin_escribir(tmp_path, monkeypatch, capsys):
    pkl = _sintetico_pkl(tmp_path, monkeypatch)
    monkeypatch.setattr(ev, "estado_codigo", lambda: dict(SINTETICO_ESTADO_SUCIO))
    salida = tmp_path / "sintetico_no_creado"
    with pytest.raises(ev.EvaluacionDetenida, match="no limpio"):
        ev.main(_cli_solo_curva(pkl, salida))
    assert not salida.exists()
    log = capsys.readouterr().out
    assert "[estado_codigo]" in log and "scripts/evaluacion_modelo_d.py" in log and "sha256_script" in log


def test_m1_arbol_sucio_detiene_main_antes_de_hashes(tmp_path, monkeypatch):
    monkeypatch.setattr(ev, "estado_codigo", lambda: dict(SINTETICO_ESTADO_SUCIO))
    monkeypatch.setattr(ev, "verificar_hashes", lambda *a, **k: pytest.fail("siguió con árbol sucio"))
    with pytest.raises(ev.EvaluacionDetenida, match="no limpio"):
        ev.main(["--dataset", str(tmp_path / "sintetico.parquet"), "--salida", str(tmp_path),
                 "--confirmo-autorizacion-ejecucion"])


def test_m1_arbol_limpio_registra_estado_en_el_log(capsys):
    ev.exigir_arbol_limpio(SINTETICO_ESTADO_LIMPIO)
    log = capsys.readouterr().out
    assert log.startswith("[estado_codigo] ")
    registrado = json.loads(log[len("[estado_codigo] "):])
    assert registrado["git_status_porcelain"] == "" and registrado["sha256_script"] == "a" * 64


def test_m1_estado_codigo_incluye_porcelain_y_hash_del_script():
    estado = ev.estado_codigo()  # lee git del repo; no toca datos
    assert set(estado) == {"head", "git_status_porcelain", "sha256_script", "sha256_script_lf"}
    assert estado["sha256_script"] == ev.sha256_archivo(Path(ev.__file__))


def test_m2_nota_de_empates_con_totales_y_por_anio():
    nota = ev.nota_empates_zona(_sintetico_folds_empates())
    assert "13/30 (43.3 %)" in nota
    assert "2023 8/10 (80.0 %)" in nota and "2024 5/20 (25.0 %)" in nota
    assert "grupo empatado del corte: 3" in nota


def test_m2_matriz_zona_no_se_presenta_sin_empates(tmp_path):
    p = tmp_path / "sintetico_sin_folds.json"
    m = {"VP": 1, "FP": 2, "FN": 3, "VN": 4}
    p.write_text(json.dumps({"sello": "SINTETICO", "zona_agregado_2023_2026": m,
                             "dia_seleccionados_agregado_2023_2026": m}), encoding="utf-8")
    with pytest.raises(ev.EvaluacionDetenida, match="M-2"):
        ev.regenerar_figuras_desde_json(p, tmp_path / "sintetico_salida")


def test_m2_figura_zona_lleva_la_nota(tmp_path, monkeypatch):
    import matplotlib.figure

    textos = []
    original = matplotlib.figure.Figure.text
    monkeypatch.setattr(matplotlib.figure.Figure, "text",
                        lambda self, *a, **k: textos.append(a[2]) or original(self, *a, **k))
    m = {"VP": 0, "FP": 1, "FN": 0, "VN": 9}
    ev._figuras(tmp_path / "f", {"disponible": False}, m, dict(m), "SINTETICO", base=tmp_path, nota_zona="NOTA SINTETICA")
    assert textos == ["NOTA SINTETICA"]
