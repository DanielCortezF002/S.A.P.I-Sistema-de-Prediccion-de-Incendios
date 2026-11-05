# Guía de Contribución y Estándares de Ingeniería — S.A.P.I.

Gracias por contribuir a **S.A.P.I. (Sistema de Alerta y Predicción de Incendios)**.
Este proyecto combina desarrollo de software profesional, analítica geoespacial y modelos de Machine Learning en un contexto de alta responsabilidad académica y técnica. Para mantener la excelencia, trazabilidad e integridad del repositorio, todos los colaboradores (humanos y agentes de IA) deben acatar estrictamente los estándares descritos en esta guía.

---

## 1. Principio Rector: Integridad Científica Innegociable

S.A.P.I. investiga la predicción preventiva de incendios forestales bajo un marco ético estricto. Cualquier contribución que toque modelos, features, evaluación o documentación debe respetar los siguientes **invariantes científicos**:

1. **Semántica del Score:** El puntaje emitido por el **Modelo D** (`HistGradientBoostingClassifier`) es un **ranking relativo exploratorio** entre las 50 celdas de la misma evaluación. **Nunca** debe llamarse "probabilidad calibrada de incendio", "alerta oficial" ni "riesgo absoluto".
2. **Declaración de Estado Científico:** El sistema opera bajo `scientific_model_validation = false` y **F4 FAIL**. Los tests de software y pruebas unitarias demuestran que el código no arroja errores, pero **no sustituyen la validación científica** con datos externos etiquetados ni evaluación en terreno.
3. **Naturaleza de NASA FIRMS:** Una detección satelital FIRMS (sensor VIIRS) representa una **anomalía térmica espacial observada**, **no** una ignición o incendio confirmado en terreno.
4. **Naturaleza de DMC:** Los datos de la Dirección Meteorológica de Chile provienen de estaciones meteorológicas específicas (p. ej. Estación 330007 Rodelillo) y representan **contexto meteorológico regional**, no mediciones micrometeorológicas por celda individual.
5. **Topografía DEM y Celdas N/D:** Para celdas sin cobertura en el modelo digital de elevación Copernicus GLO-30 (p. ej. celdas costeras VP-047 y VP-038), se reporta estrictamente `N/D` con su nota técnica explicativa. **Queda terminantemente prohibido inventar o interpolar ceros artificiales**.
6. **Cero Fabricación de Evidencia:** Nunca inventar métricas, conteos de tests, porcentajes de cobertura, timestamps ni respaldos institucionales (CONAF o SENAPRED).

---

## 2. Flujo de Trabajo Git y Estrategia de Ramas

El repositorio utiliza una estrategia basada en ramas cortas vinculadas a **Jira (Proyecto SAPI)** integradas exclusivamente mediante Pull Requests:

```
main (código estable integrado)
  ↑
  └── PR con revisión obligatoria
        ↑
        feat/SAPI-XX-descripcion-corta
```

### 2.1. Convención de Nomenclatura de Ramas

Toda rama de trabajo debe crearse a partir de la rama `main` actualizada y seguir el siguiente formato:

| Prefijo | Propósito | Ejemplo |
|---|---|---|
| `feat/` | Nueva funcionalidad o módulo | `feat/SAPI-71-dmc-refresh` |
| `fix/` | Corrección de bug o fallo en prueba | `fix/SAPI-72-evidence-paths` |
| `docs/` | Documentación, ADR o informes académicos | `docs/SAPI-62-model-card` |
| `chore/` | Mantenimiento, dependencias o configuración de CI | `chore/hito2-w0-gate` |
| `refactor/` | Reestructuración de código sin cambio de comportamiento | `refactor/SAPI-69-centralize-firms` |

### 2.2. Aislamiento Mediante Worktrees

Para evitar colisiones entre ramas de desarrollo activo, entornos de agentes de IA y revisiones de auditoría, se recomienda utilizar **Git Worktrees**:

```bash
# Crear un worktree aislado para una nueva tarea
git worktree add ../SAPI-nueva-tarea feat/SAPI-XX-nombre-tarea
```

**Regla:** Nunca ejecutar commits directos sobre `main` ni realizar force-push (`git push --force`).

