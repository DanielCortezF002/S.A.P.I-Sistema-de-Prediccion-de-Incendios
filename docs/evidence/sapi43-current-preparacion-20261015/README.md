# Preparación CURRENT real — SAPI-43/71 (Directiva 35 / Etapa 2)

**No se ejecutó ningún refresco real ni se contactó ningún servicio externo
en esta sesión.** Este documento prepara, no ejecuta.

## 1. Requisitos exactos para DMC y NASA FIRMS con datos auténticos

| Variable | Usada por | Rol |
|---|---|---|
| `DMC_USUARIO` | `src/config.py:60`, consumida por `src/refresh/dmc_refresh.py` | Usuario de la API DMC (`getDatosRecientesEma`) |
| `DMC_TOKEN` | `src/config.py:61` | Token de autenticación DMC |
| `DMC_API_BASE_URL` | `src/config.py:22-23` | No es secreto (tiene default público: `https://climatologia.meteochile.gob.cl`) |
| `NASA_FIRMS_API_KEY` | `.env.example:64`, resuelta en runtime por `src/refresh/firms_refresh.py::refresh` (`map_key` por parámetro, nunca al importar) | MAP_KEY de NASA FIRMS (registro gratuito de autoservicio en `firms.modaps.eosdis.nasa.gov`) |

Ninguna de las tres se lee desde un archivo versionado: no existe `.env` en
este repositorio (`.env.example` solo trae placeholders), y la arquitectura
las inyecta en tiempo de ejecución al proceso del operador.

## 2. Verificación de presencia — solo PRESENTE/AUSENTE, nunca valores

Comando ejecutado en este entorno (15-10-2026):

```
python -c "import os
for var in ['DMC_USUARIO','DMC_TOKEN','NASA_FIRMS_API_KEY']:
    print(f'{var}: {\"PRESENTE\" if os.environ.get(var) else \"AUSENTE\"}')"
```

Resultado:

| Variable | Estado |
|---|---|
| `DMC_USUARIO` | **AUSENTE** |
| `DMC_TOKEN` | **AUSENTE** |
| `NASA_FIRMS_API_KEY` | **AUSENTE** |

No existe archivo `.env` en este clon (`ls .env` → no encontrado). Ningún
valor fue impreso, solicitado ni inferido.

## 3. Entorno operacional desechable y aislado (descrito, NO ejecutado)

El runbook original (`docs/ops/FIRST-CONTROLLED-REFRESH.md`) fue escrito
para un worktree específico distinto de este clon
(`D:\portafolio y seminario\SAPI-71-postmerge-worktree`), con su propia
evidencia, SHA aprobado y checklist GO/ABORT/ROLLBACK ya detallado paso a
paso. **No se adapta ni se ejecuta ese runbook contra este clon** — ese
worktree y este candidato (`C:\SAPI-S2-CLOSEOUT-CLAUDE-20261015`) son
entornos distintos; mezclarlos sin verificación de identidad violaría el
propio precondición #2 del runbook ("usar la revisión aprobada... nunca el
worktree histórico").

Para preparar (no ejecutar) un refresco real sobre **este** candidato, de
llegar la autorización, el procedimiento correcto sería:

1. Clonar este candidato (SHA final vigente) a un worktree
   **nuevo y desechable**, fuera de `C:\SAPI-S2-CLOSEOUT-CLAUDE-20261015`.
2. Verificar en ese clon nuevo: `git rev-parse HEAD`, `git status --short`
   (debe estar limpio), ausencia de `CURRENT.json` en
   `data/processed/{dmc,firms}/` (primera publicación) o identidad conocida
   si ya existe uno (usar rollback, no sobreescribir).
3. Detener cualquier consumidor (bridge/Streamlit) que pudiera leer el store
   durante la operación.

### Comandos concretos (listos para copiar, NO ejecutados en esta sesión)

