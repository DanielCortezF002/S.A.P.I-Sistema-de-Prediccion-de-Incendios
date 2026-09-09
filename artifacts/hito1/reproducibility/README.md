# Bundle de reproducibilidad — Hito 1

**Formalizado 09-09-2026, posterior al cierre histórico de Sprint 1
(31-08-2026).** No es evidencia de que este bundle haya existido durante
Sprint 1 — es una formalización de reproducibilidad hecha hoy sobre los
artefactos científicos originales ya verificados (mismo `dataset_hash`,
mismos resultados de `score_current_grid()`, sin alterar metodología ni
métricas).

## Contenido

- **`manifest.json`** — cadena de proveniencia completa (NASA FIRMS → DMC →
  Copernicus DEM → dataset temporal → Modelo D → inferencia), hashes SHA256,
  clasificación R1–R4 de reproducibilidad, decisión de licencia sobre el
  dataset.

## Qué está versionado en git y qué no

| Artefacto | ¿Versionado? | Dónde |
|---|---|---|
| `models/prototype_model_d.pkl` (Modelo D oficial, 68 KB) | **SÍ**, desde 09-09-2026 | `models/prototype_model_d.pkl` (excepción quirúrgica en `.gitignore`) |
| `models/prototype_model_d_metadata.json` | Sí, desde el Hito 1 original | `models/prototype_model_d_metadata.json` |
| `data/processed/temporal_dataset_h6.parquet` (10,8 MB) | **NO** — `LICENSE_NOT_CONFIRMED` | fuera de git, ver `manifest.json` sección `licencia_dataset` |
| `data/raw/*` (NASA FIRMS, DMC, DEM crudos, ~210 MB) | No | fuera de git |

## Guía completa

Ver `docs/deploy.md`, sección **"Reproducibilidad de datos y modelo"** —
distingue RUTA A (reproducción desde el snapshot congelado) de RUTA B
(reconstrucción desde las APIs externas). No se duplica aquí para evitar
que ambas fuentes diverjan.

## Verificar el estado local contra este manifest

```bash
python scripts/verify_reproducibility.py
```
