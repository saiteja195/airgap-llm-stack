"""Environment preflight: tells you what a customer environment is missing.

Two groups share one result format:
  * runtime checks - run inside the agent pod (and by `/api/preflight`)
  * cluster checks - run from an operator's shell via kubectl (`python -m app.preflight --cluster`)
"""

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys

PASS, WARN, FAIL = "pass", "warn", "fail"


def check(id_: str, name: str, status: str, detail: str, fix: str = "") -> dict:
    return {"id": id_, "name": name, "status": status, "detail": detail, "fix": fix}


async def runtime_checks() -> list[dict]:
    # Imported lazily so `--cluster` works on an operator machine with only the Python stdlib.
    import httpx

    from . import config
    from .airgap import egress_report

    out: list[dict] = []

    eg = await egress_report()
    out.append(
        check(
            "egress-blocked",
            "Outbound internet is blocked",
            PASS if eg["airgapped"] else FAIL,
            "all probes failed" if eg["airgapped"] else f"reachable: {', '.join(eg['leaked'])}",
            ""
            if eg["airgapped"]
            else "Apply the default-deny egress NetworkPolicy and use a CNI that enforces it.",
        )
    )

    async with httpx.AsyncClient(timeout=5.0) as c:
        try:
            tags = (await c.get(f"{config.OLLAMA_URL}/api/tags")).json().get("models", [])
            names = {m["name"].split(":latest")[0] for m in tags}
            out.append(check("ollama", "Model server reachable", PASS, f"{len(names)} models loaded"))
            for label, model in (("generation", config.GEN_MODEL), ("embedding", config.EMBED_MODEL)):
                ok = model.split(":latest")[0] in names
                out.append(
                    check(
                        f"model-{label}",
                        f"{label.capitalize()} model present ({model})",
                        PASS if ok else FAIL,
                        "loaded" if ok else "not found in model server",
                        ""
                        if ok
                        else "Re-run scripts/load-bundle.sh; the bundle must include the model weights.",
                    )
                )
        except (httpx.HTTPError, ValueError) as e:
            out.append(
                check("ollama", "Model server reachable", FAIL, str(e), "Check the ollama pod and Service.")
            )
        try:
            r = await c.get(f"{config.QDRANT_URL}/collections/{config.COLLECTION}")
            if r.status_code == 200:
                n = r.json()["result"].get("points_count", 0)
                out.append(
                    check(
                        "vector-db",
                        "Vector DB populated",
                        PASS if n else WARN,
                        f"{n} chunks indexed",
                        ""
                        if n
                        else "Run the ingest Job: helm upgrade --install ... --set ingest.enabled=true",
                    )
                )
            else:
                out.append(
                    check(
                        "vector-db", "Vector DB populated", WARN, "collection missing", "Run the ingest Job."
                    )
                )
        except (httpx.HTTPError, ValueError) as e:
            out.append(
                check("vector-db", "Vector DB reachable", FAIL, str(e), "Check the qdrant pod and Service.")
            )

    out += resource_checks()
    return out


def resource_checks() -> list[dict]:
    out = []
    cpus = os.cpu_count() or 0
    out.append(
        check(
            "cpu",
            "CPU cores",
            PASS if cpus >= 4 else WARN,
            f"{cpus} visible",
            "4+ cores recommended for CPU inference.",
        )
    )
    try:
        mem_kb = int(next(ln for ln in open("/proc/meminfo") if ln.startswith("MemTotal")).split()[1])
        gb = mem_kb / 1024 / 1024
        out.append(
            check(
                "memory",
                "Memory",
                PASS if gb >= 8 else WARN,
                f"{gb:.1f} GiB",
                "8+ GiB recommended for the default model.",
            )
        )
    except (OSError, StopIteration, ValueError):
        pass
    free_gb = shutil.disk_usage("/").free / 1e9
    out.append(
        check(
            "disk",
            "Free disk",
            PASS if free_gb >= 10 else WARN,
            f"{free_gb:.1f} GB",
            "10+ GB needed for images and model weights.",
        )
    )
    return out


