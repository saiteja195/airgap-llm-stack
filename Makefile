.DEFAULT_GOAL := help
PY ?= python3
.PHONY: help dev test chart-test lint chart-lint chart-template bundle preflight airgap-demo bench down

help: ## list targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

dev: ## run the UI against mock Ollama/Qdrant at http://localhost:8080 (no cluster needed)
	cd agent && $(PY) -m tests.run_dev

test: ## unit tests
	cd agent && $(PY) -m pytest -q

chart-test: ## rendered-chart invariants (needs helm)
	cd agent && $(PY) -m pytest -q ../charts/tests

lint: chart-lint ## ruff + helm lint + shell syntax
	cd agent && ruff check . && ruff format --check .
	for f in scripts/*.sh; do bash -n $$f; done

chart-lint: ## helm lint + render with every optional feature on
	helm lint charts/airgap-agent
	helm template t charts/airgap-agent --set monitoring.serviceMonitor.enabled=true --set monitoring.grafanaDashboard.enabled=true --set netpol.apiServerCIDR=10.0.0.1/32 >/dev/null

bundle: ## (connected machine) build bundle/airgap-bundle.tar
	scripts/bundle.sh

preflight: ## what is this environment missing?
	scripts/preflight.sh

airgap-demo: ## kind cluster -> block egress -> load bundle -> install -> first answer
	scripts/airgap-demo.sh

bench: ## tokens/sec + latency against the running deployment
	scripts/bench.sh

down: ## delete the kind cluster
	kind delete cluster --name $${CLUSTER:-airgap}
