# airgap-llm-stack

**Deploy an LLM agent stack into a locked-down Kubernetes cluster with no outbound internet.**
Agent API + vector DB + local model server, shipped as a Helm chart with an offline image bundle and a preflight checker that tells you what a customer environment is missing.

![console](docs/img/console.png)

| Component | Choice |
|---|---|
| Agent API + console UI | FastAPI, one static page, no build step, no CDN assets |
| Local model | [Ollama](https://ollama.com) serving Gemma 4 E2B (CPU-friendly), weights baked into the image |
| Vector DB | Qdrant |
| Isolation | default-deny NetworkPolicies, node-level egress block in the demo, non-root + read-only rootfs, generated API key |
| Observability | `/metrics` (Prometheus), ServiceMonitor, Grafana dashboard ConfigMap |

## Quickstart

```bash
make dev            # console at http://localhost:8080 against mock backends - no cluster, no model
make test lint      # unit tests, ruff, helm lint, shell syntax

# on a connected machine
make bundle         # -> bundle/airgap-bundle.tar (images, model weights, chart, scripts, SHA-256 manifest)

# on the demo machine (docker, kind, kubectl, helm)
make airgap-demo    # kind up -> block egress -> preflight -> load bundle -> install -> first answer
make bench          # tokens/sec + latency against the running stack
make down
```

## What a customer does (3 steps)

1. `make preflight` - fix every FAIL.
2. `scripts/load-bundle.sh airgap-bundle.tar` - verifies checksums, then imports images; makes no network calls.
3. `helm upgrade --install airgap airgap-agent-*.tgz -n airgap --create-namespace`

## Metrics

| Metric | Where it comes from | Result |
|---|---|---|
| Cold start to first answer | `scripts/airgap-demo.sh` (bundle load + install + first answer) -> `bench/results.json` | _not yet measured_ |
| Tokens/sec on the local model | agent `/metrics` (`airgap_tokens_per_second`), `make bench` | _not yet measured_ |
| Install steps | fixed at 3; shown in the console | 3 |

Numbers will be recorded in [docs/benchmarks.md](docs/benchmarks.md) with hardware and model details once measured on a real cluster.

## Status

| Piece | State |
|---|---|
| Agent API, console UI, tests | working; tested against mock Ollama/Qdrant |
| Helm chart | `helm lint` + `helm template` clean; **not yet installed on a real cluster** |
| bundle / load / demo scripts | written, syntax-checked; **not yet run end to end** |
| Model tag (`gemma4:e2b`) | placeholder - confirm the exact Ollama tag and CPU speed |
| CNI NetworkPolicy enforcement on kind | unverified; the demo also blocks egress at the node level |
| Query gate (`agent.gate.mode`: off / similarity / model) | implemented and unit-tested against mocks; default **off**; the similarity threshold (0.45) is untuned on real embeddings |
| Jev decision model as the gate | not vetted; any Ollama-served classifier can be set as `agent.gate.model`, a Jev-style one needs its I/O format checked first (#3) |

See [docs/architecture.md](docs/architecture.md) and [docs/threat-model.md](docs/threat-model.md).
