"""HU-88.T1 -- Explicacion estructural del Modelo D (solo lectura).

Que hace
--------
1. Calcula el SHA-256 de ``models/prototype_model_d.pkl`` y lo compara con el
   hash esperado ANTES de deserializarlo (un pickle no verificado no se carga).
2. Carga el artefacto en solo lectura (``open(..., "rb")``; no escribe, no
   reentrena, no llama ``fit``) y verifica su estructura: 22 arboles y
   25 variables. Si no coincide, falla.
3. Explica el ensamble de arboles a partir de sus propios parametros:
   importancia por ganancia de particion (suma de ``gain`` de cada variable
   sobre todos los nodos internos), numero de particiones, arboles que usan
   cada variable, variable de la raiz de cada arbol, profundidad y hojas por
   arbol.
4. Escribe en ``reports/hu88_explicacion_modelo_d/``: JSON, Markdown y una
   figura SVG de importancias.

Que NO hace
-----------
- No lee el dataset de entrenamiento (14b36ad8...) ni ningun otro dato real:
  toda la explicacion sale de la estructura del artefacto. Por eso NO hay
  importancia por permutacion ni SHAP (requeririan datos).
- No modifica ``models/``. Re-verifica el hash al final para demostrarlo.

Limitacion tecnica: el recorrido de arboles usa atributos privados de
scikit-learn 1.9.0 (``_predictors`` / ``TreePredictor.nodes``). Con otra
version de scikit-learn el script puede fallar; usar el entorno fijado en
artifacts/hito1/reproducibility/manifest.json.

Uso::

    python scripts/explicar_modelo_d.py
    python scripts/explicar_modelo_d.py --model otro.pkl --expected-sha256 <hex> \
        --expected-trees 5 --expected-features 4 --out-dir /tmp/salida

Codigos de salida: 0 ok, 2 hash distinto, 3 estructura distinta,
4 artefacto con formato no soportado, 5 artefacto modificado durante la
ejecucion.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = REPO_ROOT / "models" / "prototype_model_d.pkl"
DEFAULT_OUT_DIR = REPO_ROOT / "reports" / "hu88_explicacion_modelo_d"
EXPECTED_SHA256 = "ac017bef1f42a30ac74ba3e3787368c4418798b2d562adcfba01c923cff2173f"
EXPECTED_TREES = 22
EXPECTED_FEATURES = 25

EXIT_OK = 0
EXIT_HASH_MISMATCH = 2
EXIT_STRUCTURE_MISMATCH = 3
EXIT_UNSUPPORTED = 4
EXIT_MODIFIED = 5

JSON_NAME = "modelo_d_explicacion.json"
MD_NAME = "modelo_d_explicacion.md"
SVG_NAME = "modelo_d_importancias.svg"


class ExplicacionError(Exception):
    """Error controlado con codigo de salida asociado."""

    def __init__(self, message: str, exit_code: int) -> None:
        super().__init__(message)
        self.exit_code = exit_code


@dataclass(frozen=True)
class Artefacto:
    estimator: Any
    metadata: dict[str, Any] | None


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_hash(path: Path, expected: str) -> str:
    actual = sha256_of(path)
    if actual.lower() != expected.lower():
        raise ExplicacionError(
            f"SHA-256 no coincide para {path}: esperado {expected}, obtenido {actual}. "
            "El artefacto NO se deserializo.",
            EXIT_HASH_MISMATCH,
        )
    return actual


def load_artifact(path: Path) -> Artefacto:
    """Deserializa en solo lectura. Llamar solo despues de verify_hash."""
    import joblib

    with path.open("rb") as fh:
        obj = joblib.load(fh)
    if isinstance(obj, dict) and "model" in obj:
        meta = obj.get("metadata")
        return Artefacto(
            estimator=obj["model"], metadata=meta if isinstance(meta, dict) else None
        )
    return Artefacto(estimator=obj, metadata=None)


def _trees(estimator: Any) -> list[Any]:
    predictors = getattr(estimator, "_predictors", None)
    if predictors is None:
        raise ExplicacionError(
            f"Formato no soportado: {type(estimator).__name__} no expone _predictors "
            "(se esperaba HistGradientBoostingClassifier de scikit-learn).",
            EXIT_UNSUPPORTED,
        )
    return [tree for iteration in predictors for tree in iteration]


def feature_names(estimator: Any) -> list[str]:
    names = getattr(estimator, "feature_names_in_", None)
    if names is not None:
        return [str(n) for n in names]
    return [f"x{i}" for i in range(int(estimator.n_features_in_))]


def verify_structure(
    estimator: Any, expected_trees: int, expected_features: int
) -> None:
    n_trees = len(_trees(estimator))
    n_features = int(getattr(estimator, "n_features_in_", -1))
    problems = []
    if n_trees != expected_trees:
        problems.append(f"arboles: esperado {expected_trees}, obtenido {n_trees}")
    if n_features != expected_features:
        problems.append(
            f"variables: esperado {expected_features}, obtenido {n_features}"
        )
    if problems:
        raise ExplicacionError(
            "Estructura no coincide -- " + "; ".join(problems), EXIT_STRUCTURE_MISMATCH
        )


def _tree_depth(nodes: Any) -> int:
    """Profundidad maxima medida como numero de aristas raiz->hoja."""
    return int(nodes["depth"].max()) if len(nodes) else 0


def explain(estimator: Any) -> dict[str, Any]:
    names = feature_names(estimator)
    n_features = len(names)
    trees = _trees(estimator)

    gain = [0.0] * n_features
    n_splits = [0] * n_features
    trees_using: list[set[int]] = [set() for _ in range(n_features)]
    root_count = [0] * n_features
    thresholds: list[list[float]] = [[] for _ in range(n_features)]
    per_tree = []

    for t_idx, tree in enumerate(trees):
        nodes = tree.nodes
        internal = [i for i in range(len(nodes)) if not bool(nodes["is_leaf"][i])]
        leaves = [i for i in range(len(nodes)) if bool(nodes["is_leaf"][i])]
        tree_gain = 0.0
        for i in internal:
            f = int(nodes["feature_idx"][i])
            g = float(nodes["gain"][i])
            gain[f] += g
            tree_gain += g
            n_splits[f] += 1
            trees_using[f].add(t_idx)
            thresholds[f].append(float(nodes["num_threshold"][i]))
        root_feature = int(nodes["feature_idx"][0]) if internal else None
        if root_feature is not None:
            root_count[root_feature] += 1
        leaf_values = [float(nodes["value"][i]) for i in leaves]
        per_tree.append(
            {
                "arbol": t_idx + 1,
                "n_nodos": int(len(nodes)),
                "n_hojas": len(leaves),
                "n_particiones": len(internal),
                "profundidad_max": _tree_depth(nodes),
                "variable_raiz": (
                    names[root_feature] if root_feature is not None else None
                ),
                "ganancia_total": tree_gain,
                "valor_hoja_min": min(leaf_values) if leaf_values else None,
                "valor_hoja_max": max(leaf_values) if leaf_values else None,
                "muestras_raiz": int(nodes["count"][0]) if len(nodes) else 0,
            }
        )

    total_gain = sum(gain)
    total_splits = sum(n_splits)
    features = []
    for f, name in enumerate(names):
        features.append(
            {
                "variable": name,
                "indice": f,
                "ganancia_total": gain[f],
                "importancia_ganancia": (
                    (gain[f] / total_gain) if total_gain > 0 else 0.0
                ),
                "n_particiones": n_splits[f],
                "frecuencia_particion": (
                    (n_splits[f] / total_splits) if total_splits else 0.0
                ),
                "n_arboles_que_la_usan": len(trees_using[f]),
                "n_veces_en_raiz": root_count[f],
                "umbral_min": min(thresholds[f]) if thresholds[f] else None,
                "umbral_max": max(thresholds[f]) if thresholds[f] else None,
            }
        )
    ranking = sorted(features, key=lambda r: (-r["importancia_ganancia"], r["indice"]))
    for pos, row in enumerate(ranking, start=1):
        row["rank"] = pos

    depths = [t["profundidad_max"] for t in per_tree]
    leaves_n = [t["n_hojas"] for t in per_tree]
    params = estimator.get_params() if hasattr(estimator, "get_params") else {}
    return {
        "tipo_modelo": type(estimator).__name__,
        "n_arboles": len(trees),
        "n_iteraciones": int(getattr(estimator, "n_iter_", len(trees))),
        "n_variables": n_features,
        "clases": [int(c) for c in getattr(estimator, "classes_", [])],
        "hiperparametros": {
            k: params[k] for k in sorted(params) if _jsonable(params[k])
        },
        "parada_temprana": early_stopping_info(estimator),
        "resumen_arboles": {
            "profundidad_min": min(depths) if depths else None,
            "profundidad_max": max(depths) if depths else None,
            "hojas_min": min(leaves_n) if leaves_n else None,
            "hojas_max": max(leaves_n) if leaves_n else None,
            "hojas_total": sum(leaves_n),
            "particiones_total": total_splits,
        },
        "variables_no_usadas": [
            r["variable"] for r in features if r["n_particiones"] == 0
        ],
        "importancias": ranking,
        "arboles": per_tree,
    }


ORIGEN_DETENCION = "detención temprana"
ORIGEN_TOPE = "tope de iteraciones"
ORIGEN_INDETERMINADO = "indeterminado"


def early_stopping_info(estimator: Any) -> dict[str, Any]:
    """Por que el ensamble tiene N arboles: parametros y atributos del artefacto.

    Todo se lee del objeto ya cargado (sin datos). ``validation_score_`` es la
    puntuacion (``scoring``; con 'loss' es la log-loss negativa) sobre la
    particion de validacion interna que scikit-learn separo al entrenar; su
    indice 0 es el modelo sin arboles.
    """
    params = estimator.get_params() if hasattr(estimator, "get_params") else {}
    keys = ("early_stopping", "n_iter_no_change", "max_iter", "tol")
    keys += ("validation_fraction", "scoring")
    info: dict[str, Any] = {k: params.get(k) for k in keys}
    n_iter = getattr(estimator, "n_iter_", None)
    info["n_iter_"] = int(n_iter) if n_iter is not None else None
    do_es = getattr(estimator, "do_early_stopping_", None)
    info["do_early_stopping_"] = bool(do_es) if do_es is not None else None
    scores = getattr(estimator, "validation_score_", None)
    if scores is not None and len(scores):
        info["n_validation_score_"] = int(len(scores))
        best = max(range(len(scores)), key=lambda i: scores[i])
        info["mejor_iteracion_validacion"] = best
        info["iteraciones_sin_mejora_al_final"] = int(len(scores) - 1 - best)
    else:
        info["n_validation_score_"] = 0
        info["mejor_iteracion_validacion"] = None
        info["iteraciones_sin_mejora_al_final"] = None
    info["detenido_por_parada_temprana"] = bool(
        info["do_early_stopping_"]
        and info["n_iter_"] is not None
        and info["max_iter"] is not None
        and info["n_iter_"] < info["max_iter"]
    )
    # Origen explicito del numero de arboles. Regla: si el entrenamiento termino
    # antes de max_iter con parada temprana activa, fue la detencion temprana;
    # si llego a max_iter (este o no activa la parada temprana), fue el tope.
    if info["detenido_por_parada_temprana"]:
        info["origen_n_arboles"] = ORIGEN_DETENCION
    elif (
        info["n_iter_"] is not None
        and info["max_iter"] is not None
        and info["n_iter_"] >= info["max_iter"]
    ):
        info["origen_n_arboles"] = ORIGEN_TOPE
    else:
        info["origen_n_arboles"] = ORIGEN_INDETERMINADO
    info["nota"] = (
        "scikit-learn conserva todos los arboles construidos hasta detenerse; "
        "no descarta los posteriores a la mejor iteracion de validacion."
    )
    return info


def _jsonable(value: Any) -> bool:
    try:
        json.dumps(value)
    except TypeError:
        return False
    return True


def _versions() -> dict[str, str]:
    out = {"python": platform.python_version()}
    for mod in ("numpy", "scipy", "sklearn", "joblib"):
        try:
            out[mod] = __import__(mod).__version__
        except Exception:  # pragma: no cover - entorno incompleto
            out[mod] = "no disponible"
    return out


METODO = (
    "Importancia por ganancia: suma del campo 'gain' (reduccion de la perdida log-loss "
    "lograda por la particion, segun scikit-learn) de todos los nodos internos que usan "
    "cada variable, normalizada para sumar 1. Se calcula solo con la estructura del "
    "artefacto (sin datos). Es una medida interna del entrenamiento: no es causal, no "
    "es importancia por permutacion, y puede sobrevalorar variables continuas con "
    "muchos umbrales posibles."
)

FUENTE_IMPORTANCIA = (
    "Calculada por este script recorriendo atributos PRIVADOS de scikit-learn 1.9.0 "
    "(HistGradientBoostingClassifier._predictors y TreePredictor.nodes). No es un "
    "atributo oficial del modelo (HistGradientBoostingClassifier no expone "
    "feature_importances_) y puede romperse o cambiar con otra version de scikit-learn."
)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _texto_parada(pt: dict[str, Any]) -> str:
    base = (
        f"Parametros leidos del artefacto: early_stopping={pt['early_stopping']!r}, "
        f"n_iter_no_change={pt['n_iter_no_change']}, max_iter={pt['max_iter']}, "
        f"tol={pt['tol']}, validation_fraction={pt['validation_fraction']}, "
        f"scoring={pt['scoring']!r}; atributos: n_iter_={pt['n_iter_']}, "
        f"do_early_stopping_={pt['do_early_stopping_']}, "
        f"validation_score_ con {pt['n_validation_score_']} valores."
    )
    origen = f" Origen del numero de arboles: {pt['origen_n_arboles']}."
    if pt["origen_n_arboles"] == ORIGEN_TOPE:
        activa = "activa" if pt["do_early_stopping_"] else "inactiva"
        return (
            base
            + origen
            + (
                f" El entrenamiento llego al tope max_iter={pt['max_iter']} "
                f"(parada temprana {activa}); no se detuvo por parada temprana."
            )
        )
    if not pt["detenido_por_parada_temprana"]:
        return base + origen + " El entrenamiento no se detuvo por parada temprana."
    return (
        base
        + origen
        + (
            f" El entrenamiento se detuvo por parada temprana en la iteracion "
            f"{pt['n_iter_']} de {pt['max_iter']} posibles: la mejor puntuacion de "
            f"validacion interna se alcanzo tras {pt['mejor_iteracion_validacion']} "
            f"arboles y las {pt['iteraciones_sin_mejora_al_final']} iteraciones "
            f"siguientes no la mejoraron. {pt['nota']}"
        )
    )


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    exp = payload["explicacion"]
    art = payload["artefacto"]
    res = exp["resumen_arboles"]
    lines = [
        "# HU-88 -- Explicacion estructural del Modelo D",
        "",
        f"- Generado: {payload['generado_en']}",
        f"- Artefacto: `{art['ruta']}`",
        f"- SHA-256 verificado (antes de cargar y despues): `{art['sha256']}`",
        f"- Tipo: {exp['tipo_modelo']} -- {exp['n_arboles']} arboles, {exp['n_variables']} variables "
        f"(verificado contra lo esperado: {payload['verificacion']['arboles_esperados']} / "
        f"{payload['verificacion']['variables_esperadas']})",
        f"- Datos usados: {payload['datos_usados']}",
        "",
        "## Por que hay este numero de arboles",
        "",
        _texto_parada(exp["parada_temprana"]),
        "",
        "## Forma de los arboles",
        "",
        f"- Profundidad maxima por arbol: {res['profundidad_min']}--{res['profundidad_max']} "
        f"(hiperparametro max_depth={exp['hiperparametros'].get('max_depth')})",
        f"- Hojas por arbol: {res['hojas_min']}--{res['hojas_max']} (total {res['hojas_total']})",
        f"- Particiones totales: {res['particiones_total']}",
        f"- Variables que ningun arbol usa: {', '.join(exp['variables_no_usadas']) or 'ninguna'}",
        "",
        "## Importancia de variables (ganancia de particion)",
        "",
        METODO,
        "",
        f"Fuente del calculo: {FUENTE_IMPORTANCIA}",
        "",
        "| # | Variable | Importancia (ganancia) | Particiones | Arboles que la usan | Veces en raiz |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for r in exp["importancias"]:
        lines.append(
            f"| {r['rank']} | `{r['variable']}` | {r['importancia_ganancia'] * 100:.1f} % | "
            f"{r['n_particiones']} | {r['n_arboles_que_la_usan']} | {r['n_veces_en_raiz']} |"
        )
    lines += [
        "",
        f"Figura: `{SVG_NAME}` (misma informacion que la tabla).",
        "",
        "## Detalle por arbol",
        "",
        "| Arbol | Nodos | Hojas | Particiones | Profundidad | Variable raiz | Ganancia total |",
        "|---:|---:|---:|---:|---:|---|---:|",
    ]
    for t in exp["arboles"]:
        lines.append(
            f"| {t['arbol']} | {t['n_nodos']} | {t['n_hojas']} | {t['n_particiones']} | "
            f"{t['profundidad_max']} | `{t['variable_raiz']}` | {t['ganancia_total']:.3f} |"
        )
    lines += [
        "",
        "## Limitaciones",
        "",
        "- El score del Modelo D es un ranking relativo, no una probabilidad calibrada.",
        "- `scientific_model_validation=false`: este reporte no valida el modelo.",
        "- La importancia por ganancia describe como el modelo se ajusto a sus datos de "
        "entrenamiento; no mide causalidad ni desempeno fuera de muestra.",
        "- La importancia por ganancia y el detalle por arbol se calculan con atributos "
        "privados de scikit-learn 1.9.0 (`_predictors`); otra version puede no ser compatible.",
        "",
        f"Entorno: {', '.join(f'{k} {v}' for k, v in payload['entorno'].items())}",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_svg(
    path: Path, ranking: list[dict[str, Any]], n_trees: int, sha256: str
) -> None:
    """Barras horizontales, una serie, hue unico; <title> por barra = tooltip."""
    row_h, gap, top, left, right_pad, bar_w = 22, 6, 56, 250, 70, 360
    width = left + bar_w + right_pad
    height = top + len(ranking) * (row_h + gap) + 30
    max_v = max((r["importancia_ganancia"] for r in ranking), default=0.0) or 1.0
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="t d">',
        '<title id="t">Modelo D: importancia de variables por ganancia de particion</title>',
        '<desc id="d">Barras horizontales ordenadas de mayor a menor. Calculado solo con la '
        "estructura del artefacto, sin datos. No es causal.</desc>",
        "<style>",
        ":root{--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--grid:#e4e3df;--bar:#2a78d6}",
        "@media (prefers-color-scheme: dark){:root{--surface:#1a1a19;--ink:#f0efec;"
        "--ink2:#c3c2b7;--grid:#383835;--bar:#3987e5}}",
        "text{font-family:system-ui,-apple-system,'Segoe UI',sans-serif;font-size:12px;fill:var(--ink)}",
        ".muted{fill:var(--ink2)} .bar{fill:var(--bar)} .bar:hover{opacity:.8}",
        "</style>",
        f'<rect width="{width}" height="{height}" fill="var(--surface)"/>',
        '<text x="16" y="24" style="font-size:15px;font-weight:600">Modelo D -- importancia por ganancia</text>',
        f'<text x="16" y="42" class="muted">Proporcion de la ganancia total de particiones ({n_trees} arboles). '
        "Estructural, no causal.</text>",
        f'<line x1="{left}" y1="{top - 4}" x2="{left}" y2="{height - 26}" stroke="var(--grid)" stroke-width="1"/>',
    ]
    for i, r in enumerate(ranking):
        y = top + i * (row_h + gap)
        w = bar_w * r["importancia_ganancia"] / max_v
        pct = r["importancia_ganancia"] * 100
        label = escape(r["variable"])
        tip = escape(
            f"{r['variable']}: {pct:.1f} % de la ganancia; {r['n_particiones']} particiones; "
            f"{r['n_arboles_que_la_usan']} arboles; raiz {r['n_veces_en_raiz']} veces"
        )
        parts.append(
            f'<text x="{left - 8}" y="{y + row_h / 2 + 4}" text-anchor="end">{label}</text>'
        )
        if w > 0:
            rx = min(4.0, w / 2)
            parts.append(
                f'<rect class="bar" x="{left}" y="{y}" width="{w:.2f}" height="{row_h}" rx="{rx:.2f}">'
                f"<title>{tip}</title></rect>"
            )
        parts.append(
            f'<text x="{left + w + 6:.2f}" y="{y + row_h / 2 + 4}" class="muted">{pct:.1f} %</text>'
        )
    parts.append(
        f'<text x="16" y="{height - 8}" class="muted">Fuente: SHA-256 {escape(sha256[:12])}... '
        "artefacto -- scripts/explicar_modelo_d.py (HU-88)</text>"
    )
    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def run(
    model_path: Path,
    out_dir: Path,
    expected_sha256: str = EXPECTED_SHA256,
    expected_trees: int = EXPECTED_TREES,
    expected_features: int = EXPECTED_FEATURES,
    generated_at: str | None = None,
) -> dict[str, Any]:
    model_path = Path(model_path)
    out_dir = Path(out_dir)
    sha_before = verify_hash(model_path, expected_sha256)
    artefacto = load_artifact(model_path)
    verify_structure(artefacto.estimator, expected_trees, expected_features)
    explicacion = explain(artefacto.estimator)

    meta = artefacto.metadata or {}
    if meta.get("feature_columns") is not None:
        coincide = list(meta["feature_columns"]) == feature_names(artefacto.estimator)
    else:
        coincide = None

    sha_after = sha256_of(model_path)
    if sha_after != sha_before:
        raise ExplicacionError(
            "El artefacto cambio durante la ejecucion.", EXIT_MODIFIED
        )

    try:
        ruta = model_path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        ruta = model_path.name

    payload = {
        "hu": "HU-88",
        "generado_en": generated_at
        or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "artefacto": {
            "ruta": ruta,
            "sha256": sha_before,
            "sha256_esperado": expected_sha256,
            "sha256_despues_de_ejecutar": sha_after,
            "modo_acceso": "solo lectura (rb); sin fit ni escritura",
            "model_version": meta.get("model_version"),
            "metadata_embebida": {
                k: meta.get(k)
                for k in (
                    "status",
                    "trained_at",
                    "training_start",
                    "training_end",
                    "horizon_hours",
                    "n_training_rows",
                    "n_positive_rows",
                    "dataset_hash",
                )
                if k in meta
            },
            "feature_columns_coinciden_con_modelo": coincide,
        },
        "verificacion": {
            "arboles_esperados": expected_trees,
            "variables_esperadas": expected_features,
            "arboles_obtenidos": explicacion["n_arboles"],
            "variables_obtenidas": explicacion["n_variables"],
            "resultado": "OK",
        },
        "datos_usados": "ninguno (solo estructura del artefacto; el dataset no se lee)",
        "scientific_model_validation": False,
        "score_semantics": "relative_rank",
        "metodo_importancia": METODO,
        "fuente_importancia": FUENTE_IMPORTANCIA,
        "entorno": _versions(),
        "explicacion": explicacion,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / JSON_NAME, payload)
    write_markdown(out_dir / MD_NAME, payload)
    write_svg(
        out_dir / SVG_NAME,
        explicacion["importancias"],
        explicacion["n_arboles"],
        sha_before,
    )
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--expected-sha256", default=EXPECTED_SHA256)
    parser.add_argument("--expected-trees", type=int, default=EXPECTED_TREES)
    parser.add_argument("--expected-features", type=int, default=EXPECTED_FEATURES)
    parser.add_argument(
        "--generated-at", default=None, help="Fecha ISO fija (reproducibilidad)"
    )
    args = parser.parse_args(argv)
    try:
        payload = run(
            args.model,
            args.out_dir,
            expected_sha256=args.expected_sha256,
            expected_trees=args.expected_trees,
            expected_features=args.expected_features,
            generated_at=args.generated_at,
        )
    except ExplicacionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return exc.exit_code
    exp = payload["explicacion"]
    print(f"SHA-256 OK: {payload['artefacto']['sha256']}")
    print(f"Estructura OK: {exp['n_arboles']} arboles, {exp['n_variables']} variables")
    print(f"Origen del numero de arboles: {exp['parada_temprana']['origen_n_arboles']}")
    for r in exp["importancias"][:5]:
        print(
            f"  {r['rank']}. {r['variable']}: {r['importancia_ganancia'] * 100:.1f} %"
        )
    print(f"Salida: {Path(args.out_dir)}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
