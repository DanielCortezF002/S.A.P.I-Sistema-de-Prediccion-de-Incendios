-- Seed demo corredor Viña–Quilpué–Villa Alemana: 50 celdas circulares (~1 km²)
-- Fecha única de snapshot: 2025-02-15 | Generado por scripts/generate_seed.py

TRUNCATE predicciones_riesgo RESTART IDENTITY CASCADE;

INSERT INTO predicciones_riesgo (cell_id, fecha, probabilidad, nivel_riesgo, temperatura, humedad_relativa, velocidad_viento, regla_30_30_30, geom)
VALUES
('VP-001', '2025-02-15'::date, 0.26, 'bajo', 19.2, 75.6, 28.0, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.52, -33.04), 4326)::geography, 564)::geometry),
('VP-002', '2025-02-15'::date, 0.26, 'bajo', 19.2, 75.6, 28.4, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.512, -33.04), 4326)::geography, 564)::geometry),
('VP-003', '2025-02-15'::date, 0.26, 'bajo', 19.2, 75.6, 28.8, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.504, -33.04), 4326)::geography, 564)::geometry),
('VP-004', '2025-02-15'::date, 0.51, 'medio', 22.7, 52.6, 19.2, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.496, -33.04), 4326)::geography, 564)::geometry),
('VP-005', '2025-02-15'::date, 0.51, 'medio', 22.7, 52.6, 19.6, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.488, -33.04), 4326)::geography, 564)::geometry),
('VP-006', '2025-02-15'::date, 0.51, 'medio', 22.7, 52.6, 20.0, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.48, -33.04), 4326)::geography, 564)::geometry),
('VP-007', '2025-02-15'::date, 0.51, 'medio', 22.7, 52.6, 20.4, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.472, -33.04), 4326)::geography, 564)::geometry),
('VP-008', '2025-02-15'::date, 0.64, 'medio', 26.2, 35.6, 23.3, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.464, -33.04), 4326)::geography, 564)::geometry),
('VP-009', '2025-02-15'::date, 0.64, 'medio', 26.2, 35.6, 23.7, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.456, -33.04), 4326)::geography, 564)::geometry),
('VP-010', '2025-02-15'::date, 0.64, 'medio', 26.2, 35.6, 24.1, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.448, -33.04), 4326)::geography, 564)::geometry),
('VP-011', '2025-02-15'::date, 0.26, 'bajo', 19.3, 75.4, 28.0, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.52, -33.032), 4326)::geography, 564)::geometry),
('VP-012', '2025-02-15'::date, 0.26, 'bajo', 19.3, 75.4, 28.4, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.512, -33.032), 4326)::geography, 564)::geometry),
('VP-013', '2025-02-15'::date, 0.26, 'bajo', 19.3, 75.4, 28.8, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.504, -33.032), 4326)::geography, 564)::geometry),
('VP-014', '2025-02-15'::date, 0.51, 'medio', 22.8, 52.4, 19.2, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.496, -33.032), 4326)::geography, 564)::geometry),
('VP-015', '2025-02-15'::date, 0.51, 'medio', 22.8, 52.4, 19.6, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.488, -33.032), 4326)::geography, 564)::geometry),
('VP-016', '2025-02-15'::date, 0.51, 'medio', 22.8, 52.4, 20.0, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.48, -33.032), 4326)::geography, 564)::geometry),
('VP-017', '2025-02-15'::date, 0.51, 'medio', 22.8, 52.4, 20.4, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.472, -33.032), 4326)::geography, 564)::geometry),
('VP-018', '2025-02-15'::date, 0.64, 'medio', 26.3, 35.4, 23.3, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.464, -33.032), 4326)::geography, 564)::geometry),
('VP-019', '2025-02-15'::date, 0.64, 'medio', 26.3, 35.4, 23.7, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.456, -33.032), 4326)::geography, 564)::geometry),
('VP-020', '2025-02-15'::date, 0.64, 'medio', 26.3, 35.4, 24.1, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.448, -33.032), 4326)::geography, 564)::geometry),
('VP-021', '2025-02-15'::date, 0.26, 'bajo', 19.4, 75.1, 28.0, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.52, -33.024), 4326)::geography, 564)::geometry),
('VP-022', '2025-02-15'::date, 0.26, 'bajo', 19.4, 75.1, 28.4, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.512, -33.024), 4326)::geography, 564)::geometry),
('VP-023', '2025-02-15'::date, 0.26, 'bajo', 19.4, 75.1, 28.8, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.504, -33.024), 4326)::geography, 564)::geometry),
('VP-024', '2025-02-15'::date, 0.51, 'medio', 22.9, 52.1, 19.2, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.496, -33.024), 4326)::geography, 564)::geometry),
('VP-025', '2025-02-15'::date, 0.51, 'medio', 22.9, 52.1, 19.6, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.488, -33.024), 4326)::geography, 564)::geometry),
('VP-026', '2025-02-15'::date, 0.51, 'medio', 22.9, 52.1, 20.0, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.48, -33.024), 4326)::geography, 564)::geometry),
('VP-027', '2025-02-15'::date, 0.52, 'medio', 22.9, 52.1, 20.4, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.472, -33.024), 4326)::geography, 564)::geometry),
('VP-028', '2025-02-15'::date, 0.64, 'medio', 26.4, 35.1, 23.3, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.464, -33.024), 4326)::geography, 564)::geometry),
('VP-029', '2025-02-15'::date, 0.64, 'medio', 26.4, 35.1, 23.7, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.456, -33.024), 4326)::geography, 564)::geometry),
('VP-030', '2025-02-15'::date, 0.64, 'medio', 26.4, 35.1, 24.1, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.448, -33.024), 4326)::geography, 564)::geometry),
('VP-031', '2025-02-15'::date, 0.26, 'bajo', 19.6, 74.9, 28.0, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.52, -33.016), 4326)::geography, 564)::geometry),
('VP-032', '2025-02-15'::date, 0.26, 'bajo', 19.6, 74.9, 28.4, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.512, -33.016), 4326)::geography, 564)::geometry),
('VP-033', '2025-02-15'::date, 0.26, 'bajo', 19.6, 74.9, 28.8, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.504, -33.016), 4326)::geography, 564)::geometry),
('VP-034', '2025-02-15'::date, 0.51, 'medio', 23.1, 51.9, 19.2, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.496, -33.016), 4326)::geography, 564)::geometry),
('VP-035', '2025-02-15'::date, 0.51, 'medio', 23.1, 51.9, 19.6, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.488, -33.016), 4326)::geography, 564)::geometry),
('VP-036', '2025-02-15'::date, 0.52, 'medio', 23.1, 51.9, 20.0, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.48, -33.016), 4326)::geography, 564)::geometry),
('VP-037', '2025-02-15'::date, 0.52, 'medio', 23.1, 51.9, 20.4, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.472, -33.016), 4326)::geography, 564)::geometry),
('VP-038', '2025-02-15'::date, 0.97, 'alto', 32.5, 24.0, 34.0, 1, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.464, -33.016), 4326)::geography, 564)::geometry),
('VP-039', '2025-02-15'::date, 0.64, 'medio', 26.6, 34.9, 23.7, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.456, -33.016), 4326)::geography, 564)::geometry),
('VP-040', '2025-02-15'::date, 0.64, 'medio', 26.6, 34.9, 24.1, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.448, -33.016), 4326)::geography, 564)::geometry),
('VP-041', '2025-02-15'::date, 0.26, 'bajo', 19.7, 74.6, 28.0, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.52, -33.008), 4326)::geography, 564)::geometry),
('VP-042', '2025-02-15'::date, 0.26, 'bajo', 19.7, 74.6, 28.4, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.512, -33.008), 4326)::geography, 564)::geometry),
('VP-043', '2025-02-15'::date, 0.26, 'bajo', 19.7, 74.6, 28.8, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.504, -33.008), 4326)::geography, 564)::geometry),
('VP-044', '2025-02-15'::date, 0.51, 'medio', 23.2, 51.6, 19.2, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.496, -33.008), 4326)::geography, 564)::geometry),
('VP-045', '2025-02-15'::date, 0.52, 'medio', 23.2, 51.6, 19.6, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.488, -33.008), 4326)::geography, 564)::geometry),
('VP-046', '2025-02-15'::date, 0.52, 'medio', 23.2, 51.6, 20.0, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.48, -33.008), 4326)::geography, 564)::geometry),
('VP-047', '2025-02-15'::date, 0.52, 'medio', 23.2, 51.6, 20.4, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.472, -33.008), 4326)::geography, 564)::geometry),
('VP-048', '2025-02-15'::date, 0.64, 'medio', 26.7, 34.6, 23.3, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.464, -33.008), 4326)::geography, 564)::geometry),
('VP-049', '2025-02-15'::date, 0.97, 'alto', 32.5, 24.0, 34.0, 1, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.456, -33.008), 4326)::geography, 564)::geometry),
('VP-050', '2025-02-15'::date, 0.64, 'medio', 26.7, 34.6, 24.1, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.448, -33.008), 4326)::geography, 564)::geometry);

