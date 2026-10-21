#!/usr/bin/env bash
# Build the offline bundle. Run ONCE on a connected machine; carry bundle/airgap-bundle.tar across the air gap.
# Output: images (docker save), Helm chart package, scripts, and a SHA-256 manifest.
# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"
need docker helm sha256sum tar

OLLAMA_BASE="${OLLAMA_BASE:-ollama/ollama:latest}"
QDRANT_IMAGE="${QDRANT_IMAGE:-qdrant/qdrant:v1.13.0}"
AGENT_IMAGE="airgap/agent:${VERSION}"
MODELS_IMAGE="airgap/ollama-models:${VERSION}"

rm -rf "$BUNDLE_DIR" && mkdir -p "$BUNDLE_DIR/payload"
P="$BUNDLE_DIR/payload"

log "building agent image"
docker build -f "$ROOT/agent/Dockerfile" -t "$AGENT_IMAGE" "$ROOT"

log "building model image ($GEN_MODEL + $EMBED_MODEL baked in) - this downloads the weights"
docker build -f "$ROOT/scripts/ollama-models.Dockerfile" \
  --build-arg OLLAMA_IMAGE="$OLLAMA_BASE" --build-arg GEN_MODEL="$GEN_MODEL" --build-arg EMBED_MODEL="$EMBED_MODEL" \
  -t "$MODELS_IMAGE" "$ROOT/scripts"

log "pulling $QDRANT_IMAGE"
docker pull "$QDRANT_IMAGE"

log "exporting images"
docker save "$AGENT_IMAGE" "$MODELS_IMAGE" "$QDRANT_IMAGE" -o "$P/images.tar"

log "packaging chart and scripts"
helm package "$ROOT/charts/airgap-agent" --version "$VERSION" --app-version "$VERSION" -d "$P" >/dev/null
mkdir -p "$P/scripts" "$P/kind"
cp "$ROOT"/scripts/{lib.sh,load-bundle.sh,block-egress.sh,preflight.sh} "$P/scripts/"
cp "$ROOT/kind/cluster.yaml" "$P/kind/"
cp -r "$ROOT/agent" "$P/agent-src"   # for python -m app.preflight on the operator machine
rm -rf "$P/agent-src/tests" "$P/agent-src/.ruff_cache" "$P/agent-src/__pycache__"

( cd "$P" && find . -type f ! -name MANIFEST.sha256 -print0 | sort -z | xargs -0 sha256sum > MANIFEST.sha256 )
cat >"$P/VERSION" <<V
version=$VERSION
gen_model=$GEN_MODEL
embed_model=$EMBED_MODEL
built=$(date -u +%FT%TZ)
V

tar -C "$BUNDLE_DIR" -cf "$BUNDLE_DIR/airgap-bundle.tar" payload
( cd "$BUNDLE_DIR" && sha256sum airgap-bundle.tar > airgap-bundle.tar.sha256 )
log "bundle ready: $BUNDLE_DIR/airgap-bundle.tar ($(du -h "$BUNDLE_DIR/airgap-bundle.tar" | cut -f1))"
