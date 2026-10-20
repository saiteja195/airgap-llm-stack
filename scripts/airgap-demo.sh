#!/usr/bin/env bash
# End-to-end rehearsal: kind cluster -> block egress -> load bundle -> install -> first answer.
# Writes timings to bench/results.json. Needs: docker, kind, kubectl, helm, python3, and a built bundle (make bundle).
# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"
need docker kind kubectl helm python3
TAR="$BUNDLE_DIR/airgap-bundle.tar"
[[ -f "$TAR" ]] || die "no bundle at $TAR - run 'make bundle' on a connected machine first"
QUESTION="${QUESTION:-How do I run the preflight checker?}"
INSTALL_STEPS=3   # customer-facing steps: preflight, load bundle, helm install

T0="$(now)"
log "1/6 creating kind cluster '$CLUSTER'"
kind get clusters | grep -qx "$CLUSTER" || kind create cluster --name "$CLUSTER" --config "$ROOT/kind/cluster.yaml" --wait 120s
kubectl config use-context "kind-$CLUSTER" >/dev/null

log "2/6 blocking egress (node-level) - nothing below may touch the internet"
"$ROOT/scripts/block-egress.sh"

log "3/6 preflight (cluster)"
"$ROOT/scripts/preflight.sh" || log "preflight reported failures above (continuing for the demo)"

log "4/6 loading offline bundle"
T_LOAD="$(now)"
"$ROOT/scripts/load-bundle.sh" --kind "$CLUSTER" "$TAR"
LOAD_S="$(elapsed "$T_LOAD")"

log "5/6 installing chart"
T_INSTALL="$(now)"
API_IP="$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$CLUSTER-control-plane")"
helm upgrade --install "$RELEASE" "$BUNDLE_DIR"/airgap-agent-*.tgz -n "$NAMESPACE" --create-namespace \
  --set agent.installSteps="$INSTALL_STEPS" --set netpol.apiServerCIDR="$API_IP/32" \
  --set model.generation="$GEN_MODEL" --set model.embedding="$EMBED_MODEL" --wait --timeout 15m
kubectl -n "$NAMESPACE" wait --for=condition=complete job -l app.kubernetes.io/component=ingest --timeout=10m
INSTALL_S="$(elapsed "$T_INSTALL")"

log "6/6 asking a question over the local docs"
KEY="$(kubectl -n "$NAMESPACE" get secret "$RELEASE-agent" -o jsonpath='{.data.api-key}' | base64 -d)"
kubectl -n "$NAMESPACE" port-forward "svc/$RELEASE-agent" 8080:8080 >/dev/null 2>&1 &
PF=$!; trap 'kill $PF 2>/dev/null || true' EXIT
for _ in $(seq 1 30); do curl -fsS localhost:8080/healthz >/dev/null 2>&1 && break; sleep 1; done
python3 "$ROOT/scripts/ask.py" http://localhost:8080 "$KEY" "$QUESTION"
FIRST_ANSWER_S="$(elapsed "$T_LOAD")"

mkdir -p "$ROOT/bench"
cat >"$ROOT/bench/results.json" <<J
{"load_bundle_s": $LOAD_S, "install_s": $INSTALL_S, "cold_start_to_first_answer_s": $FIRST_ANSWER_S, "install_steps": $INSTALL_STEPS, "model": "$GEN_MODEL"}
J
log "cold start (load -> first answer): ${FIRST_ANSWER_S}s | total demo: $(elapsed "$T0")s | results: bench/results.json"
log "console: http://localhost:8080  (API key: $KEY)  -- Ctrl-C to stop the port-forward; 'make down' removes the cluster"
wait "$PF"