INSERT INTO staging_incendios (fecha, latitud, longitud, fuente, geom) VALUES
('2025-02-15'::timestamptz, -33.043, -71.484, 'conaf_seed', ST_SetSRID(ST_MakePoint(-71.484, -33.043), 4326)),
('2025-02-15'::timestamptz, -33.046, -71.488, 'conaf_seed', ST_SetSRID(ST_MakePoint(-71.488, -33.046), 4326)),
('2025-02-15'::timestamptz, -33.049, -71.492, 'conaf_seed', ST_SetSRID(ST_MakePoint(-71.492, -33.049), 4326)),
('2025-02-15'::timestamptz, -33.052, -71.496, 'conaf_seed', ST_SetSRID(ST_MakePoint(-71.496, -33.052), 4326)),
('2025-02-15'::timestamptz, -33.055, -71.5, 'conaf_seed', ST_SetSRID(ST_MakePoint(-71.5, -33.055), 4326)),
('2025-02-15'::timestamptz, -33.058, -71.504, 'conaf_seed', ST_SetSRID(ST_MakePoint(-71.504, -33.058), 4326)),
('2025-02-15'::timestamptz, -33.061, -71.508, 'conaf_seed', ST_SetSRID(ST_MakePoint(-71.508, -33.061), 4326)),
('2025-02-15'::timestamptz, -33.064, -71.512, 'conaf_seed', ST_SetSRID(ST_MakePoint(-71.512, -33.064), 4326)),
('2025-02-15'::timestamptz, -33.067, -71.516, 'conaf_seed', ST_SetSRID(ST_MakePoint(-71.516, -33.067), 4326)),
('2025-02-15'::timestamptz, -33.07, -71.52, 'conaf_seed', ST_SetSRID(ST_MakePoint(-71.52, -33.07), 4326));

