#!/bin/sh
set -e
echo "[S.A.P.I. Prototipo] Iniciando demonio de simulacion analitica horaria/diaria..."
while true; do
    echo "[Pipeline] Ejecutando actualizacion automatizada de caracteristicas y predicciones..."
    python -m src.pipeline.run_daily
    echo "[Pipeline] Ciclo completado con exito. Durmiendo por 24 horas..."
    sleep 86400
done
