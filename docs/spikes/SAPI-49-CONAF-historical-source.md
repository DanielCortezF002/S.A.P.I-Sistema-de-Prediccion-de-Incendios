# SAPI-49 — Spike: Identificación y Evaluación de Fuente Oficial de Datos Históricos de Incendios CONAF

| Metadato | Detalle |
|---|---|
| **ID de Historia** | SAPI-49 (`Spike — Identificar fuente real de datos históricos CONAF`) |
| **Épica** | SAPI-22 (`Ingesta y Fuentes de Datos`) |
| **Riesgo Vinculado** | R-CONAF-01 (`docs/matriz-riesgo.md`) |
| **Autor / Rol** | Senior Data Engineer, Cloud Architect y Technical Research Lead (Antigravity) |
| **Fecha de Investigación** | 14 de octubre de 2026 |
| **Estado** | Completado (Investigación empírica con evidencia reproducible) |
| **Workspace Git** | `C:\SAPI-antigravity` (rama `feat/SAPI-antigravity-sprint2`) |

---

## 1. Contexto y Diagnóstico del Estado Actual

En el Hito 1 del proyecto S.A.P.I., la ingesta de ocurrencia histórica de incendios quedó formalizada exclusivamente a través de NASA FIRMS (12.477 focos satelitales georreferenciados para el quinquenio 2021–2026, historia SAPI-26). Por el contrario, la fuente institucional de la Corporación Nacional Forestal (CONAF) quedó registrada como un riesgo técnico abierto: **R-CONAF-01**.

### 1.1 Diagnóstico del código actual (`src/ingesta/parallel_ingester.py`)
Al inspeccionar `ParallelIngester._ingest_conaf()` (líneas 230–256):
```python
response = self._download_with_retry(
    f"{CONAF_DATA_URL}/wp-json/wp/v2/posts",
    {"per_page": 1},
)
payload = self._parse_conaf_response(response)
```
Y el método `_parse_conaf_response`:
```python
def _parse_conaf_response(self, response: requests.Response) -> list[dict[str, Any]]:
    """Carga histórico institucional embebido (prototipo demo).
    La API pública de CONAF no expone incendios vía REST; el prototipo
    usa el seed institucional versionado en repositorio.
    """
    if CONAF_SEED_PATH.exists():
        return json.loads(CONAF_SEED_PATH.read_text(encoding="utf-8"))
    return [{"source": "conaf", "status": "reachable", "meta": response.status_code}]
```

**Hallazgos técnicos verificados:**
1. `CONAF_DATA_URL` apunta a `https://www.conaf.cl`. El endpoint `/wp-json/wp/v2/posts` corresponde a la API REST nativa del gestor de contenidos WordPress (CMS) para artículos de noticias institucionales; **no tiene relación alguna con datos operacionales ni históricos de incendios**.
2. La respuesta HTTP del CMS se ignora completamente.
3. Se intenta leer `CONAF_SEED_PATH` (`data/raw/conaf_historico_seed.json`), archivo que **no existe en el repositorio** (0 coincidencias en filesystem e historial git).
4. El parser devuelve un registro sintético `[{"source": "conaf", "status": "reachable"}]`.

**Objetivo de este spike:** Identificar una fuente gubernamental u oficial auténtica, accesible por medios programáticos estándar, con cobertura temporal y espacial compatible con el proyecto, determinando si ofrece registros puntuales de ignición o únicamente agregados estadísticos, e inspeccionar una muestra real de su esquema sin crear parsers ficticios.

---

## 2. Investigación de Fuentes Oficiales Candidatas

Se realizó una prospección sistemática sobre los portales estatales de Chile, infraestructura de datos espaciales y repositorios científicos:

