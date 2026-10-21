#!/usr/bin/env bash
# shellcheck disable=SC2034
# Shared helpers for the airgap-llm-stack scripts.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${VERSION:-0.1.0}"
GEN_MODEL="${GEN_MODEL:-gemma4:e2b}"
EMBED_MODEL="${EMBED_MODEL:-nomic-embed-text}"
CLUSTER="${CLUSTER:-airgap}"
NAMESPACE="${NAMESPACE:-airgap}"
RELEASE="${RELEASE:-airgap}"
BUNDLE_DIR="${BUNDLE_DIR:-$ROOT/bundle}"

log() { printf '\033[1;34m==>\033[0m %s\n' "$*" >&2; }
die() { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }
need() { for c in "$@"; do command -v "$c" >/dev/null 2>&1 || die "missing required tool: $c"; done; }
now() { date +%s.%N; }
elapsed() { awk -v a="$1" -v b="$(now)" 'BEGIN{printf "%.1f", b-a}'; }