INSERT INTO staging_meteo (fecha, temperatura, humedad_relativa, velocidad_viento, estacion_id, geom) VALUES
(TIMESTAMP '2025-02-15 12:00:00+00' - INTERVAL '1 hours', 21, 49, 13, 'VTM', ST_SetSRID(ST_MakePoint(-71.50, -33.04), 4326)),
(TIMESTAMP '2025-02-15 12:00:00+00' - INTERVAL '2 hours', 22, 48, 14, 'VTM', ST_SetSRID(ST_MakePoint(-71.50, -33.04), 4326)),
(TIMESTAMP '2025-02-15 12:00:00+00' - INTERVAL '3 hours', 23, 47, 15, 'VTM', ST_SetSRID(ST_MakePoint(-71.50, -33.04), 4326)),
(TIMESTAMP '2025-02-15 12:00:00+00' - INTERVAL '4 hours', 20, 46, 16, 'VTM', ST_SetSRID(ST_MakePoint(-71.50, -33.04), 4326)),
(TIMESTAMP '2025-02-15 12:00:00+00' - INTERVAL '5 hours', 21, 45, 17, 'VTM', ST_SetSRID(ST_MakePoint(-71.50, -33.04), 4326)),
(TIMESTAMP '2025-02-15 12:00:00+00' - INTERVAL '6 hours', 22, 44, 18, 'VTM', ST_SetSRID(ST_MakePoint(-71.50, -33.04), 4326)),
(TIMESTAMP '2025-02-15 12:00:00+00' - INTERVAL '7 hours', 23, 43, 19, 'VTM', ST_SetSRID(ST_MakePoint(-71.50, -33.04), 4326)),
(TIMESTAMP '2025-02-15 12:00:00+00' - INTERVAL '8 hours', 20, 50, 20, 'VTM', ST_SetSRID(ST_MakePoint(-71.50, -33.04), 4326)),
(TIMESTAMP '2025-02-15 12:00:00+00' - INTERVAL '9 hours', 21, 49, 21, 'VTM', ST_SetSRID(ST_MakePoint(-71.50, -33.04), 4326)),
(TIMESTAMP '2025-02-15 12:00:00+00' - INTERVAL '10 hours', 22, 48, 12, 'VTM', ST_SetSRID(ST_MakePoint(-71.50, -33.04), 4326));

INSERT INTO observability_logs (componente, evento, detalle, nivel)
VALUES ('seed', 'init', 'Seed corredor Vina-Quilpue-Villa Alemana: 50 celdas, meteo zonal', 'INFO');
