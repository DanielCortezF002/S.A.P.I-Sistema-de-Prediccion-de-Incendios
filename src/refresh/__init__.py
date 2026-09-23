"""Refresco manual, versionado y atómico de insumos de scoring (SAPI-71 Fase B).

Nada de este paquete corre desde n8n ni desde n8n-bridge: se ejecuta a mano
(`python -m src.refresh.firms_refresh ...`) en el host o con
`docker compose run --rm analytics-backend python -m ...`. Nunca reentrena
Model D ni reconstruye el dataset de entrenamiento.
"""
