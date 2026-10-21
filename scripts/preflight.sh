#!/usr/bin/env bash
# Operator-side preflight. Needs only python3 and kubectl; no pip installs (stdlib + httpx are NOT required for --cluster).
# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"
SRC="$ROOT/agent"; [[ -d "$ROOT/agent-src" ]] && SRC="$ROOT/agent-src"
need python3
cd "$SRC" && exec python3 -m app.preflight --cluster "$@"
