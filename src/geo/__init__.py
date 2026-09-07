"""Geometría pura del territorio (grilla de análisis).

No es una capa analítica (ingesta/procesamiento/modelo/pipeline): no lee
fuentes externas ni produce features o predicciones, solo define la forma
del territorio. Por eso `app/` puede importar de acá sin romper el Data
Contract (ver `tests/test_architecture.py::_PROHIBITED_MODULES`), igual que
ya puede importar de `src.config`.
"""
