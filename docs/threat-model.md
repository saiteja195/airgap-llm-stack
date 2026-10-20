# Threat model (air-gap scope)

| Threat | Mitigation | Evidence |
|---|---|---|
| Data exfiltration from a pod | default-deny egress NetworkPolicy; only in-namespace backends reachable | console "Air-gap proof" probes public IPs and must show BLOCKED |
| Runtime fetches of models/images | weights and images ship in the bundle; `imagePullPolicy: IfNotPresent` | demo blocks node egress before loading the bundle |
| Tampered / corrupted bundle | SHA-256 manifest verified before any load | `scripts/load-bundle.sh` aborts on mismatch |
| Unauthenticated access | API key from a Kubernetes Secret (generated once, kept across upgrades) | `/api/*` returns 401 without `X-API-Key` |
| Container breakout surface | non-root, read-only rootfs (agent), dropped capabilities, seccomp RuntimeDefault | chart `securityContext` |

Out of scope (v0): bundle signing (cosign), mTLS between pods, multi-tenant isolation, CNI-specific policy validation beyond the empirical egress probe.
