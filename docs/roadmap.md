# Development roadmap

Work top to bottom. Each task is one branch (`<type>/<name>`), merged to `main` only when its checks pass. Tasks marked **[your machine]** need Docker, kind and a real cluster; **[anywhere]** can be done in a cloud session or on a laptop with only Python.

Standing checks for every task: `make test lint` (plus `make chart-lint chart-test` if the chart or scripts changed), then update the README **Status** table so nothing is claimed that has not been run.

Legend: `Needs` = tasks that must be finished first. `Done when` = the acceptance check.

---

## Phase 0 - Prove the baseline

Nothing later is trustworthy until this phase is done.

- [ ] **T01 First real run of the demo** [your machine]
  Branch: `fix/demo-first-run` (as many `fix/...` branches as the run needs). Related: issue #2.
  Needs: none.
  Do: `make bundle`, `make airgap-demo`, `make bench`. Fix whatever breaks (image names, non-root Ollama, probes, NetworkPolicy API egress, port-forward).
  Done when: the demo finishes unattended; preflight has no FAIL; every egress probe shows BLOCKED; the first answer has citations; `bench/results.json` exists.

- [ ] **T02 Record the first benchmark numbers** [your machine]
  Branch: `docs/benchmarks-first-run`.
  Needs: T01.
  Do: fill `docs/benchmarks.md` and the README metrics table (hardware, model, cold start to first answer, tokens/sec median, install steps).
  Done when: the README table has no "not yet measured" cells.

- [ ] **T03 Confirm kind enforces NetworkPolicy** [your machine]
  Branch: `feat/kind-calico` (only if needed).
  Needs: T01.
  Do: from a pod, test an allowed and a denied connection with the node-level block temporarily off. If kindnet does not enforce policies, add a Calico option (`CNI=calico make airgap-demo`) with its images in the bundle.
  Done when: the policies are shown to block traffic on their own, and the result is written into `docs/threat-model.md`.

- [ ] **T04 Choose the default model** [your machine]
  Branch: `chore/default-model`. Related: issue #1.
  Needs: T01.
  Do: measure Gemma 4 E2B against one smaller and one larger model on CPU (tokens/sec, answer quality on 10 questions, bundle size). Pick one.
  Done when: the model name is changed in all three places (`scripts/lib.sh`, `charts/airgap-agent/values.yaml`, `agent/app/config.py`) and the choice and numbers are recorded in `docs/benchmarks.md`.

## Phase 1 - Make the air gap trustworthy

- [ ] **T05 Image-presence preflight** [anywhere]
  Branch: `feat/preflight-images`.
  Needs: none (verify on a cluster in T01 follow-up).
  Do: a cluster check that every image the chart uses is present on every node, naming the missing ones and the fix command.
  Done when: unit-tested against fake `kubectl` JSON; a deliberately missing image shows a FAIL with a fix hint.

- [ ] **T06 Pin the Ollama base image by digest** [anywhere]
  Branch: `chore/pin-ollama-digest`.
  Needs: none.
  Do: default `OLLAMA_BASE` to a pinned tag or digest; make `bundle.sh` fail if the resolved digest differs from the pin; record it in the bundle `VERSION`.
  Done when: two bundle builds a day apart are reproducible in image digests.

- [ ] **T07 Sign and verify the bundle** [anywhere, then your machine]
  Branch: `feat/bundle-signing`.
  Needs: T06.
  Do: sign `airgap-bundle.tar` with cosign (key-based, no network at verify time); `load-bundle.sh` verifies the signature before checksums.
  Done when: a tampered bundle is rejected with a clear message; the verification key ships in the bundle docs.

- [ ] **T08 Encrypt traffic to the console** [your machine]
  Branch: `feat/tls-ingress`.
  Needs: T01.
  Do: optional ingress with a self-signed or customer-supplied certificate; document how to rotate it.
  Done when: the console works over HTTPS and the API key is never sent over plain HTTP in the documented install.

- [ ] **T09 Independent proof of isolation** [your machine]
  Branch: `feat/egress-audit`.
  Needs: T03.
  Do: a script that captures traffic on the node during a demo run and reports any connection leaving the cluster network.
  Done when: the report is empty for a clean run and flags a deliberately leaked connection.

## Phase 2 - Answer quality

