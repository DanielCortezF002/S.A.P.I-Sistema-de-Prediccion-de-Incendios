-- SAPI-59 · CA3 — ranking completo de la última ejecución persistida.
--
-- Definición aprobada de "última ejecución":
--   ORDER BY created_at DESC, id DESC
-- created_at  = instante en que el sistema persistió la corrida
-- forecast_time = instante evaluado por el modelo (NO define "última")
--
-- Latencia <1s: medida en RankingPersistenceIT.ca3LatestByCreatedAt
-- (warm-up 2 + 10 lecturas; max < 1000 ms) sobre PostGIS real (Omen / failsafe).

SELECT e.id AS ejecucion_id,
       e.forecast_time,
       e.model_version,
       e.inputs_fingerprint,
       e.schema_version,
       e.score_semantics,
       e.scientific_model_validation,
       e.horizon_hours,
       e.created_at,
       p.cell_id,
       p.score,
       p.rank,
       p.display_rank,
       p.tie_group_size
FROM ejecuciones e
JOIN predicciones_celda p ON p.ejecucion_id = e.id
WHERE e.id = (
    SELECT id
    FROM ejecuciones
    ORDER BY created_at DESC, id DESC
    LIMIT 1
)
ORDER BY p.rank ASC;