```powershell
# 1) Worktree desechable, fuera de este clon de cierre
$Candidate = '9321a517a727c7bb47349f07d8219388dba956d5'  # o el SHA final vigente al momento de operar
$Disposable = Join-Path $env:TEMP ('sapi43-refresh-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
git clone --quiet 'C:\SAPI-S2-CLOSEOUT-CLAUDE-20261015' $Disposable
Set-Location -LiteralPath $Disposable
git checkout --quiet $Candidate
git rev-parse HEAD                     # debe == $Candidate
git status --short                     # debe estar vacio

# 2) Verificacion de partida (solo lectura, sin credenciales)
Test-Path 'data/processed/firms/CURRENT.json'   # esperado: False (primera publicacion)
Test-Path 'data/processed/dmc/.refresh.lock'    # esperado: False
Test-Path 'data/processed/firms/.refresh.lock'  # esperado: False

# 3) Verificacion de credenciales -- SOLO presencia, nunca valores
foreach ($v in 'DMC_USUARIO','DMC_TOKEN','NASA_FIRMS_API_KEY') {
    if (Test-Path "env:$v") { "$v`: PRESENTE" } else { "$v`: AUSENTE" }
}

# 4) Si todo lo anterior es correcto Y se cuenta con autorizacion humana
#    explicita y separada, recien entonces (operacion NO preparada por este
#    documento, requiere decision aparte):
#    python -m src.refresh.firms_refresh status
#    python -m src.refresh.dmc_refresh status
#    (solo entonces, siguiendo GO/ABORT/ROLLBACK de FIRST-CONTROLLED-REFRESH.md)
```

Nada de lo anterior fue ejecutado en esta sesión; se entrega como
procedimiento listo para que el operador lo corra él mismo.
4. Inyectar `DMC_USUARIO`, `DMC_TOKEN`, `NASA_FIRMS_API_KEY` **solo** en el
   entorno de proceso del operador en ese clon desechable (nunca en archivo
   versionado, nunca en este repositorio).
5. Ejecutar `python -m src.refresh.firms_refresh status` y
   `python -m src.refresh.dmc_refresh status` primero (solo lectura) para
   confirmar el estado de partida antes de cualquier `refresh`.
6. Solo entonces, con autorización humana explícita y separada de esta
   preparación, proceder con `refresh` siguiendo el GO/ABORT/ROLLBACK ya
   escrito en `FIRST-CONTROLLED-REFRESH.md` (gates de abort 65/69/75/78,
   verificación de fingerprint reproducible sin cambios, 50 celdas).

**CURRENT canónico de este candidato no fue tocado ni se tocará sin ese
paso 6 separado y explícitamente autorizado.**

## 4. Instrucciones mínimas para el operador

1. Registrar un MAP_KEY FIRMS gratuito en `https://firms.modaps.eosdis.nasa.gov`
   (autoservicio, sin costo, sin aprobación institucional).
2. Confirmar si ya se dispone de `DMC_USUARIO`/`DMC_TOKEN` vigentes (el
   contrato DMC ya se probó en vivo el 23-09-2026 según
   `docs/ops/DMC-LIVE-CONTRACT-PROBE.md`).
3. Exportar las tres variables **solo** en la sesión de shell del operador en
   el worktree desechable del paso 1 de la sección 3 (ej.
   `$env:NASA_FIRMS_API_KEY = '...'` en PowerShell, sin escribirlas a disco,
   sin incluirlas en ningún commit, log, prompt o documento).
4. Nunca pegar estos valores en un chat, prompt a un asistente, ticket de
   Jira o captura de pantalla.

## 5. Estado explícito

- **SAPI-43/71: preparado, no ejecutado.** Ningún refresco real corrió en
  esta sesión. Ninguna credencial fue solicitada, impresa o inferida.
- **CURRENT canónico: sin tocar.**
- **Bloqueo restante:** autorización humana explícita + credenciales reales
  en manos del operador, inyectadas únicamente en un worktree desechable.
