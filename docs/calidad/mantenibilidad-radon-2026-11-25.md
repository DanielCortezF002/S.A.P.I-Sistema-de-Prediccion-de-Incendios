# C4 · Mantenibilidad · complejidad con radon · 25-11-2026

- Código medido: árbol de trabajo en `5c5793e` y descendientes (mismo código de aplicación que `518c0b58e6b229317f51b1da56ac23346dc2ef74`: los commits posteriores a 518c0b5 solo agregan `reports/` y `docs/calidad/`; se verifica con `git diff --stat 518c0b5 HEAD -- src services tools app` en el resultado).
- Herramienta: radon 6.0.1 (con mando 0.7.1, colorama 0.4.6, six 1.17.0) en un entorno virtual desechable, Python 3.15.2 del equipo. Ejecutado en el computador local, no en ambiente desplegado.
- Hardware: AMD Ryzen AI 7 350 (8 núcleos, 16 hilos), 31 GB de RAM, Windows 11 Home 10.0.26200.

## 1. Escenario (commiteado antes de medir)

| Parte | Valor |
|---|---|
| Fuente | Desarrollador que debe cambiar la lógica de negocio del ranking |
| Estímulo | Un cambio en el cálculo del ranking del Modelo D |
| Entorno | Código en desarrollo, en el commit indicado |
| Alcance («lógica de negocio») | Los 16 archivos Python que el ml-api importa de forma transitiva desde `services/ml_api/main.py` (lista generada con `ast`, en [alcance.txt](evidencia/2026-11-25-mantenibilidad/alcance.txt)). Fuera: backend Java (radon no lo mide), `app/` (interfaz Streamlit), pruebas y scripts |
| Medida | `radon cc` (complejidad ciclomática por función o método) y `radon mi` (índice de mantenibilidad por archivo) |
| **Criterio** | **Cumple** si (1) ningún bloque tiene rango D, E o F (CC > 20) **y** (2) todos los archivos tienen MI rango A (MI ≥ 20). Si falla uno, no cumple. Se informan también la CC media, los bloques de rango C (11–20) y el MI mínimo. No se ajusta después de medir |

## 2. Resultado

Pendiente de la medición.
