# Architecture

```
            operator ──port-forward──▶ agent (FastAPI + console)
                                         │  │
                          /api/ask       │  └──▶ qdrant (StatefulSet, PVC)    vectors + chunks
                                         └─────▶ ollama (Deployment)          chat + embeddings, weights baked in image
   ingest Job ──embed──▶ ollama ──upsert──▶ qdrant            (runs on install; corpus baked into the agent image)
```

## Request path
1. `POST /api/ask` embeds the question (Ollama embed model), searches Qdrant top-k.
2. Citations are streamed first (NDJSON `citations` event), so the UI can show sources while the model is still generating.
3. Ollama `/api/chat` streams tokens; the final chunk carries `eval_count`/`eval_duration`, which gives tokens/sec without any estimation.
4. `done` event reports tokens, tokens/sec, latency; the same numbers feed `/metrics`.

## Why models are baked into an image
The cluster must never pull anything at runtime. `scripts/ollama-models.Dockerfile` runs `ollama pull` at build time on the connected machine, so shipping the bundle ships the weights, and the pod needs no PVC pre-seeding. Trade-off: a multi-GB image (`gemma4:e2b` alone is ~7.2 GB, so budget ~8 GB for the bundle and node image storage); swapping models means rebuilding that image (`GEN_MODEL=... make bundle`).

## Network policy model
Default-deny (ingress + egress) for the namespace, then explicit allows: clients -> DNS, clients -> qdrant:6333, clients -> ollama:11434, optional API-server egress (for the console's NetworkPolicy panel), and ingress to the agent from its namespace and the monitoring namespace. Qdrant and Ollama accept traffic only from pods labelled `airgap/role: client`.

## Preflight
One implementation, two entry points: `python -m app.preflight --cluster` (operator shell, stdlib + kubectl only) and `GET /api/preflight` (in-pod runtime checks, rendered in the console). Every non-passing check carries a remediation hint.

## Query gate (optional, off by default)
After retrieval and before generation, `app/gate.py` classifies the question as `in_scope`, `out_of_scope` or `injection`. Blocked questions get a canned refusal and never reach the generator, which saves the latency and tokens and keeps prompt-injection attempts away from the model. A `gate` event streams to the console with verdict, confidence, mode and cost.

| `agent.gate.mode` | How it decides | Notes |
|---|---|---|
| `off` | no gate | default |
| `similarity` | best retrieval score >= `minScore`; regex catches obvious injection phrasing | no extra model; tune `minScore` on real embeddings |
| `model` | asks `agent.gate.model` (via Ollama, JSON output) for a label and confidence | model must be in the bundle: `GATE_MODEL=<tag> make bundle`; fails open (answers) if the classifier errors, and reports the error |

`airgap_gate_verdicts_total{verdict=...}` is exported for dashboards. A dedicated Jev-style decision model is the intended `model`-mode backend once its input/output format is verified (issue #3).