| Fuente / Portal | Institución Responsable | URL Base | Cobertura Temporal | Cobertura Territorial | Formato | Tipo de Datos | ¿Registros Individuales con Coordenadas? | Mecanismo de Acceso | Licencia |
|---|---|---|---|---|---|---|---|---|---|
| **A. IDE Minagri / CIREN (ArcGIS REST)** | IDE Minagri / CONAF / CIREN | `https://esri.ciren.cl/server/rest/services/IDEMINAGRI/` | 2010 a 2025 (15 temporadas consecutivas) | Nacional (todas las regiones + Rapa Nui) | GeoJSON, Esri JSON, WMS, KMZ | Eventos de ignición | **SÍ (Puntos WGS84 y UTM con fecha/hora)** | HTTP GET a endpoint `/query` (público, sin token) | Datos públicos del Estado de Chile |
| **B. Plataforma de Datos para la Resiliencia (Itrend)** | Itrend en convenio con CONAF | `https://www.plataformadedatos.cl/datasets/es/94233F2661964B0` | 2002 a 2020 (18 temporadas) | Nacional | CSV, GeoJSON, Shapefile | Puntos de ignición estimados | **SÍ (Latitud/Longitud, fecha/hora, duración)** | Descarga web o API REST vía librería `pytrend` (requiere API key) | Creative Commons Atribución 4.0 (CC BY 4.0) |
| **C. Portal CONAF Incendios / Centro Documental** | CONAF (PPCIF) | `https://www.conaf.cl/incendios/` | 1985 a 2024 | Nacional / Regional / Comunal | Excel (.xlsx, .xls), PDF, Looker Studio | Estadísticas agregadas | **NO (Solo agregados: N° incendios y ha totales por mes/comuna)** | Descarga manual web | Dominio público / Gobierno abierto |
| **D. Repositorio Científico PANGAEA / (CR)2** | Universidad de Chile / (CR)2 / PANGAEA | `https://doi.org/10.1594/PANGAEA.941127` | 1984 a 2018 | Centro-Sur de Chile (32°S–42°S) | Shapefile, NetCDF, GeoTIFF | Polígonos de cicatrices satelitales | **NO (Son polígonos de área quemada / severidad satelital, no avisos CONAF)** | Descarga directa por DOI | Creative Commons CC-BY 3.0 |
| **E. Datos Abiertos Chile (`datos.gob.cl`)** | SEGPRES / Estado de Chile | `https://datos.gob.cl` | N/A | N/A | N/A | No dispone de dataset activo de igniciones CONAF | **NO** | N/A | N/A |

### 2.1 Conclusión sobre granularidad de datos públicos de CONAF
- En el portal principal de CONAF (`conaf.cl`), la institución **únicamente publica estadísticas agregadas** en planillas Excel y reportes en PDF (ocurrencia total por región/comuna y hectáreas consumidas por tipo de vegetación). El sistema operacional transaccional de CONAF (**SIDCO**, Sistema de Información Digital para Control de Operaciones) es un sistema interno de despacho y alerta temprana restringido para brigadistas y personal de operaciones, sin endpoint público abierto.
- **Sin embargo, a través de la Infraestructura de Datos Espaciales del Ministerio de Agricultura (IDE Minagri / CIREN)**, CONAF publica periódicamente la capa cartográfica oficial de ocurrencia por temporada bajo el servicio `IDEMINAGRI/INCENDIOS_MINIS_INSTI/MapServer`. **Esta capa SÍ contiene los registros individuales de cada incendio forestal con fecha, hora, coordenadas y desglose de daños.**

---

## 3. Fuente Seleccionada: IDE Minagri / CONAF ArcGIS REST Feature Service

La fuente seleccionada para el proyecto S.A.P.I. es el servicio oficial de mapas y entidades mantenido por CIREN para la IDE del Ministerio de Agricultura de Chile:

