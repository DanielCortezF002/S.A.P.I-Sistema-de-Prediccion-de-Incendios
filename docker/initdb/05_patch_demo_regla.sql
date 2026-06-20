-- Parche demo: regla 30-30-30 activa en 2 celdas (ejecutar en Supabase si el seed ya estaba cargado)
UPDATE predicciones_riesgo
SET probabilidad = 0.96,
    nivel_riesgo = 'alto',
    temperatura = 35.2,
    humedad_relativa = 22.0,
    velocidad_viento = 34.5,
    regla_30_30_30 = 1
WHERE cell_id = 'VP-007';

UPDATE predicciones_riesgo
SET probabilidad = 0.93,
    nivel_riesgo = 'alto',
    temperatura = 36.5,
    humedad_relativa = 18.0,
    velocidad_viento = 38.0,
    regla_30_30_30 = 1
WHERE cell_id = 'VP-034';
