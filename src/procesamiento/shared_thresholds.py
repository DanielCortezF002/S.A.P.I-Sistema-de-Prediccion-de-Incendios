"""Constantes de negocio compartidas, sin dependencias de ningún pipeline.

Extraído el 09-09-2026 desde `src/procesamiento/features.py` (auditoría de
arquitectura 4+1, ver `docs/architecture-4plus1-hito1.md`). Antes de este
cambio, `src/procesamiento/regional_meteo.py` (parte del pipeline temporal
nuevo) importaba estas constantes directamente desde `features.py` — un
módulo cuyo consumidor principal es el pipeline **legacy**
(`FeatureEngineer` es usado por `src.modelo.baseline`, `src.modelo.optimizer`
y `src.modelo.inference_engine`, y `features.py` importa `imblearn` a nivel
de módulo para `FeatureEngineer.apply_smote_balance`). Ese import forzaba a
Python a cargar `imblearn`/SMOTE cada vez que se importaba `regional_meteo`,
aunque el pipeline temporal nunca usa SMOTE ni ningún otro contenido de
`FeatureEngineer` — solo estos tres flotantes.

Este módulo es intencionalmente una hoja del árbol de imports (no importa
nada de `src.modelo` ni de `src.procesamiento.features`) para que ambos
pipelines —el legacy (vía `features.py`, que sigue reexportando estos
nombres por compatibilidad) y el temporal (vía este módulo directamente)—
puedan compartir la MISMA definición de la regla 30-30-30 sin que uno
dependa transitivamente del otro. Los valores no cambiaron: siguen siendo
exactamente 30.0/30.0/30.0, igual que antes de esta extracción.
"""

from __future__ import annotations

RULE_30_30_30_TEMP_THRESHOLD = 30.0
RULE_30_30_30_HUMIDITY_THRESHOLD = 30.0
RULE_30_30_30_WIND_THRESHOLD = 30.0
