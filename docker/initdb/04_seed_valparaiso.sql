-- Seed demo corredor Viña–Quilpué–Villa Alemana: 50 celdas circulares (~1 km²)
-- Fecha única de snapshot: 2025-02-15 | Generado por scripts/generate_seed.py

TRUNCATE predicciones_riesgo RESTART IDENTITY CASCADE;

INSERT INTO predicciones_riesgo (cell_id, fecha, probabilidad, nivel_riesgo, temperatura, humedad_relativa, velocidad_viento, regla_30_30_30, geom)
VALUES
('VP-001', '2025-02-15'::date, 0.41, 'medio', 18.8, 76.5, 28.0, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.52, -33.04), 4326)::geography, 564)::geometry),
('VP-002', '2025-02-15'::date, 0.41, 'medio', 18.9, 76.2, 28.4, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.512, -33.04), 4326)::geography, 564)::geometry),
('VP-003', '2025-02-15'::date, 0.42, 'medio', 19.1, 75.9, 28.8, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.504, -33.04), 4326)::geography, 564)::geometry),
('VP-004', '2025-02-15'::date, 0.43, 'medio', 19.2, 75.6, 29.2, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.496, -33.04), 4326)::geography, 564)::geometry),
('VP-005', '2025-02-15'::date, 0.43, 'medio', 19.4, 75.3, 29.6, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.488, -33.04), 4326)::geography, 564)::geometry),
('VP-006', '2025-02-15'::date, 0.44, 'medio', 19.5, 75.0, 30.0, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.48, -33.04), 4326)::geography, 564)::geometry),
('VP-007', '2025-02-15'::date, 0.44, 'medio', 19.6, 74.7, 30.4, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.472, -33.04), 4326)::geography, 564)::geometry),
('VP-008', '2025-02-15'::date, 0.45, 'medio', 19.8, 74.4, 30.8, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.464, -33.04), 4326)::geography, 564)::geometry),
('VP-009', '2025-02-15'::date, 0.45, 'medio', 19.9, 74.1, 31.2, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.456, -33.04), 4326)::geography, 564)::geometry),
('VP-010', '2025-02-15'::date, 0.46, 'medio', 20.1, 73.8, 31.6, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.448, -33.04), 4326)::geography, 564)::geometry),
('VP-011', '2025-02-15'::date, 0.46, 'medio', 22.2, 53.5, 18.0, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.52, -33.032), 4326)::geography, 564)::geometry),
('VP-012', '2025-02-15'::date, 0.47, 'medio', 22.4, 53.2, 18.4, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.512, -33.032), 4326)::geography, 564)::geometry),
('VP-013', '2025-02-15'::date, 0.49, 'medio', 22.6, 52.9, 18.8, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.504, -33.032), 4326)::geography, 564)::geometry),
('VP-014', '2025-02-15'::date, 0.49, 'medio', 22.7, 52.6, 19.2, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.496, -33.032), 4326)::geography, 564)::geometry),
('VP-015', '2025-02-15'::date, 0.5, 'medio', 22.9, 52.3, 19.6, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.488, -33.032), 4326)::geography, 564)::geometry),
('VP-016', '2025-02-15'::date, 0.51, 'medio', 23.0, 52.0, 20.0, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.48, -33.032), 4326)::geography, 564)::geometry),
('VP-017', '2025-02-15'::date, 0.52, 'medio', 23.1, 51.7, 20.4, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.472, -33.032), 4326)::geography, 564)::geometry),
('VP-018', '2025-02-15'::date, 0.53, 'medio', 23.3, 51.4, 20.8, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.464, -33.032), 4326)::geography, 564)::geometry),
('VP-019', '2025-02-15'::date, 0.54, 'medio', 23.4, 51.1, 21.2, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.456, -33.032), 4326)::geography, 564)::geometry),
('VP-020', '2025-02-15'::date, 0.55, 'medio', 23.6, 50.8, 21.6, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.448, -33.032), 4326)::geography, 564)::geometry),
('VP-021', '2025-02-15'::date, 0.46, 'medio', 22.2, 53.5, 18.0, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.52, -33.024), 4326)::geography, 564)::geometry),
('VP-022', '2025-02-15'::date, 0.47, 'medio', 22.4, 53.2, 18.4, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.512, -33.024), 4326)::geography, 564)::geometry),
('VP-023', '2025-02-15'::date, 0.49, 'medio', 22.6, 52.9, 18.8, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.504, -33.024), 4326)::geography, 564)::geometry),
('VP-024', '2025-02-15'::date, 0.49, 'medio', 22.7, 52.6, 19.2, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.496, -33.024), 4326)::geography, 564)::geometry),
('VP-025', '2025-02-15'::date, 0.5, 'medio', 22.9, 52.3, 19.6, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.488, -33.024), 4326)::geography, 564)::geometry),
('VP-026', '2025-02-15'::date, 0.51, 'medio', 23.0, 52.0, 20.0, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.48, -33.024), 4326)::geography, 564)::geometry),
('VP-027', '2025-02-15'::date, 0.52, 'medio', 23.1, 51.7, 20.4, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.472, -33.024), 4326)::geography, 564)::geometry),
('VP-028', '2025-02-15'::date, 0.53, 'medio', 23.3, 51.4, 20.8, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.464, -33.024), 4326)::geography, 564)::geometry),
('VP-029', '2025-02-15'::date, 0.54, 'medio', 23.4, 51.1, 21.2, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.456, -33.024), 4326)::geography, 564)::geometry),
('VP-030', '2025-02-15'::date, 0.55, 'medio', 23.6, 50.8, 21.6, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.448, -33.024), 4326)::geography, 564)::geometry),
('VP-031', '2025-02-15'::date, 0.78, 'alto', 25.8, 36.5, 20.5, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.52, -33.016), 4326)::geography, 564)::geometry),
('VP-032', '2025-02-15'::date, 0.79, 'alto', 25.9, 36.2, 20.9, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.512, -33.016), 4326)::geography, 564)::geometry),
('VP-033', '2025-02-15'::date, 0.8, 'alto', 26.1, 35.9, 21.3, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.504, -33.016), 4326)::geography, 564)::geometry),
('VP-034', '2025-02-15'::date, 0.81, 'alto', 26.2, 35.6, 21.7, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.496, -33.016), 4326)::geography, 564)::geometry),
('VP-035', '2025-02-15'::date, 0.82, 'alto', 26.4, 35.3, 22.1, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.488, -33.016), 4326)::geography, 564)::geometry),
('VP-036', '2025-02-15'::date, 0.83, 'alto', 26.5, 35.0, 22.5, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.48, -33.016), 4326)::geography, 564)::geometry),
('VP-037', '2025-02-15'::date, 0.97, 'alto', 32.5, 24.0, 34.0, 1, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.472, -33.016), 4326)::geography, 564)::geometry),
('VP-038', '2025-02-15'::date, 0.84, 'alto', 26.8, 34.4, 23.3, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.464, -33.016), 4326)::geography, 564)::geometry),
('VP-039', '2025-02-15'::date, 0.85, 'alto', 26.9, 34.1, 23.7, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.456, -33.016), 4326)::geography, 564)::geometry),
('VP-040', '2025-02-15'::date, 0.86, 'alto', 27.1, 33.8, 24.1, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.448, -33.016), 4326)::geography, 564)::geometry),
('VP-041', '2025-02-15'::date, 0.78, 'alto', 25.8, 36.5, 20.5, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.52, -33.008), 4326)::geography, 564)::geometry),
('VP-042', '2025-02-15'::date, 0.79, 'alto', 25.9, 36.2, 20.9, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.512, -33.008), 4326)::geography, 564)::geometry),
('VP-043', '2025-02-15'::date, 0.97, 'alto', 32.5, 24.0, 34.0, 1, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.504, -33.008), 4326)::geography, 564)::geometry),
('VP-044', '2025-02-15'::date, 0.81, 'alto', 26.2, 35.6, 21.7, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.496, -33.008), 4326)::geography, 564)::geometry),
('VP-045', '2025-02-15'::date, 0.82, 'alto', 26.4, 35.3, 22.1, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.488, -33.008), 4326)::geography, 564)::geometry),
('VP-046', '2025-02-15'::date, 0.83, 'alto', 26.5, 35.0, 22.5, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.48, -33.008), 4326)::geography, 564)::geometry),
('VP-047', '2025-02-15'::date, 0.83, 'alto', 26.6, 34.7, 22.9, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.472, -33.008), 4326)::geography, 564)::geometry),
('VP-048', '2025-02-15'::date, 0.84, 'alto', 26.8, 34.4, 23.3, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.464, -33.008), 4326)::geography, 564)::geometry),
('VP-049', '2025-02-15'::date, 0.85, 'alto', 26.9, 34.1, 23.7, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.456, -33.008), 4326)::geography, 564)::geometry),
('VP-050', '2025-02-15'::date, 0.86, 'alto', 27.1, 33.8, 24.1, 0, ST_Buffer(ST_SetSRID(ST_MakePoint(-71.448, -33.008), 4326)::geography, 564)::geometry);

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
