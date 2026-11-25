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

## 2. Resultado (verificado hoy)

Escenario commiteado en `f234b3e30ff6c69a372cae90ff87d7d0b4de7f16` (2026-11-25T08:11:59-03:00). Medición: 2026-11-25T11:12:09Z, una vez. `git diff --stat 518c0b5 HEAD -- src services tools app` salió vacío: el código medido es el de 518c0b5.

| Medida | Observado | Cumple |
|---|---|---|
| (1) 0 bloques con rango D, E o F | **3 bloques con rango D** (de 129): `src/ingesta/firms_schema.py::_values` CC 27; `src/procesamiento/firms_source.py::validate_pointer_dict` CC 25; `tools/n8n_bridge/contract.py::_cell_violations` CC 23 | **No** |
| (2) MI rango A en los 16 archivos | 16 de 16 en A. Mínimo: `src/procesamiento/meteo_fire_joiner.py`, MI 37,37 | Sí |

**Veredicto: NO CUMPLE** (falla la condición 1).

Datos descriptivos: 129 bloques; 109 en A, 14 en B, 3 en C, 3 en D; CC media 3,57 (A). Rango C: `score_current_grid` (CC 11, `src/inference/prototype_service.py`), `project_frame` (14, `firms_schema.py`), `validate_grid_result` (16, `contract.py`).

Lectura acotada: las tres funciones en D son **validadores** (esquema FIRMS, puntero `CURRENT.json` y contrato de la grilla), con muchas ramas de rechazo. La CC alta no indica un error, pero sí que cuesta más cambiarlas y probar todas sus ramas. No se midió cuántas de esas ramas cubren las pruebas.

| ID | Hallazgo | Severidad | Decisión |
|---|---|---|---|
| DEF-MAN-01 | `_values` CC 27 (D) | Media | **Abierto.** Sin ticket Jira (no autorizado hoy) |
| DEF-MAN-02 | `validate_pointer_dict` CC 25 (D) | Media | **Abierto** |
| DEF-MAN-03 | `_cell_violations` CC 23 (D) | Media | **Abierto** |

Evidencia (archivos generados por radon, sin editar): [radon-cc.json](evidencia/2026-11-25-mantenibilidad/radon-cc.json) (SHA-256 `500d1d51…99eb`), [radon-mi.json](evidencia/2026-11-25-mantenibilidad/radon-mi.json) (`e8633536…3371`), [radon-cc-rango-C-o-peor.txt](evidencia/2026-11-25-mantenibilidad/radon-cc-rango-C-o-peor.txt) (`515713ca…9d45`), [fecha-utc.txt](evidencia/2026-11-25-mantenibilidad/fecha-utc.txt). Comandos: `radon cc -j <alcance>`, `radon mi -j <alcance>`, `radon cc -s -a -nc <alcance>`.

## 3. Lo que no se midió

- **Cobertura de la lógica de negocio:** no se corrió pytest hoy. El último dato es histórico: 85,17 % de la suite Python en `cf5f4cc` (22-11, otra rama), que no es la cobertura de este alcance. Si se corre, va con `--ignore=tests/test_f1_ca8_operational_overlay_dynamic.py`.
- **Backend Java:** radon no lo mide; no se usó otra herramienta.

## 4. Clasificación

- **Verificado hoy:** sección 2 completa.
- **Histórico:** la cobertura de `cf5f4cc`.
- **Pendiente:** cobertura del alcance, complejidad del backend Java y tickets de DEF-MAN-01 a 03.