- **Endpoint Raíz del Servicio:** `https://esri.ciren.cl/server/rest/services/IDEMINAGRI/INCENDIOS_MINIS_INSTI/MapServer`
- **Catálogo de Capas Relevantes (verificado en vivo):**
  - Capa 36: `ideminagri.ideconaf.if_temporada_2010_2011_1`
  - Capa 37: `ideminagri.ideconaf.if_temporada_2011_2012_1`
  - Capa 38: `ideminagri.ideconaf.if_temporada_2012_2013_1`
  - Capa 39: `ideminagri.ideconaf.if_temporada_2013_2014_1`
  - Capa 40: `ideminagri.ideconaf.if_temporada_2014_2015_1`
  - Capa 41: `ideminagri.ideconaf.if_temporada_2015_2016_1`
  - Capa 42: `ideminagri.ideconaf.if_temporada_2016_2017_1`
  - Capa 43: `ideminagri.ideconaf.if_temporada_2017_2018_1`
  - Capa 44: `ideminagri.ideconaf.if_temporada_2018_2019_1`
  - Capa 45: `ideminagri.ideconaf.if_temporada_2019_2020_1`
  - Capa 46: `ideminagri.ideconaf.if_temporada_2020_2021_1`
  - Capa 47: `ideminagri.ideconaf.if_temporada_2021_2022_1_1` (6.884 eventos verificados)
  - Capa 48: `ideminagri.ideconaf.if_temporada_2022_2023_1`
  - Capa 49: `ideminagri.ideconaf.if_temporada_2023_2024_1`
  - Capa 50: `ideminagri.ideconaf.If_temporada_2024_2025_1` (6.262 eventos verificados)
  - Capas 51 a 62: Incendios de Magnitud por temporada (2013 a 2025).

---

## 4. Inspección de Esquema y Muestra Auténtica

Se realizaron consultas en vivo al servicio ArcGIS REST de IDE Minagri para obtener la definición exacta del esquema y un registro auténtico.

### 4.1 Diccionario de Datos (Esquema Verificado)

| Campo | Tipo Esri | Tipo Python/SQL | Descripción / Semántica |
|---|---|---|---|
| `objectid` | `esriFieldTypeOID` | `INTEGER` (PK) | Identificador secuencial interno de la entidad |
| `temporada` | `esriFieldTypeString` | `VARCHAR(15)` | Temporada forestal (ej. `"2021-2022"`, `"2024-2025"`) |
| `region` | `esriFieldTypeString` | `VARCHAR(50)` | Nombre de la región administrativa (ej. `"O'Higgins"`, `"Valparaíso"`) |
| `provincia` | `esriFieldTypeString` | `VARCHAR(50)` | Nombre de la provincia |
| `comuna` | `esriFieldTypeString` | `VARCHAR(50)` | Nombre de la comuna |
| `codreg` | `esriFieldTypeDouble` / String | `VARCHAR(5)` | Código único territorial (CUT) regional |
| `codcom` | `esriFieldTypeString` | `VARCHAR(10)` | Código CUT comunal (disponible en capas consolidadas) |
| `numero_reg` / `n_mero_re` | `esriFieldTypeDouble` | `INTEGER` | Número de registro oficial CONAF |
| `nombre` / `nom_incen` | `esriFieldTypeString` | `VARCHAR(100)` | Denominación toponímica asignada al incendio por CONAF |
| `utm_e` | `esriFieldTypeDouble` | `DOUBLE PRECISION` | Coordenada UTM Este (m) |
| `utm_n` | `esriFieldTypeDouble` | `DOUBLE PRECISION` | Coordenada UTM Norte (m) |
| `huso` / `huso_op_` | `esriFieldTypeString` | `VARCHAR(5)` | Huso UTM (18 o 19) |
| `inicio_c` / `inicio_cer` | `esriFieldTypeString` | `VARCHAR(100)` | Lugar o factor de inicio cercano (ej. `"Camino secundario"`, `"Faenas agrícolas"`) |
| `combustibl` / `combus_i` | `esriFieldTypeString` | `VARCHAR(100)` | Tipo de combustible de ignición inicial (ej. `"Pastizal"`, `"Desechos"`, `"Matorral"`) |
| `causa_gene` | `esriFieldTypeString` | `VARCHAR(150)` | Causa general codificada según estándar CONAF (ej. `"1.2 - Faenas agrícolas y pecuarias"`) |
| `causa_espe` | `esriFieldTypeString` | `TEXT` | Causa específica investigada en terreno por la UAD (Unidad de Análisis y Diagnóstico) |
| `superficie` | `esriFieldTypeDouble` | `DOUBLE PRECISION` | Superficie total afectada en hectáreas (ha) |
| `pino_*`, `eucalipto`, `arbolado`, `matorral`, `pastizal`, `desechos` | `esriFieldTypeDouble` | `DOUBLE PRECISION` | Hectáreas consumidas desglosadas por estrato vegetal |
| `fh_inicio` | `esriFieldTypeString` | `VARCHAR(30)` | Fecha y hora de inicio reportada (formato texto: `D-mes-YYYY HH:MM`) |
| `fh_extinci` | `esriFieldTypeString` | `VARCHAR(30)` | Fecha y hora de extinción o control del siniestro |
| `geometry` | `esriGeometryMultipoint` | `GEOMETRY(MultiPoint, 4326)` | Geometría espacial de ignición/focos asociados a un único registro administrativo (MultiPoint en GeoJSON). Debe preservarse como MultiPoint sin descomponer en registros artificiales independientes. |

