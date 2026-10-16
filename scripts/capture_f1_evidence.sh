#!/usr/bin/env bash
# SAPI F1 (Jira SAPI-43 #10134/#10135, dictamen Astra -- "evidencia del SHA final"):
# registra automaticamente HEAD, tree, worktree y digests del candidato EXACTO que
# produjo el resto de un directorio de evidencia ya generado (artifacts/hito2/f1/<ts>/).
# No recalcula ni reinterpreta los artefactos; solo sella identidad git + checksums
# sobre lo que ya existe en el directorio, para que nunca quede un SHA fijo/obsoleto
# ni un git_commits.txt vacio.
#
# Uso:
#   scripts/capture_f1_evidence.sh <directorio-de-evidencia>
#
# Ejemplo:
#   scripts/capture_f1_evidence.sh artifacts/hito2/f1/20261014T120000Z
set -euo pipefail

if [ "$#" -ne 1 ]; then
    echo "uso: $0 <directorio-de-evidencia>" >&2
    exit 2
fi

EVIDENCE_DIR="$1"
if [ ! -d "$EVIDENCE_DIR" ]; then
    echo "error: no existe el directorio '$EVIDENCE_DIR'" >&2
    exit 2
fi

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

HEAD_SHA="$(git rev-parse HEAD)"
TREE_SHA="$(git rev-parse 'HEAD^{tree}')"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
UTC_NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
WORKTREE_STATUS="$(git status --porcelain)"
WORKTREE_STATE="clean"
if [ -n "$WORKTREE_STATUS" ]; then
    WORKTREE_STATE="dirty"
fi

# Referencia anterior conocida del mismo linaje (build/F1-remediation), para que
# git_commits.txt siempre liste exactamente lo que este candidato agrega -- nunca
# vacio, nunca un historial ajeno. Si HEAD no la tiene como ancestro (por ejemplo,
# en una ronda futura con una referencia distinta), se usa la raiz del repositorio.
PRIOR_REF="462a1fb8dd236efc2efe8b75883c9c6cb93df210"
if ! git merge-base --is-ancestor "$PRIOR_REF" HEAD 2>/dev/null; then
    PRIOR_REF="$(git rev-list --max-parents=0 HEAD | tail -n1)"
fi

{
    echo "head: $HEAD_SHA"
    echo "tree: $TREE_SHA"
    echo "branch: $BRANCH"
    echo "captured_utc: $UTC_NOW"
    echo "worktree: $WORKTREE_STATE"
    if [ "$WORKTREE_STATE" = "dirty" ]; then
        echo "worktree_entries:"
        echo "$WORKTREE_STATUS" | sed 's/^/  /'
    fi
    echo "commits_since: $PRIOR_REF"
} > "$EVIDENCE_DIR/git_identity.txt"

git log --format='%H %ad %s' --date=iso-strict "$PRIOR_REF..HEAD" > "$EVIDENCE_DIR/git_commits.txt"
if [ ! -s "$EVIDENCE_DIR/git_commits.txt" ]; then
    echo "error: git_commits.txt quedo vacio ($PRIOR_REF..HEAD no tiene commits); no se escribe un paquete sin atribucion" >&2
    exit 1
fi

# SHA256SUMS.txt: todo archivo del directorio de evidencia EXCEPTO el propio
# manifiesto (sin autorreferencia, Astra P2) y sin incluir git_identity.txt/
# git_commits.txt como si fueran parte del contenido verificado por otra corrida
# -- se generan e incluyen en la MISMA pasada, así que sí entran al manifiesto.
MANIFEST="$EVIDENCE_DIR/SHA256SUMS.txt"
(
    cd "$REPO_ROOT"
    find "$EVIDENCE_DIR" -type f ! -name "$(basename "$MANIFEST")" -print0 \
        | sort -z \
        | xargs -0 sha256sum
) > "$MANIFEST"

echo "evidencia sellada en $EVIDENCE_DIR:"
echo "  head=$HEAD_SHA tree=$TREE_SHA worktree=$WORKTREE_STATE"
echo "  commits atribuidos: $(wc -l < "$EVIDENCE_DIR/git_commits.txt")"
echo "  archivos en manifiesto: $(wc -l < "$MANIFEST")"