- [ ] **T10 Retrieval evaluation set** [anywhere, final numbers on your machine]
  Branch: `test/retrieval-eval`.
  Needs: T04.
  Do: 30+ questions with the expected source document, a script that reports hit rate at k and groundedness, a baseline committed to `docs/evals.md`.
  Done when: `make eval` prints the metrics and CI fails if hit rate drops more than an agreed margin.

- [ ] **T11 Better chunking** [anywhere]
  Branch: `feat/chunking-overlap`.
  Needs: T10.
  Do: overlap between chunks, heading path as metadata, and a size cap tuned on the eval set.
  Done when: the eval hit rate improves, with before and after numbers recorded.

- [ ] **T12 Hybrid search and reranking** [anywhere]
  Branch: `feat/hybrid-search`.
  Needs: T10, T11.
  Do: combine keyword and vector scores; optionally a small offline reranker (bundled).
  Done when: the eval improves again; the added bundle size and latency are recorded.

- [ ] **T13 Tune the query gate and vet Jev-style models** [your machine]
  Branch: `feat/gate-tuning`. Related: issue #3.
  Needs: T10, T04.
  Do: tune `minScore` on real embeddings using in-scope and off-topic eval questions; check licence, accuracy and Ollama loadability of the small Jev-style models; wire one in only if it beats the similarity gate.
  Done when: false-block rate and miss rate are measured and recorded; the default `agent.gate.mode` is chosen from data.

- [ ] **T14 Customer documents without rebuilding the image** [anywhere]
  Branch: `feat/doc-ingest`.
  Needs: T11.
  Do: ingest from a ConfigMap or PVC; add PDF and docx text extraction (offline libraries, added to the bundle); show indexed documents in the console.
  Done when: a customer adds a PDF and gets cited answers without a new image.

## Phase 3 - Operations

- [ ] **T15 Bundled observability** [your machine]
  Branch: `feat/observability-bundle`. Related: issue #4.
  Needs: T01.
  Do: ship Prometheus and Grafana images in the bundle with a values file; import the dashboard into a real Grafana and fix what is wrong; add the alert rules to a real Alertmanager test.
  Done when: the demo shows live dashboards and a forced failure fires an alert.

- [ ] **T16 Support bundle** [anywhere]
  Branch: `feat/diagnose`.
  Needs: none.
  Do: `make diagnose` collects pod state, logs, events, preflight output and chart values (secrets redacted) into one archive for the customer to send.
  Done when: unit-tested redaction; running it against the demo cluster produces a complete archive.

- [ ] **T17 Upgrade and rollback path** [your machine]
  Branch: `test/upgrade-path`.
  Needs: T01, T07.
  Do: build bundle v0.1.0 and v0.2.0; upgrade in place; roll back; define what happens to the Qdrant data and the ingest Job.
  Done when: an automated script upgrades and rolls back with documents still answerable.

- [ ] **T18 Hardware profiles** [your machine]
  Branch: `feat/resource-profiles`.
  Needs: T04.
  Do: values files for laptop, CPU server and GPU node; the vLLM GPU profile deferred earlier; sensible requests and limits for each.
  Done when: each profile installs on matching hardware and its tokens/sec is in `docs/benchmarks.md`.

## Phase 4 - Showcase

- [ ] **T19 Demo recording and benchmark write-up** [your machine]
  Branch: `docs/demo-showcase`.
  Needs: T02, T15.
  Do: a 2-minute screen recording of `make airgap-demo`, an updated screenshot, and a benchmark table with hardware.
  Done when: the README leads with the recording and the table.

- [ ] **T20 Customer runbook** [anywhere]
  Branch: `docs/customer-runbook`.
  Needs: T01, T17.
  Do: rewrite `docs/` as a handover pack: prerequisites, install, verification, upgrade, troubleshooting built from the failures actually hit.
  Done when: someone who has not seen the project can install it from the runbook alone.

- [ ] **T21 Multi-turn conversations** (optional) [anywhere]
  Branch: `feat/conversation-memory`.
  Needs: T10.
  Do: keep the last few turns in the request, with a token budget, and rewrite follow-up questions before retrieval.
  Done when: follow-up questions like "and the second step?" retrieve correctly, shown by eval cases.

---

## Tracking

| Issue | Covered by |
|---|---|
| #1 Verify default model | T04 |
| #2 Run the demo end to end | T01, T02, T03 |
| #3 Jev decision-model gate | T13 |
| #4 Observability | T15 |

Suggested first week: T01 → T02 → T03 → T04, then T05, T06 and T10 in parallel branches.
