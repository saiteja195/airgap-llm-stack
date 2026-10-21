# Customer runbook

This runbook is also the knowledge base the demo agent answers from.

## Install in three steps

1. Run the preflight checker: `make preflight`. Fix every FAIL before continuing.
2. Load the offline bundle: `scripts/load-bundle.sh bundle/airgap-bundle.tar`. This imports container images and model weights without touching the internet.
3. Install the chart: `helm upgrade --install airgap charts/airgap-agent -n airgap --create-namespace`.

For a full local rehearsal, `make airgap-demo` creates a kind cluster, blocks egress, loads the bundle and asks a first question.

## Preflight checker

The preflight checker reports what a customer environment is missing. Cluster checks cover the Kubernetes version (1.27 or newer), a default StorageClass, a CNI that enforces NetworkPolicy, and node memory. Runtime checks cover model availability, vector database contents, free disk, and whether outbound internet is truly blocked. Every non-passing check prints a fix hint. Run it with `python -m app.preflight --cluster` from an operator shell or open the Preflight panel in the console.

## Network policy

The chart applies a default-deny egress policy to every pod in the namespace. It then allows only: the agent talking to Qdrant and Ollama, DNS lookups to kube-dns, and Prometheus scraping the agent metrics port. No pod is allowed to reach the internet. The Air-gap proof panel actively probes public addresses such as 1.1.1.1:443 and must show BLOCKED for each.

## Offline bundle

`scripts/bundle.sh` runs once on a connected machine. It pulls the container images, exports them with `docker save`, downloads the model weights, packages the Helm chart, and writes a SHA-256 manifest. Copy `airgap-bundle.tar` across the air gap. `scripts/load-bundle.sh` verifies the checksums before loading anything, so a corrupted transfer fails fast.

## Secrets

The API key is generated at install time and stored in a Kubernetes Secret. It is never written to values files or logs. Retrieve it with `kubectl get secret airgap-agent -n airgap -o jsonpath='{.data.api-key}' | base64 -d`.

## Troubleshooting

If the agent says it does not know, check that the ingest Job completed and that the vector database reports indexed chunks in the Preflight panel. If answers are slow, check node CPU and memory; the default model needs about 8 GiB of memory for comfortable CPU inference. If images fail to pull with ErrImagePull, the bundle was not loaded on every node.