### 4.1.1 Tratamiento Técnico de la Geometría MultiPoint
- **Naturaleza del dato:** En el servicio IDE Minagri (ej. capa 47), el atributo geométrico devuelto por ArcGIS Server en formato GeoJSON (`f=geojson`) es de tipo `MultiPoint` (`"type": "MultiPoint"`), estructurado como un arreglo de pares de coordenadas `[[lon, lat], ...]`. Aunque en la gran mayoría de los registros contiene un único par coordenado (el punto de inicio), la especificación formal del servicio es multipunto.
- **Preservación de integridad y prohibición de inventar igniciones:**
  1. **Prohibición de "explode" o descomposición ingenua:** Un error común en pipelines geoespaciales es aplicar `ST_Dump` o desglosar los puntos individuales en filas separadas. En el dominio de S.A.P.I., hacer esto violaría la integridad científica, fabricando artificialmente "nuevas igniciones independientes" a partir de focos secundarios o vértices del mismo evento reportado.
  2. **Persistencia nativa en PostGIS:** La columna espacial debe definirse estrictamente como `GEOMETRY(MultiPoint, 4326)`. Cada fila de la tabla `conaf_fire_incidents` representa exactamente un único incendio administrativo (`numero_reg`), independientemente de cuántos puntos contenga su geometría.
  3. **Intersección espacial con la grilla SAPI (`VP-001..VP-050`):**
     - La relación espacial se evalúa mediante `ST_Intersects(grid.geom, conaf.geom)`.
     - Si los puntos de un `MultiPoint` tocan más de una celda, debe aplicarse una regla de negocio explícita y documentada (por ejemplo, vincular el evento a la celda que contiene el primer punto o centroide, o registrar presencia a nivel de evento), sin duplicar nunca la cuenta de igniciones independientes.

### 4.2 Muestra Auténtica Descargada en Vivo (GeoJSON)

Consulta ejecutada:
`GET https://esri.ciren.cl/server/rest/services/IDEMINAGRI/INCENDIOS_MINIS_INSTI/MapServer/47/query?where=1%3D1&outFields=*&f=geojson&resultRecordCount=1`

Respuesta devuelta por el servidor oficial:
```json
{
  "type": "Feature",
  "id": 1,
  "geometry": {
    "type": "MultiPoint",
    "coordinates": [
      [
        -72.00256023794459,
        -34.44314052404984
      ]
    ]
  },
  "properties": {
    "objectid": 1,
    "id": 1,
    "temporada": "2021-2022",
    "region": "O'Higgins",
    "provincia": "Cardenal Caro",
    "comuna": "Pichilemu",
    "codreg": "06",
    "codprov": "062",
    "codcom": "06201",
    "ambito": "Conaf",
    "numero_reg": 183,
    "nom_incen": "LAS QUILAS",
    "utm_e": 224122.370645,
    "utm_n": 6184617.04985,
    "huso": "19",
    "inicio_c": "Casa o refugio",
    "combus_i": "Basural",
    "causa_gene": "Incendios de causa desconocida",
    "causa_espe": "4.1.2. No determinada (la causa no es investigada)",
    "pino_00_10": 0,
    "pino_11_17": 0,
    "pino18_mas": 0,
    "eucalipto": 0.2,
    "otras_plan": 0,
    "total_plan": 0.2,
    "arbolado": 0,
    "matorral": 0.4,
    "pastizal": 0,
    "total_veg": 0.4,
    "agricola": 0,
    "desechos": 0,
    "total_otra": 0,
    "superficie": 0.6,
    "fh_inicio": "3-feb-2022 20:40",
    "fh_extinci": "4-feb-2022 10:32"
  }
}
```

