"""Exploración R-ETIQUETA-01 (ver docs/matriz-riesgo.md) — NO es entrenamiento
de producción. Investiga si la regla sintética de ignición (30-30-30)
coincide con detecciones satelitales reales confirmadas de feb-2025, y qué
tan bien un modelo distingue esas detecciones reales del clima "normal" de
la misma estación/mes, con una muestra exploratoria de n=12.

Requiere que ya exista, generado por el join real (SAPI-28/32):
  - data/processed/fires_meteo_join_2025-02_clean.parquet
    (o data/processed/feb2025_cleaned_verification.parquet, mismo contrato)
  - data/raw/dmc_historico_330007_2025-02.json

Salida: reports/exploratorio_r_etiqueta_01_resultados.csv
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

from src.procesamiento.raw_parser import parse_dmc_json

FEATURES = ["temperatura", "humedad_relativa", "velocidad_viento_kmh"]
DMC_HISTORICO_PATH = Path("data/raw/dmc_historico_330007_2025-02.json")
JOIN_CANDIDATES = [
    Path("data/processed/fires_meteo_join_2025-02_clean.parquet"),
    Path("data/processed/feb2025_cleaned_verification.parquet"),
]
OUT_PATH = Path("reports/exploratorio_r_etiqueta_01_resultados.csv")
DISTANCIA_MAX_KM = 30.0
VENTANA_EXCLUSION_MIN = 60
NEGATIVOS_TEST_SIZE = 0.2
RANDOM_STATE = 42


def _load_joined() -> pd.DataFrame:
    for path in JOIN_CANDIDATES:
        if path.exists():
            return pd.read_parquet(path)
    raise FileNotFoundError(
        "No se encontró el parquet del join ignición-meteo. Correr "
        "meteo_fire_joiner.join_fires_to_meteo() sobre feb-2025 primero."
    )


def build_positivos_y_negativos() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Positivos: detecciones satelitales reales <=30km de la estación DMC.
    Negativos: resto de lecturas DMC de feb-2025, excluyendo una ventana de
    +-60min alrededor de cada positivo (evita casi-duplicados por cercanía
    temporal directa a un incendio real).
    """
    joined = _load_joined()
    positivos = joined[joined["distancia_estacion_km"] <= DISTANCIA_MAX_KM].copy()
    positivos = positivos.sort_values("ignition_ts").reset_index(drop=True)

    meteo = parse_dmc_json(DMC_HISTORICO_PATH)
    meteo["momento"] = pd.to_datetime(meteo["momento"], utc=True)

    exclusion = pd.Timedelta(minutes=VENTANA_EXCLUSION_MIN)
    mask_excluir = pd.Series(False, index=meteo.index)
    for ts in positivos["ignition_ts"]:
        mask_excluir |= (meteo["momento"] >= ts - exclusion) & (meteo["momento"] <= ts + exclusion)

    negativos_pool = meteo.loc[~mask_excluir, FEATURES].dropna().reset_index(drop=True)
    return positivos, negativos_pool


def run_leave_one_out(positivos: pd.DataFrame, negativos_pool: pd.DataFrame) -> pd.DataFrame:
    """12 folds LOO sobre los positivos; class_weight='balanced' (no SMOTE:
    con 11 positivos por fold, SMOTE generaría variaciones fabricadas de una
    muestra ya mínima). Negativos de test separados de los de entrenamiento
    (split fijo, reutilizado en los 12 folds) para no evaluar sobre filas
    que el modelo ya vio.
    """
    neg_train, neg_test = train_test_split(
        negativos_pool, test_size=NEGATIVOS_TEST_SIZE, random_state=RANDOM_STATE
    )

    resultados: list[dict] = []
    for i in range(len(positivos)):
        held_out = positivos.iloc[[i]]
        train_pos = positivos.drop(index=i)

        x_train = pd.concat([train_pos[FEATURES], neg_train[FEATURES]], ignore_index=True)
        y_train = pd.Series([1] * len(train_pos) + [0] * len(neg_train))

        clf = RandomForestClassifier(
            n_estimators=200, class_weight="balanced", random_state=RANDOM_STATE
        )
        clf.fit(x_train, y_train)

        proba_held_out = clf.predict_proba(held_out[FEATURES])[0, 1]
        proba_neg_test = clf.predict_proba(neg_test[FEATURES])[:, 1]

        resultados.append(
            {
                "fold": i + 1,
                "ignition_ts": str(held_out["ignition_ts"].iloc[0]),
                "proba_predicha": round(float(proba_held_out), 4),
                "recall_binario_0.5": int(proba_held_out >= 0.5),
                "percentil_vs_negativos_test": round(
                    float((proba_neg_test <= proba_held_out).mean() * 100), 1
                ),
            }
        )

    res_df = pd.DataFrame(resultados)
    res_df["n_duplicados_evento"] = res_df.groupby("ignition_ts")["ignition_ts"].transform("count")
    res_df["evento_independiente_sin_fuga"] = res_df["n_duplicados_evento"] == 1
    return res_df


def main() -> None:
    positivos, negativos_pool = build_positivos_y_negativos()
    print(f"positivos (detecciones reales <={DISTANCIA_MAX_KM:.0f}km): {len(positivos)}")
    print(f"negativos pool (tras excluir ventanas de {VENTANA_EXCLUSION_MIN}min): {len(negativos_pool)}")

    res_df = run_leave_one_out(positivos, negativos_pool)
    print()
    print(res_df.to_string(index=False))

    independientes = res_df[res_df["evento_independiente_sin_fuga"]]
    print()
    print(f"=== EXPLORATORIO, n={len(res_df)} ({len(independientes)} sin fuga de duplicados) ===")
    print("recall promedio (todos, incluye fuga):", res_df["recall_binario_0.5"].mean())
    print(
        "recall promedio (solo eventos sin fuga):",
        independientes["recall_binario_0.5"].mean() if len(independientes) else float("nan"),
    )
    print(
        "percentil promedio (solo eventos sin fuga):",
        round(independientes["percentil_vs_negativos_test"].mean(), 1) if len(independientes) else float("nan"),
    )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    res_df.to_csv(OUT_PATH, index=False)
    print(f"\nguardado: {OUT_PATH}")


if __name__ == "__main__":
    main()
