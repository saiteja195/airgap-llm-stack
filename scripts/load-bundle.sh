#!/usr/bin/env bash
# Verify and load the offline bundle on the air-gapped side. Makes NO network calls.
#   load-bundle.sh [--kind NAME | --ctr] [path/to/airgap-bundle.tar]
#     --kind NAME  import images into every node of the kind cluster NAME (default when kind is present)
#     --ctr        import into the local containerd (k3s/kubeadm node; run on every node)
# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"
MODE="kind"; TARGET="$CLUSTER"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --kind) MODE=kind; TARGET="$2"; shift 2 ;;
    --ctr) MODE=ctr; shift ;;
    *) TAR="$1"; shift ;;
  esac
done
TAR="${TAR:-$BUNDLE_DIR/airgap-bundle.tar}"
[[ -f "$TAR" ]] || die "bundle not found: $TAR"

WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
log "extracting $TAR"
tar -C "$WORK" -xf "$TAR"
log "verifying checksums"
( cd "$WORK/payload" && sha256sum --quiet -c MANIFEST.sha256 ) || die "checksum mismatch: the transfer is corrupt, re-copy the bundle"

case "$MODE" in
  kind) need kind; log "loading images into kind cluster '$TARGET'"; kind load image-archive "$WORK/payload/images.tar" --name "$TARGET" ;;
  ctr)  need ctr;  log "importing images into containerd";           ctr -n k8s.io images import "$WORK/payload/images.tar" ;;
esac
mkdir -p "$BUNDLE_DIR" && cp "$WORK"/payload/airgap-agent-*.tgz "$BUNDLE_DIR/"
log "images loaded; chart copied to $BUNDLE_DIR"
