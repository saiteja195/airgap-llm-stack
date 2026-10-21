"""Air-gap evidence: active egress probes and the NetworkPolicies enforcing them."""

import asyncio
import os
import ssl
import time

import httpx

from . import config

SA_DIR = "/var/run/secrets/kubernetes.io/serviceaccount"


async def probe(target: str, timeout: float = 2.0) -> dict:
    """Try a TCP connect to host:port. In a correctly air-gapped cluster this must fail."""
    host, _, port = target.rpartition(":")
    t0 = time.perf_counter()
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, int(port)), timeout)
        writer.close()
        return {"target": target, "reachable": True, "ms": round((time.perf_counter() - t0) * 1000)}
    except (OSError, TimeoutError) as e:
        return {"target": target, "reachable": False, "reason": type(e).__name__}


async def egress_report() -> dict:
    results = await asyncio.gather(*(probe(t) for t in config.EGRESS_PROBES))
    leaked = [r["target"] for r in results if r["reachable"]]
    return {"airgapped": not leaked, "leaked": leaked, "probes": results}


async def network_policies() -> dict:
    """List NetworkPolicies in our namespace via the in-cluster API (needs the chart's Role)."""
    token_path = f"{SA_DIR}/token"
    if not os.path.exists(token_path):
        return {"available": False, "reason": "not running in a cluster", "policies": []}
    token = open(token_path).read().strip()
    ctx = ssl.create_default_context(cafile=f"{SA_DIR}/ca.crt")
    url = (
        f"https://kubernetes.default.svc/apis/networking.k8s.io/v1/namespaces/"
        f"{config.NAMESPACE}/networkpolicies"
    )
    try:
        async with httpx.AsyncClient(verify=ctx, timeout=5.0) as c:
            r = await c.get(url, headers={"Authorization": f"Bearer {token}"})
            r.raise_for_status()
    except httpx.HTTPError as e:
        return {"available": False, "reason": f"{type(e).__name__}: {e}", "policies": []}
    policies = []
    for item in r.json().get("items", []):
        spec = item["spec"]
        policies.append(
            {
                "name": item["metadata"]["name"],
                "types": spec.get("policyTypes", []),
                "selector": spec.get("podSelector", {}).get("matchLabels") or "all pods",
                "egress_rules": len(spec.get("egress", [])),
            }
        )
    return {"available": True, "policies": policies}