def _kubectl(*args: str) -> dict | None:
    try:
        r = subprocess.run(
            ["kubectl", *args, "-o", "json"], capture_output=True, text=True, timeout=20, check=True
        )
        return json.loads(r.stdout)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def cluster_checks() -> list[dict]:
    out: list[dict] = []
    if not shutil.which("kubectl"):
        return [
            check(
                "kubectl",
                "kubectl installed",
                FAIL,
                "not found on PATH",
                "Install kubectl matching your cluster version.",
            )
        ]
    out.append(check("kubectl", "kubectl installed", PASS, shutil.which("kubectl") or ""))
    if not shutil.which("helm"):
        out.append(
            check(
                "helm",
                "helm installed",
                FAIL,
                "not found on PATH",
                "Install Helm 3.12+ (ship the binary in the bundle).",
            )
        )
    else:
        out.append(check("helm", "helm installed", PASS, shutil.which("helm") or ""))

    ver = _kubectl("version")
    if not ver or "serverVersion" not in ver:
        out.append(
            check(
                "api-server",
                "Cluster reachable",
                FAIL,
                "kubectl cannot reach the API server",
                "Check kubeconfig/context.",
            )
        )
        return out
    sv = ver["serverVersion"]
    minor = int("".join(ch for ch in sv["minor"] if ch.isdigit()) or 0)
    out.append(
        check(
            "k8s-version",
            "Kubernetes >= 1.27",
            PASS if minor >= 27 else FAIL,
            f"v{sv['major']}.{sv['minor']}",
            "Upgrade the cluster.",
        )
    )

    sc = _kubectl("get", "storageclass")
    default = [
        i["metadata"]["name"]
        for i in (sc or {}).get("items", [])
        if i["metadata"].get("annotations", {}).get("storageclass.kubernetes.io/is-default-class") == "true"
    ]
    out.append(
        check(
            "storageclass",
            "Default StorageClass",
            PASS if default else FAIL,
            ", ".join(default) or "none",
            "Mark a StorageClass default or set persistence.storageClass in values.",
        )
    )

    pods = _kubectl("get", "pods", "-n", "kube-system")
    cni = sorted(
        {
            n
            for i in (pods or {}).get("items", [])
            for n in ("calico", "cilium", "antrea", "kindnet", "weave", "canal")
            if n in i["metadata"]["name"]
        }
    )
    enforcing = {"calico", "cilium", "antrea", "canal", "kindnet"}
    ok = any(c in enforcing for c in cni)
    out.append(
        check(
            "cni-netpol",
            "CNI enforces NetworkPolicy",
            PASS if ok else WARN,
            ", ".join(cni) or "unknown CNI",
            "Verify with the egress-blocked runtime check; flannel alone does NOT enforce policies.",
        )
    )

    nodes = _kubectl("get", "nodes")
    for n in (nodes or {}).get("items", []):
        mem = n["status"]["allocatable"]["memory"]
        gib = int(mem.rstrip("Ki")) / 1024 / 1024 if mem.endswith("Ki") else 0
        out.append(
            check(
                f"node-{n['metadata']['name']}",
                f"Node {n['metadata']['name']} memory",
                PASS if gib >= 8 else WARN,
                f"{gib:.1f} GiB allocatable",
                "8+ GiB recommended.",
            )
        )
    return out


def render(results: list[dict]) -> str:
    icon = {PASS: "PASS", WARN: "WARN", FAIL: "FAIL"}
    lines = []
    for r in results:
        lines.append(f"[{icon[r['status']]}] {r['name']}: {r['detail']}")
        if r["status"] != PASS and r["fix"]:
            lines.append(f"        fix: {r['fix']}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="airgap-llm-stack preflight")
    ap.add_argument("--cluster", action="store_true", help="kubectl-based cluster checks")
    ap.add_argument("--runtime", action="store_true", help="in-pod/runtime checks")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    results: list[dict] = []
    if args.cluster or not args.runtime:
        results += cluster_checks()
    if args.runtime or not args.cluster:
        results += asyncio.run(runtime_checks())
    print(json.dumps(results, indent=2) if args.json else render(results))
    return 1 if any(r["status"] == FAIL for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
