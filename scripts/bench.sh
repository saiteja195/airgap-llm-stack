#!/usr/bin/env bash
# Measure tokens/sec and latency against a running deployment (RUNS questions, default 5).
# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"
need kubectl python3
RUNS="${RUNS:-5}"
KEY="$(kubectl -n "$NAMESPACE" get secret "$RELEASE-agent" -o jsonpath='{.data.api-key}' | base64 -d)"
kubectl -n "$NAMESPACE" port-forward "svc/$RELEASE-agent" 8081:8080 >/dev/null 2>&1 &
PF=$!; trap 'kill $PF 2>/dev/null || true' EXIT
for _ in $(seq 1 30); do curl -fsS localhost:8081/healthz >/dev/null 2>&1 && break; sleep 1; done
QS=("How do I run the preflight checker?" "What does the network policy allow?" "How are secrets handled?" "What is in the offline bundle?" "Why are answers slow?")
OUT="$(mktemp)"
for i in $(seq 0 $((RUNS - 1))); do
  python3 "$ROOT/scripts/ask.py" http://localhost:8081 "$KEY" "${QS[$((i % ${#QS[@]}))]}" 2>>"$OUT" >/dev/null
done
python3 - "$OUT" <<'PY'
import json, statistics, sys
rows = [json.loads(l) for l in open(sys.argv[1]) if l.startswith("{")]
tps = [r["tokens_per_s"] for r in rows]
lat = [r["latency_s"] for r in rows]
print(json.dumps({"runs": len(rows), "tokens_per_s_median": statistics.median(tps), "latency_s_median": statistics.median(lat)}, indent=2))
PY
