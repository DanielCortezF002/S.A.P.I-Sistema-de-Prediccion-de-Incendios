#!/usr/bin/env bash
# Una corrida k6 RNF-03 a nivel API (N=1). Luz verde: Daniel 25-11 08:50 Chile, vía Director.
set -u
AQUI="$(cd "$(dirname "$0")" && pwd)"; W=$(cygpath -w "$AQUI")
OUT="$AQUI/corrida-rnf03-1vu-$(date -u +%Y%m%dT%H%M%SZ)"; mkdir -p "$OUT"; WO=$(cygpath -w "$OUT")
{
  echo "inicio_utc: $(date -u +%FT%TZ)"
  echo "sha_repo_HEAD: $(git -C "$AQUI" rev-parse HEAD)"
  echo "sha_codigo_stack: 518c0b58e6b229317f51b1da56ac23346dc2ef74"
  echo "imagenes:"; docker compose -p sapi-h3-518c0b5 images 2>&1
  echo "contenedores_en_marcha:"; docker ps --format '{{.Names}} {{.Image}} {{.Status}}'
  echo "N=1 VU; calentamiento 1 iteración (excluida); medición 30 iteraciones secuenciales sin pausa; timeout 90 s"
  echo "umbral: p95 rango más cercano <= 2000 ms y 0 fallos"
  echo "luz_verde: Daniel 25-11 08:50 Chile vía Director (task_d961225e01aa)"
} > "$OUT/00-cabecera.txt"
fase() {
  MSYS_NO_PATHCONV=1 docker run --rm -v "$W:/scripts:ro" -v "$WO:/out" grafana/k6:0.54.0 run \
    -e FASE=$1 -e BASE_URL=http://host.docker.internal:18080 \
    --summary-export=/out/$1-summary-export.json --out json=/out/$1-muestras.json \
    /scripts/rnf03_api_1vu.js > "$OUT/$1-consola.txt" 2>&1
  echo "k6 exit=$?" >> "$OUT/$1-consola.txt"
}
echo "calentamiento_inicio_utc: $(date -u +%FT%TZ)" >> "$OUT/00-cabecera.txt"; fase calentamiento
echo "medicion_inicio_utc: $(date -u +%FT%TZ)" >> "$OUT/00-cabecera.txt"; fase medicion
echo "fin_utc: $(date -u +%FT%TZ)" >> "$OUT/00-cabecera.txt"
echo "$OUT"
