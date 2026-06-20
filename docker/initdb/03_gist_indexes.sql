CREATE INDEX IF NOT EXISTS idx_staging_incendios_geom ON staging_incendios USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_staging_meteo_geom ON staging_meteo USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_matriz_features_geom ON matriz_features USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_matriz_features_fecha ON matriz_features (fecha);
CREATE INDEX IF NOT EXISTS idx_predicciones_riesgo_geom ON predicciones_riesgo USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_predicciones_riesgo_fecha ON predicciones_riesgo (fecha);
CREATE INDEX IF NOT EXISTS idx_predicciones_fecha_cell ON predicciones_riesgo (fecha DESC, cell_id);
CREATE INDEX IF NOT EXISTS idx_staging_meteo_created ON staging_meteo (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_staging_incendios_created ON staging_incendios (created_at DESC);
