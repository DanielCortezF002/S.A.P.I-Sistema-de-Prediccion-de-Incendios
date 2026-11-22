"""HU-83 (SAPI-83) — Evaluación del Modelo D con datos reales.

Implementa EXACTAMENTE el protocolo de docs/preregistro_sapi83.md. Cualquier
cambio de reglas debe registrarse primero como desviación en ese documento.

Orden obligatorio de `main()` (cada paso se detiene con error si falla):
  1. Verificación de hashes SHA-256 de dataset, FIRMS, modelo desplegado y
     resultados de referencia — ANTES de leer contenido alguno.
  2. Recalcular la selección de días desde FIRMS y exigir que coincida con
     docs/dias_prueba_seleccionados.csv (commiteado antes de ejecutar).
  3. Walk-forward de scripts/experiment_abcd.py (sin modificarlo: se importan
     sus constantes y `_prep_xy`) re-entrenando el D por fold, en memoria.
  4. Control de reproducción CA4. Si no da SÍ -> `EvaluacionDetenida`: no se
     calculan umbrales, matrices ni figuras (regla de parada).
  5. Matriz por zona (Top 5 de app/utils/score_contract.py, con empates) y
     matriz por día (umbral p90 SOLO con años de entrenamiento).
  6. Curva de entrenamiento del D desplegado (solo lectura del artefacto).

El score es un ranking relativo, NO una probabilidad calibrada de incendio.

Ejecutar exige `--confirmo-autorizacion-ejecucion`: la preparación de HU-83
(22-11-2026) NO autorizó correr este script con datos reales.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Mapping, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

# ── Constantes preregistradas (docs/preregistro_sapi83.md, secciones 2-9) ─────
SHA256_DATASET = "14b36ad8db680cf57f6e0c655cb0a1940ed4b4c63e810d59e470055babc530fe"
SHA256_FIRMS = "a9a85db4431b3e54f936b724e4de5a7fbb0cc19f5721f5e1a344a192bf9bb271"
SHA256_MODELO_D = "ac017bef1f42a30ac74ba3e3787368c4418798b2d562adcfba01c923cff2173f"
# Blob en git (LF). En disco Windows puede tener CRLF -> se normaliza.
SHA256_REFERENCIA = "4bbe4db0054c4c08c08c93cfc0253201475b2fab9562ec61ccd0acc8ae04f8cd"

FIRMS_CSV = REPO_ROOT / "artifacts" / "hito1" / "reproducibility" / "firms" / "nasa_firms_2021-08-30_2026-08-30.csv"
MODELO_D_PKL = REPO_ROOT / "models" / "prototype_model_d.pkl"
REFERENCIA_JSON = REPO_ROOT / "reports" / "experiment_abcd_h6_results.json"
DIAS_CSV = REPO_ROOT / "docs" / "dias_prueba_seleccionados.csv"

ANIOS_PRUEBA = (2023, 2024, 2025, 2026)
PERIODO_INICIO = date(2023, 1, 1)
PERIODO_FIN = date(2026, 8, 29)  # último día con forecast_time en el dataset
COBERTURA_FIRMS = (date(2021, 8, 30), date(2026, 8, 30))
DIAS_FORZADOS = (date(2024, 2, 2), date(2024, 2, 3))  # comentario SAPI-83, 20-11-2026
CUOTA_POR_ANIO = 2
N_DIAS_CON_INCENDIO = 9
VENTANA_SIN_DETECCION = 3  # [c-3, c+3] sin detección en la grilla
BUSQUEDA_MAX_DIAS = 60
PERCENTIL_UMBRAL = 90
TOLERANCIA_PR_AUC = 1e-9
TOP_N_PANTALLA = 5  # debe ser igual a app.utils.score_contract.TOP_N (lo verifica un test y main)

COLUMNAS_CSV_DIAS = ["fecha", "clase", "anio", "n_celdas", "n_det", "motivo", "dia_emparejado"]


class EvaluacionDetenida(RuntimeError):
    """La evaluación se detiene: una precondición preregistrada no se cumple."""


class FugaDeUmbral(EvaluacionDetenida):
    """El umbral recibió días del año de prueba o posteriores (CA5-a)."""


# ── 1. Hashes ──────────────────────────────────────────────────────────────────
def sha256_archivo(path: Path, *, normalizar_fin_de_linea: bool = False) -> str:
    data = Path(path).read_bytes()
    if normalizar_fin_de_linea:
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class ArtefactoEsperado:
    nombre: str
    ruta: Path
    sha256: str
    normalizar_fin_de_linea: bool = False


def verificar_hashes(artefactos: Iterable[ArtefactoEsperado]) -> dict[str, str]:
    """Verifica TODOS los hashes; si alguno falta o difiere, se detiene."""
    errores, ok = [], {}
    for a in artefactos:
        if not Path(a.ruta).is_file():
            errores.append(f"{a.nombre}: no existe {a.ruta}")
            continue
        real = sha256_archivo(a.ruta, normalizar_fin_de_linea=a.normalizar_fin_de_linea)
        if real != a.sha256:
            errores.append(f"{a.nombre}: sha256 {real} != esperado {a.sha256}")
        else:
            ok[a.nombre] = real
    if errores:
        raise EvaluacionDetenida("Verificación de hashes fallida: " + "; ".join(errores))
    return ok


# ── 2. Selección de días (solo FIRMS: latitude, longitude, acq_date) ───────────
def cargar_firms_fechas(path: Path) -> pd.DataFrame:
    """Lee SOLO las columnas que usa el criterio de selección."""
    return pd.read_csv(path, usecols=["latitude", "longitude", "acq_date"])


def estadisticas_diarias_firms(fires: pd.DataFrame) -> pd.DataFrame:
    """Por fecha UTC (`acq_date`): n_celdas y n_det de detecciones EN la grilla."""
    from src.geo.grid import assign_cell

    df = fires[["latitude", "longitude", "acq_date"]].copy()
    df["cell_id"] = [assign_cell(float(la), float(lo)) for la, lo in zip(df["latitude"], df["longitude"])]
    df = df[df["cell_id"].notna()]
    if df.empty:
        return pd.DataFrame({"fecha": [], "n_celdas": [], "n_det": []})
    df["fecha"] = pd.to_datetime(df["acq_date"]).dt.date
    out = df.groupby("fecha").agg(n_celdas=("cell_id", "nunique"), n_det=("cell_id", "size")).reset_index()
    return out.sort_values("fecha").reset_index(drop=True)


def _clave_orden(row) -> tuple:
    return (-int(row["n_celdas"]), -int(row["n_det"]), row["fecha"])


def seleccionar_dias(
    stats: pd.DataFrame,
    *,
    anios=ANIOS_PRUEBA,
    periodo=(PERIODO_INICIO, PERIODO_FIN),
    cobertura=COBERTURA_FIRMS,
    forzados=DIAS_FORZADOS,
    cuota=CUOTA_POR_ANIO,
    n_total=N_DIAS_CON_INCENDIO,
    ventana=VENTANA_SIN_DETECCION,
    busqueda_max=BUSQUEDA_MAX_DIAS,
) -> pd.DataFrame:
    """Criterio de la sección 6 del preregistro. Determinista; no usa el modelo."""
    stats = stats[stats["n_celdas"] >= 1]
    fechas_con_det = set(stats["fecha"])
    info = {r["fecha"]: r for _, r in stats.iterrows()}
    candidatos = [
        r for _, r in stats.iterrows() if periodo[0] <= r["fecha"] <= periodo[1] and r["fecha"].year in anios
    ]
    candidatos.sort(key=_clave_orden)

    elegidos: dict[date, str] = {}
    for f in forzados:
        if f not in info or not (periodo[0] <= f <= periodo[1]):
            raise EvaluacionDetenida(f"Día forzado {f} no es día con incendio en la grilla según FIRMS.")
        elegidos[f] = "forzado_jira_sapi83"
    cupo_global = n_total - cuota * len(anios)
    for anio in anios:
        ya = sum(1 for f in elegidos if f.year == anio)
        disponibles = [r for r in candidatos if r["fecha"].year == anio and r["fecha"] not in elegidos]
        faltan = max(cuota - ya, 0)
        for r in disponibles[:faltan]:
            elegidos[r["fecha"]] = "cuota_anual_top2"
        cupo_global += faltan - min(faltan, len(disponibles))
    restantes = [r for r in candidatos if r["fecha"] not in elegidos]
    for r in restantes[:cupo_global]:
        elegidos[r["fecha"]] = "cupo_global"
    if len(elegidos) != n_total:
        raise EvaluacionDetenida(f"Solo hay {len(elegidos)} días con incendio elegibles; se requieren {n_total}.")

    controles: dict[date, date] = {}
    usados: set[date] = set()
    for d in sorted(elegidos):
        elegido = None
        for delta in range(1, busqueda_max + 1):
            for c in (d - timedelta(days=delta), d + timedelta(days=delta)):  # empate -> el más temprano
                if c.year != d.year or not (periodo[0] <= c <= periodo[1]) or c in usados:
                    continue
                ini, fin = c - timedelta(days=ventana), c + timedelta(days=ventana)
                if ini < cobertura[0] or fin > cobertura[1]:
                    continue
                if any((ini + timedelta(days=k)) in fechas_con_det for k in range(2 * ventana + 1)):
                    continue
                elegido = c
                break
            if elegido is not None:
                break
        if elegido is None:
            raise EvaluacionDetenida(f"No hay día sin incendio para emparejar con {d} (±{busqueda_max} días).")
        controles[d] = elegido
        usados.add(elegido)

    filas = []
    for d in sorted(elegidos):
        r = info[d]
        filas.append([d.isoformat(), "con_incendio", d.year, int(r["n_celdas"]), int(r["n_det"]), elegidos[d], controles[d].isoformat()])
        c = controles[d]
        filas.append([c.isoformat(), "sin_incendio", c.year, 0, 0, "control_emparejado", d.isoformat()])
    out = pd.DataFrame(filas, columns=COLUMNAS_CSV_DIAS)
    return out.sort_values(["fecha"]).reset_index(drop=True)


def verificar_csv_dias(commiteado: pd.DataFrame, recalculado: pd.DataFrame) -> None:
    a = commiteado[COLUMNAS_CSV_DIAS].astype(str).reset_index(drop=True)
    b = recalculado[COLUMNAS_CSV_DIAS].astype(str).reset_index(drop=True)
    if not a.equals(b):
        raise EvaluacionDetenida("docs/dias_prueba_seleccionados.csv no coincide con el criterio recalculado desde FIRMS.")


# ── 3. Walk-forward (protocolo de experiment_abcd.py, sin modificarlo) ─────────
def entrenar_fold_d(train: pd.DataFrame):
    """D del fold con el protocolo exacto; None si el guard de clase lo impide."""
    from sklearn.ensemble import HistGradientBoostingClassifier

    from scripts.experiment_abcd import MODELOS, RANDOM_STATE, _prep_xy

    x, y = _prep_xy(train, MODELOS["D"])
    min_clase = int(y.value_counts().min()) if y.nunique() >= 2 else 0
    if min_clase < 2:
        return None
    clf = HistGradientBoostingClassifier(random_state=RANDOM_STATE, max_depth=4, class_weight="balanced")
    clf.fit(x, y)
    return clf


def puntuar(clf, df: pd.DataFrame) -> np.ndarray:
    from scripts.experiment_abcd import MODELOS, _prep_xy

    x, _ = _prep_xy(df, MODELOS["D"])
    return clf.predict_proba(x)[:, 1]


# ── 4. Control de reproducción CA4 ─────────────────────────────────────────────
def control_reproduccion(
    recalculado: Mapping[str, Mapping], referencia: Mapping, *, tolerancia: float = TOLERANCIA_PR_AUC
) -> dict:
    """Compara fold a fold con la referencia. `recalculado[test_bloque]` =
    {"entrenado": bool, "pr_auc": float|None, "n_test": int, "n_positivos_test_filas": int}."""
    detalle, motivos = [], []
    folds = referencia.get("folds") or []
    if not folds:
        motivos.append("referencia sin folds")
    for f in folds:
        bloque = str(f["test_bloque"])
        ref_d = f["resultados"]["fila"].get("modelo_D", {})
        ref_entrenado = "error" not in ref_d
        rec = recalculado.get(bloque)
        fila = {"test_bloque": bloque, "pr_auc_referencia": ref_d.get("pr_auc")}
        if rec is None:
            motivos.append(f"fold {bloque} no recalculado")
            detalle.append({**fila, "ok": False})
            continue
        ok = True
        if bool(rec["entrenado"]) != ref_entrenado:
            ok = False
            motivos.append(f"fold {bloque}: entrenado={rec['entrenado']} vs referencia={ref_entrenado}")
        for k in ("n_test", "n_positivos_test_filas"):
            if int(rec[k]) != int(f[k]):
                ok = False
                motivos.append(f"fold {bloque}: {k} {rec[k]} != {f[k]}")
        if ref_entrenado:
            r, p = rec.get("pr_auc"), ref_d.get("pr_auc")
            if r is None or p is None or not np.isfinite(r) or abs(float(r) - float(p)) > tolerancia:
                ok = False
                motivos.append(f"fold {bloque}: PR-AUC {r} vs referencia {p} (tol {tolerancia})")
        detalle.append({**fila, "pr_auc_recalculada": rec.get("pr_auc"), "ok": ok})
    extra = set(recalculado) - {str(f["test_bloque"]) for f in folds}
    if extra:
        motivos.append(f"folds recalculados sin referencia: {sorted(extra)}")
    return {"resultado": "SÍ" if not motivos else "NO", "tolerancia": tolerancia, "folds": detalle, "motivos": motivos}


def exigir_reproduccion(control: Mapping) -> None:
    """Regla de parada: si CA4 no da SÍ, la evaluación no continúa."""
    if control.get("resultado") != "SÍ":
        raise EvaluacionDetenida("Control de reproducción CA4 = NO: " + "; ".join(control.get("motivos") or ["sin motivo"]))


# ── 5a. Matriz por zona — regla Top 5 de la pantalla ───────────────────────────
def ranking_pantalla(scores_por_celda: pd.Series) -> pd.DataFrame:
    """Mismo ranking que prototype_service.score_current_grid -> score_contract.

    rank único (orden de `sort_values(ascending=False)` sobre la serie en
    orden de cell_id), display_rank método "min", tie_group_size = nº de
    celdas con exactamente ese score, top5 = rank <= TOP_N.
    """
    s = pd.Series(scores_por_celda, dtype=float).sort_index()
    ranking = s.sort_values(ascending=False)
    out = pd.DataFrame({"cell_id": ranking.index, "score": ranking.to_numpy()})
    out["rank"] = np.arange(1, len(out) + 1)
    vals = out["score"].to_numpy()
    out["display_rank"] = [1 + int((vals > v).sum()) for v in vals]
    out["tie_group_size"] = [int((vals == v).sum()) for v in vals]
    out["top5"] = out["rank"] <= TOP_N_PANTALLA
    if len(out) > TOP_N_PANTALLA:
        corte = vals[TOP_N_PANTALLA - 1]
        out["en_grupo_empatado_del_corte"] = (vals == corte) & bool((vals[TOP_N_PANTALLA:] == corte).any())
    else:
        out["en_grupo_empatado_del_corte"] = False
    return out


def _cociente(a: int, b: int) -> Optional[float]:
    return None if b == 0 else a / b


def _matriz(vp: int, fp: int, fn: int, vn: int) -> dict:
    return {
        "VP": vp, "FP": fp, "FN": fn, "VN": vn,
        "precision": _cociente(vp, vp + fp),
        "sensibilidad": _cociente(vp, vp + fn),
        "especificidad": _cociente(vn, vn + fp),
    }


def matriz_zona(test: pd.DataFrame) -> dict:
    """`test`: columnas cell_id, forecast_time, target (0/1), score."""
    vp = fp = fn = vn = 0
    por_celda: dict[str, list[int]] = {}
    n_t = n_empate = n_pos_empate = n_menos_50 = 0
    for _, g in test.groupby("forecast_time", sort=True):
        n_t += 1
        if len(g) < 50:
            n_menos_50 += 1
        rk = ranking_pantalla(pd.Series(g["score"].to_numpy(), index=g["cell_id"].to_numpy()))
        y = dict(zip(g["cell_id"], g["target"].astype(int)))
        if rk["en_grupo_empatado_del_corte"].any():
            n_empate += 1
            n_pos_empate += int(sum(y[c] for c in rk.loc[rk["en_grupo_empatado_del_corte"], "cell_id"]))
        for cell, top in zip(rk["cell_id"], rk["top5"]):
            real = y[cell]
            m = por_celda.setdefault(cell, [0, 0, 0, 0])
            idx = 0 if (top and real) else 1 if top else 2 if real else 3
            m[idx] += 1
    for m in por_celda.values():
        vp, fp, fn, vn = vp + m[0], fp + m[1], fn + m[2], vn + m[3]
    return {
        "agregado": _matriz(vp, fp, fn, vn),
        "por_celda": {c: _matriz(*m) for c, m in sorted(por_celda.items())},
        "n_T": n_t,
        "n_T_empate_en_corte": n_empate,
        "n_positivos_en_grupo_empatado_del_corte": n_pos_empate,
        "n_T_con_menos_de_50_celdas": n_menos_50,
    }


# ── 5b. Matriz por día — umbral p90 solo con años de entrenamiento ─────────────
def score_por_dia(df: pd.DataFrame) -> pd.Series:
    """Máximo score por fecha UTC de forecast_time. `df`: forecast_time, score."""
    fechas = pd.to_datetime(df["forecast_time"], utc=True).dt.date
    return pd.Series(df["score"].to_numpy(), index=fechas).groupby(level=0).max().sort_index()


def umbral_p90(scores_dia_entrenamiento: pd.Series, anio_prueba: int) -> float:
    """Percentil 90 (lineal) sobre días de años de ENTRENAMIENTO solamente.

    Levanta `FugaDeUmbral` si algún día es del año de prueba o posterior.
    """
    if scores_dia_entrenamiento.empty:
        raise EvaluacionDetenida("Umbral sin días de entrenamiento.")
    anios = {pd.Timestamp(d).year for d in scores_dia_entrenamiento.index}
    if max(anios) >= anio_prueba:
        raise FugaDeUmbral(
            f"Umbral para {anio_prueba} recibió días de {sorted(a for a in anios if a >= anio_prueba)}: "
            "solo se permiten años de entrenamiento."
        )
    return float(np.percentile(scores_dia_entrenamiento.to_numpy(dtype=float), PERCENTIL_UMBRAL, method="linear"))


def matriz_dia(scores_dia: pd.Series, con_incendio: Mapping[date, bool], umbral: float) -> dict:
    vp = fp = fn = vn = 0
    no_evaluables = []
    for d, real in sorted(con_incendio.items()):
        if d not in scores_dia.index:
            no_evaluables.append(d.isoformat())
            continue
        alerta = float(scores_dia.loc[d]) >= umbral
        if alerta and real:
            vp += 1
        elif alerta:
            fp += 1
        elif real:
            fn += 1
        else:
            vn += 1
    return {**_matriz(vp, fp, fn, vn), "umbral_p90": umbral, "NO_EVALUABLE": no_evaluables}


# ── 6. Curva de entrenamiento del desplegado ───────────────────────────────────
def extraer_estimador(payload):
    """E1: `models/prototype_model_d.pkl` es un dict {"model", "metadata"}
    (igual que lo desenvuelve prototype_service._pin_model: payload["model"])."""
    if isinstance(payload, Mapping):
        if "model" not in payload:
            raise EvaluacionDetenida("El artefacto del modelo no tiene la clave 'model'.")
        return payload["model"]
    return payload


def curva_entrenamiento(modelo) -> dict:
    if isinstance(modelo, Mapping):
        raise TypeError("curva_entrenamiento recibió el dict del artefacto; usar extraer_estimador() antes (E1).")
    train = getattr(modelo, "train_score_", None)
    val = getattr(modelo, "validation_score_", None)
    if train is None or len(train) == 0:
        return {"disponible": False, "nota": "curva no disponible en el artefacto"}
    return {
        "disponible": True,
        "n_iter": int(getattr(modelo, "n_iter_", len(train) - 1)),
        "train_score": [float(v) for v in train],
        "validation_score": [float(v) for v in val] if val is not None and len(val) else None,
        "nota": "Scores internos del HistGradientBoostingClassifier (log-loss negativo por defecto); no es accuracy.",
    }


# ── main ───────────────────────────────────────────────────────────────────────
def _commit_sha() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except Exception:  # noqa: BLE001
        return "desconocido"


def _color_texto(valor: float, maximo: float) -> str:
    """E2: cifra blanca sobre celdas oscuras (más de la mitad del máximo en Blues)."""
    return "white" if maximo > 0 and valor > maximo / 2 else "black"


def _ruta_relativa(p: Path, base: Path) -> str:
    """E3: ruta relativa al directorio del JSON de resultados (`--salida`)."""
    return Path(p).resolve().relative_to(Path(base).resolve()).as_posix()


def _figuras(salida: Path, curva: dict, zona: dict, dia: dict, sello: str, base: Optional[Path] = None) -> list[str]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    base = salida.parent if base is None else base
    salida.mkdir(parents=True, exist_ok=True)
    rutas = []
    if curva.get("disponible"):
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.plot(curva["train_score"], label="entrenamiento")
        if curva.get("validation_score"):
            ax.plot(curva["validation_score"], label="validación interna")
        ax.set_xlabel("iteración")
        ax.set_ylabel("score interno (log-loss negativo)")
        ax.set_title(f"Curva de entrenamiento — Modelo D desplegado\n{sello}", fontsize=9)
        ax.legend()
        p = salida / "curva_entrenamiento_modelo_d.png"
        fig.savefig(p, dpi=150, bbox_inches="tight")
        plt.close(fig)
        rutas.append(_ruta_relativa(p, base))
    for nombre, m, etiquetas in (
        ("matriz_zona_top5_2023_2026.png", zona, ("Top 5", "fuera del Top 5")),
        ("matriz_dia_con_sin_incendio.png", dia, ("día de alerta", "día sin alerta")),
    ):
        mat = np.array([[m["VP"], m["FN"]], [m["FP"], m["VN"]]])
        fig, ax = plt.subplots(figsize=(5, 4))
        ax.imshow(mat, cmap="Blues")
        for (i, j), v in np.ndenumerate(mat):
            ax.text(j, i, str(v), ha="center", va="center", color=_color_texto(v, mat.max()))
        ax.set_xticks([0, 1], etiquetas)
        ax.set_yticks([0, 1], ["hubo detección", "no hubo"])
        ax.set_title(f"{nombre[:-4]}\n{sello}", fontsize=9)
        p = salida / nombre
        fig.savefig(p, dpi=150, bbox_inches="tight")
        plt.close(fig)
        rutas.append(_ruta_relativa(p, base))
    return rutas


def regenerar_figuras_desde_json(resultados_json: Path, salida: Path) -> list[str]:
    """E2: redibuja las figuras SOLO desde un JSON de resultados ya generado.

    No lee el dataset, no entrena ni recalcula matrices: usa los agregados y
    la curva guardados en el JSON. El sello original se conserva y se anota
    el commit y la hora de la regeneración.
    """
    r = json.loads(Path(resultados_json).read_text(encoding="utf-8"))
    sello = (
        f"{r['sello']}\nregenerada desde {Path(resultados_json).name} "
        f"(sha256 {sha256_archivo(resultados_json, normalizar_fin_de_linea=True)[:12]}) · "
        f"commit {_commit_sha()[:12]} · {datetime.now(timezone.utc).isoformat(timespec='seconds')}"
    )
    return _figuras(
        Path(salida) / "figuras_sapi83", r.get("curva_entrenamiento_desplegado") or {},
        r["zona_agregado_2023_2026"], r["dia_seleccionados_agregado_2023_2026"], sello, base=Path(salida),
    )


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dataset", type=Path, help="temporal_dataset_h6.parquet verificado (solo lectura)")
    ap.add_argument("--firms", type=Path, default=FIRMS_CSV)
    ap.add_argument("--modelo", type=Path, default=MODELO_D_PKL)
    ap.add_argument("--referencia", type=Path, default=REFERENCIA_JSON)
    ap.add_argument("--dias", type=Path, default=DIAS_CSV)
    ap.add_argument("--salida", type=Path, default=REPO_ROOT / "reports")
    ap.add_argument("--confirmo-autorizacion-ejecucion", action="store_true")
    ap.add_argument("--regenerar-figuras-desde-json", type=Path, default=None,
                    help="Solo redibuja figuras desde un JSON de resultados existente (no evalúa).")
    args = ap.parse_args(argv)
    if args.regenerar_figuras_desde_json is not None:
        if not args.confirmo_autorizacion_ejecucion:
            raise EvaluacionDetenida("Regeneración no autorizada: falta --confirmo-autorizacion-ejecucion.")
        regenerar_figuras_desde_json(args.regenerar_figuras_desde_json, args.salida)
        return 0
    if args.dataset is None:
        ap.error("--dataset es obligatorio para evaluar")
    if not args.confirmo_autorizacion_ejecucion:
        raise EvaluacionDetenida("Ejecución no autorizada: falta --confirmo-autorizacion-ejecucion.")

    from app.utils.score_contract import TOP_N

    if TOP_N != TOP_N_PANTALLA:
        raise EvaluacionDetenida(f"TOP_N de la pantalla ({TOP_N}) != preregistrado ({TOP_N_PANTALLA}).")

    # 1. Hashes antes de todo.
    hashes = verificar_hashes([
        ArtefactoEsperado("dataset", args.dataset, SHA256_DATASET),
        ArtefactoEsperado("firms", args.firms, SHA256_FIRMS),
        ArtefactoEsperado("modelo_d", args.modelo, SHA256_MODELO_D),
        ArtefactoEsperado("referencia", args.referencia, SHA256_REFERENCIA, normalizar_fin_de_linea=True),
    ])

    # 2. Días.
    stats = estadisticas_diarias_firms(cargar_firms_fechas(args.firms))
    dias = pd.read_csv(args.dias, dtype=str)
    verificar_csv_dias(dias, seleccionar_dias(stats))
    con_incendio_sel = {date.fromisoformat(f): c == "con_incendio" for f, c in zip(dias["fecha"], dias["clase"])}
    fechas_det = {d for d, n in zip(stats["fecha"], stats["n_celdas"]) if n >= 1}

    # 3. Walk-forward.
    df = pd.read_parquet(args.dataset)
    df = df[df["eligible_for_training"]].reset_index(drop=True)
    df["bloque"] = df["forecast_time"].dt.year.astype(str)
    bloques = sorted(df["bloque"].unique().tolist())
    referencia = json.loads(args.referencia.read_text(encoding="utf-8"))
    recalculado, modelos = {}, {}
    from sklearn.metrics import average_precision_score

    for i in range(1, len(bloques)):
        train = df[df["bloque"].isin(bloques[:i])]
        test = df[df["bloque"] == bloques[i]]
        clf = entrenar_fold_d(train)
        rec = {"entrenado": clf is not None, "pr_auc": None, "n_test": len(test), "n_positivos_test_filas": int(test["target"].sum())}
        if clf is not None:
            rec["pr_auc"] = float(average_precision_score(test["target"].astype(int), puntuar(clf, test)))
            modelos[bloques[i]] = clf
        recalculado[bloques[i]] = rec

    # 4. CA4 + regla de parada.
    control = control_reproduccion(recalculado, referencia)
    sello = f"commit {_commit_sha()[:12]} · {datetime.now(timezone.utc).isoformat(timespec='seconds')}"
    fecha = datetime.now(timezone.utc).strftime("%Y%m%d")
    args.salida.mkdir(parents=True, exist_ok=True)
    (args.salida / f"evaluacion_modelo_d_control_ca4_{fecha}.json").write_text(
        json.dumps({"sello": sello, "hashes": hashes, "control": control}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    exigir_reproduccion(control)

    # 5. Matrices.
    resultado = {"sello": sello, "hashes": hashes, "aviso": "Score = ranking relativo, no probabilidad calibrada.", "folds": {}}
    tot_z = [0, 0, 0, 0]
    tot_d = [0, 0, 0, 0]
    for anio in ANIOS_PRUEBA:
        b = str(anio)
        clf = modelos[b]
        train = df[df["bloque"].astype(int) < anio]
        test = df[df["bloque"] == b].copy()
        test["score"] = puntuar(clf, test)
        zona = matriz_zona(test[["cell_id", "forecast_time", "target", "score"]])
        tr = train[["forecast_time"]].copy()
        tr["score"] = puntuar(clf, train)
        tau = umbral_p90(score_por_dia(tr), anio)
        sd = score_por_dia(test[["forecast_time", "score"]])
        sel = {d: v for d, v in con_incendio_sel.items() if d.year == anio}
        dia_sel = matriz_dia(sd, sel, tau)
        dia_todos = matriz_dia(sd, {d: d in fechas_det for d in sd.index}, tau)
        resultado["folds"][b] = {"zona": zona, "dia_seleccionados": dia_sel, "dia_todos": dia_todos}
        for k, n in enumerate(("VP", "FP", "FN", "VN")):
            tot_z[k] += zona["agregado"][n]
            tot_d[k] += dia_sel[n]
    resultado["zona_agregado_2023_2026"] = _matriz(*tot_z)
    resultado["dia_seleccionados_agregado_2023_2026"] = _matriz(*tot_d)

    # 6. Curva del desplegado (solo lectura).
    import joblib

    resultado["curva_entrenamiento_desplegado"] = curva_entrenamiento(extraer_estimador(joblib.load(args.modelo)))
    resultado["figuras"] = _figuras(
        args.salida / "figuras_sapi83", resultado["curva_entrenamiento_desplegado"],
        resultado["zona_agregado_2023_2026"], resultado["dia_seleccionados_agregado_2023_2026"], sello,
        base=args.salida,
    )
    (args.salida / f"evaluacion_modelo_d_{fecha}.json").write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
