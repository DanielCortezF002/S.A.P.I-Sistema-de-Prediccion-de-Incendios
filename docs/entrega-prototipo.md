# Entrega prototipo S.A.P.I. — checklist y evidencia

Documento de cierre para defensa de titulación. Resume qué demostrar, cómo validarlo y las limitaciones explícitas del demo.

## Objetivos específicos (OE1–OE3)

| OE | Criterio | Evidencia |
|----|----------|-----------|
| **OE1** Pipeline ETL + PostGIS SSoT | Ingesta, procesamiento, persistencia espacial | `src/ingesta/`, `src/procesamiento/`, Docker Compose, tablas `staging_*` y `predicciones_riesgo` |
| **OE2** ML con Recall ≥ 75% | RF + XGBoost + SMOTE, validación temporal | `reports/metrics.json` (Recall XGBoost **0.78**, AUC **0.83**) |
| **OE3** Dashboard Streamlit + Folium | UI desacoplada, caché, mapa interactivo | Streamlit Cloud, `app/app.py`, build `demo-50cells-v8-professional` |

## Demo multi-fecha (2025-02-09 → 2025-02-15)

Ventana de **7 días** × **50 celdas** = **350 filas** en `predicciones_riesgo`.

| Fecha | Qué debe verse | Altos | Regla 30-30-30 |
|-------|----------------|-------|----------------|
| 2025-02-09 | Mayoría verde/amarillo, costa húmeda | 0 | 0 |
| 2025-02-10 | Perfil suave, sin rojos | 0 | 0 |
| 2025-02-11 | Idem | 0 | 0 |
| 2025-02-12 | Aumento gradual T / caída HR este | 0 | 0 |
| 2025-02-13 | Transición hacia condiciones secas | 0 | 0 |
| 2025-02-14 | Precordillera más seca, aún sin rojos | 0 | 0 |
| **2025-02-15** | **2 rojos** (VP-038, VP-049), regla activa | **2** | **2** |

Resumen JSON generado por el seed: [`reports/seed_summary.json`](../reports/seed_summary.json).

## Checklist pre-defensa

- [ ] Streamlit Cloud en **Python 3.11**, estado *Running*
- [ ] Build sidebar: `demo-50cells-v8-professional`
- [ ] Query sidebar: `exact-date-v1`
- [ ] Cambiar fecha **modifica** mapa y KPIs (probar 2025-02-09 vs 2025-02-15)
- [ ] Día 15: 50 celdas, 2 alto, regla en VP-038 y VP-049
- [ ] Tabla detalle con columna **#** 1–50
- [ ] Reporte TXT descarga con fecha y conteos por nivel
- [ ] `pytest` ≥ 80 % cobertura en CI/local
- [ ] Tag Git `v3.2.0-demo-professional` (opcional)

## Validación PostGIS

```sql
SELECT fecha, COUNT(*) AS celdas
FROM predicciones_riesgo
GROUP BY fecha
ORDER BY fecha;
-- Esperado: 7 filas, 50 celdas cada una
```

## Reaplicar seed en Supabase

Desde PowerShell en la raíz del repo (usar pooler puerto **5432** para DDL en Windows):

```powershell
$env:DATABASE_URL_POOLER='postgresql://postgres.PROJECT:PASSWORD@aws-1-sa-east-1.pooler.supabase.com:5432/postgres?sslmode=require'
docker run --rm -v "${PWD}:/work" -w /work postgres:15 psql "$env:DATABASE_URL_POOLER" -v ON_ERROR_STOP=1 -f docker/initdb/04_seed_valparaiso.sql
```

Luego **Reboot app** en Streamlit Cloud para invalidar caché.

## Limitaciones vs informe de titulación

- Datos **sintéticos calibrados** (no DMC/CONAF/NASA en vivo)
- **50 celdas** en corredor Viña–Quilpué–Villa Alemana (no región completa)
- Sin export PDF institucional ni webhooks SENAPRED
- Sin pipeline cron 24 h en cloud

Mensaje para evaluadores: *“Prototipo de viabilidad técnica; arquitectura modular lista para conectar fuentes reales en producción.”*

## Referencias

- [Manual de uso y guion](manual-uso-presentacion.md)
- [Alcance del prototipo](alcance-prototipo.md)
- [Despliegue cloud](deploy.md)
- Repositorio: [github.com/DanielCortezF002/S.A.P.I-Sistema-de-Prediccion-de-Incendios](https://github.com/DanielCortezF002/S.A.P.I-Sistema-de-Prediccion-de-Incendios)