---

## 5. Compatibilidad Técnica con el Proyecto S.A.P.I.

### 5.1 Cruce Espacial con la Grilla Operacional (`VP-001..VP-050`)
- **Geometría:** La geometría es de tipo `MultiPoint` (`coordinates: [[lon, lat], ...]`). Mediante PostGIS (`ST_Intersects(grid.geom, conaf.geom)`) o Shapely en Python (`grid_polygon.intersects(shape(feature['geometry']))`), el evento administrativo se evalúa contra las celdas de la grilla de Valparaíso (`VP-001..VP-050`).
- **Tratamiento de eventos multipunto en límites:** En caso de que un registro contenga múltiples coordenadas que toquen más de una celda, no se debe fragmentar el incendio en eventos artificiales. Se debe vincular el evento único conservando su geometría completa y determinando su celda primaria mediante criterio causal/espacial (por ejemplo, punto de inicio temporal o centroide), sin multiplicar las filas de eventos ni inventar igniciones independientes.
- **Filtrado Regional:** La capa dispone de atributo `region = 'Valparaíso'` o `codreg = '05'`, lo que permite optimizar la consulta descargando únicamente los incendios de la zona piloto antes de realizar el join espacial.

### 5.2 Cruce Temporal y Causalidad (Regla de Integridad Científica)
- En el dataset de entrenamiento de S.A.P.I. (Modelo D), la causalidad exige que las características $X_t$ se construyan estrictamente con información anterior o igual a $T$ ($t \le T$).
- La variable `fh_inicio` registra el momento en que se declaró el fuego.
- **Particularidad técnica del formato de fecha:** El servicio almacena `fh_inicio` como cadena de texto localizada en español (ej. `"3-feb-2022 20:40"`, `"16-sep-2024 08:14"`). Un adaptador de ingesta requerirá una rutina de normalización temporal que mapee los meses en español (`ene`, `feb`, `mar`, ..., `dic`) a marcas de tiempo estándar ISO 8601 UTC antes de almacenar en PostgreSQL.

### 5.3 Comparación: CONAF (Terreno) vs NASA FIRMS (Satélite)
En el Hito 1, SAPI-26 utilizó NASA FIRMS (MODIS/VIIRS). La disponibilidad de CONAF aporta valor diferenciado como **registro institucional útil para contrastación y validación**, pero debe interpretarse reconociendo sus limitaciones intrínsecas:

| Dimensión | NASA FIRMS (Actual) | CONAF IDE Minagri (Spike SAPI-49) | Rol en S.A.P.I. y Alcance Científico |
|---|---|---|---|
| **Tipo de detección** | Radiación infrarroja satelital (anomalías térmicas) | Registro institucional administrativo en terreno (alertas ciudadanas, combate de brigadas, peritaje UAD) | CONAF constituye un registro institucional útil para contrastación y validación empírica; FIRMS es la observación física satelital. Ninguno representa un "ground truth" absoluto. |
| **Falsos positivos y sesgos** | Fuentes térmicas no forestales (industrias, chimeneas, reflejos solares, quemas) | No contiene fuentes térmicas fijas, pero presenta **sesgo de reporte humano** y omisión en zonas de baja visibilidad o sin patrullaje | Permite contrastar anomalías satelitales con incidentes reportados institucionalmente, reconociendo que la ausencia de reporte no prueba ausencia física de fuego. |
| **Tiempo de refresco y disponibilidad** | NRT (Near Real Time, latencia ~3 horas) | Cierre por temporada consolidada y reportes periódicos de campaña | FIRMS es la fuente requerida para inferencia operativa; CONAF es una fuente retrospectiva para estudios de concordancia histórica y análisis de cobertura. |
| **Atributos descriptivos** | Radiométricos (temperatura de brillo, potencia FRP, confianza) | Causa general, causa específica, tipo de combustible de inicio, hectáreas dañadas | Aporta contexto post-evento para análisis cualitativo y caracterización de tipologías de ignición. |