---

## 3. Estándar de Mensajes de Commit (Conventional Commits)

Los commits deben ser atómicos, descriptivos y redactados en minúsculas siguiendo la convención de [Conventional Commits](https://www.conventionalcommits.org/):

```
<tipo>(<alcance>): <descripción concisa y factual> [opcional: Jira ticket]

[cuerpo explicativo opcional detallando el motivo del cambio y evidencia]
```

### Ejemplos Válidos:
- `feat(ml-api): expose Model D scoring endpoint via FastAPI (SAPI-55)`
- `fix(docker): exclude secrets and local artifacts from build context (SAPI-70)`
- `docs(adr): formalize ADR-009 reproducible mode for academic evaluations`
- `test(e2e): add unit tests for bidirectional table-map navigation`

---

## 4. Quality Gates y Estándares de Código

Antes de enviar un Pull Request o solicitar revisión, el código debe satisfacer todos los Quality Gates automatizados del repositorio:

### 4.1. Formateo y Análisis Estático (Python)
```bash
# Verificar formato con black
black --check .

# Análisis estático de linting
flake8
```

### 4.2. Suite de Pruebas y Cobertura Mínima
El archivo `pytest.ini` impone un **Quality Gate de cobertura mínima del 80%** sobre los paquetes `app/` y `src/`:
```bash
pytest
```
*Si se trabaja en componentes específicos:*
```bash
pytest tests/test_ranking_backend_view.py
```

### 4.3. Backend Spring Boot (Java)
Si se introducen cambios en `services/backend/`:
```bash
cd services/backend
./mvnw clean test verify
```

### 4.4. Validación de Contratos OpenAPI
Las especificaciones YAML en `contracts/openapi/` deben ser válidas contra el estándar OpenAPI v3:
```bash
pytest tests/test_openapi_contracts.py
```

---

## 5. Principio "Evidence-First" para Entregables

Cualquier cambio que impacte la interfaz gráfica, la inferencia o la reproducibilidad debe acompañarse de **evidencia técnica verificable**:

1. **Cambios en Interfaz (UI Streamlit / Folium):**
   - Probar en navegador real tanto en **Modo Oscuro** (Dark) como en **Modo Claro** (Light).
   - Verificar contraste visual accesible (WCAG 2.1 AA, ratio ≥ 3:1 para elementos gráficos y ≥ 4.5:1 para texto).
   - Adjuntar capturas de pantalla fechadas en `docs/evidence/browser_audit/`.
2. **Cambios en Ingesta y Modelos:**
   - Registrar la semilla aleatoria, versión de dataset y corte temporal en `reports/` o `artifacts/`.
   - Probar que `SAPI_REPRODUCIBILITY_MODE=1` produce el fingerprint hash exacto del Modelo D.

---

## 6. Seguridad y Manejo de Secretos

- **Prohibición Absoluta de Secretos en Git:** Ningún archivo `.env`, token de GitHub, credencial de base de datos o llave de API (NASA FIRMS MAP_KEY) debe ser agregado a Git.
- Utilizar exclusivamente `.env.example` como plantilla para documentar nuevas variables de entorno requeridas por los servicios.
- Todo contenedor Docker debe pasar la verificación de `tests/test_docker_build_hygiene.py`.

---

## 7. Checklist para Envío de Pull Requests (PR)

Antes de marcar un Pull Request como listo para revisión, asegúrate de marcar:

- [ ] La rama parte de `main` y está actualizada.
- [ ] No se modificaron archivos congelados en `artifacts/hito1/reproducibility/`.
- [ ] No se alteraron pesos ni lógica del Modelo D sin protocolo formal de investigación.
- [ ] Todos los tests de la suite pasan (`pytest` finaliza con cobertura ≥ 80%).
- [ ] `black --check .` y `flake8` no arrojan advertencias ni errores.
- [ ] No se incluyen claves, tokens ni archivos `.env`.
- [ ] Se adjunta evidencia reproducible de la verificación (comandos, logs o capturas).
- [ ] Se referencia el ticket de Jira correspondiente (p. ej. `SAPI-XX`).