#### 5.3.1 Limitaciones Metodológicas del Registro CONAF
1. **Incertidumbre en la marca temporal (`fh_inicio`):** La hora consignada corresponde habitualmente al momento de la recepción del aviso o primer combate, no necesariamente al instante físico exacto en que ocurrió la ignición en terreno.
2. **Sesgo de detección por accesibilidad y población:** Los siniestros cercanos a áreas urbanas, caminos principales o infraestructura habitada tienen una probabilidad de aviso inmediata; eventos en zonas montañosas remotas pueden reportarse con horas de retraso o no ingresar al registro administrativo si se extinguen de forma natural antes de movilizar brigadas.
3. **No calibración de etiquetas:** El registro CONAF no debe interpretarse como una verdad de terreno absoluta con "0 falsos positivos" ni utilizarse para sobreescribir o "calibrar" mecánicamente etiquetas de riesgo sin una metodología formal de concordancia y análisis de incertidumbre.

---

## 6. Limitaciones Identificadas y Riesgos Operativos

1. **Límite de transferencia por consulta (`exceededTransferLimit: true`):**
   El servidor ArcGIS REST tiene un tope de registros por petición (generalmente 1.000 o 2.000 filas). Para descargar una temporada completa (ej. 6.884 eventos en 2021-2022), el cliente debe implementar paginación mediante `resultOffset` y `resultRecordCount`.
2. **Homogeneidad de nombres de columnas:**
   Entre temporadas distantes (ej. 2010 vs 2024), existen variaciones menores en los nombres de campo (por ejemplo, `nom_incen` vs `nombre`, `numero_reg` vs `n_mero_re`, `combus_i` vs `combustibl`). El parser debe contar con un diccionario de alias o mapeo tolerante.
3. **Formato de fechas no ISO:**
   `fh_inicio` viene en texto en español (`"3-feb-2022 20:40"`). No viene en timestamp UNIX ni formato ISO 8601 con zona horaria, exigiendo parsing determinista.
4. **Disponibilidad del servicio externo:**
   El endpoint pertenece a CIREN (`esri.ciren.cl`). Aunque es un servidor institucional estable de la administración pública, la ingesta no debe ejecutarse en el loop de inferencia crítica; debe ejecutarse como un proceso de *backfill* o *refresh* batch desacoplado, persistiendo los datos crudos en `data/raw/` de forma inmutable.

---

## 7. Evaluación y Recomendación de Integración

### 7.1 Evaluación sobre el placeholder actual
- **Veredicto:** El placeholder `_parse_conaf_response` en `src/ingesta/parallel_ingester.py` (que consulta la API de WordPress de noticias) debe ser **completamente eliminado y reemplazado**.
- **No implementar un parser ficticio en Sprint 2:** Conforme a las reglas de alcance de Sprint 2 y los principios de integridad científica del proyecto S.A.P.I., este spike documenta la fuente real y su esquema comprobado. La implementación del cliente de ingesta no debe introducirse apresuradamente en Sprint 2, pues SAPI-49 estaba catalogada como *Could / Congelado* y no forma parte del vertical slice v2 comprometido en el Hito 2 (Streamlit → Spring Boot → FastAPI → PostGIS).

### 7.2 Recomendación para una Historia Posterior (Sprint 3 / Hito 3)
Se recomienda abrir una historia de desarrollo dedicada (ej. `SAPI-73: Implementar adaptador de ingesta histórica CONAF vía IDE Minagri`):
1. **Crear cliente dedicado:** `src/ingesta/conaf_arcgis_client.py` con métodos para consultar capas por temporada, paginando por `resultOffset` y transformando `fh_inicio` a ISO 8601 UTC.
2. **Script de Backfill:** Crear `scripts/backfill_conaf_incendios.py` análogo a `scripts/backfill_nasa_firms.py`.
3. **Persistencia PostGIS:** Almacenar los eventos en una tabla normalizada `conaf_fire_incidents` con geometría `GEOMETRY(MultiPoint, 4326)`, índice espacial `GIST(geom)` y clave natural `(temporada, numero_reg)`.
4. **Contrastación y Análisis de Concordancia:** Implementar una estrategia de cruce espacial y temporal entre focos NASA FIRMS y eventos terrestres CONAF para contrastar detecciones satelitales con reportes institucionales en estudios de validación científica, sin reescribir ni fabricar etiquetas de entrenamiento sin justificación metodológica.
