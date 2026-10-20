"""Invariants the air-gap story depends on, asserted against the rendered chart (needs `helm` on PATH)."""

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

CHART = Path(__file__).resolve().parents[1] / "airgap-agent"
pytestmark = pytest.mark.skipif(shutil.which("helm") is None, reason="helm not installed")


def render(*sets: str) -> list[dict]:
    args = ["helm", "template", "t", str(CHART), "-n", "airgap"]
    for s in sets:
        args += ["--set", s]
    out = subprocess.run(args, capture_output=True, text=True, check=True).stdout
    return [d for d in yaml.safe_load_all(out) if d]


def of_kind(docs, kind):
    return [d for d in docs if d["kind"] == kind]


def pod_specs(docs):
    for d in docs:
        if d["kind"] in ("Deployment", "StatefulSet", "Job"):
            yield d["metadata"]["name"], d["spec"]["template"]["spec"]


def test_default_deny_policy_covers_all_pods_both_directions():
    deny = [p for p in of_kind(render(), "NetworkPolicy") if p["metadata"]["name"].endswith("default-deny")]
    assert len(deny) == 1
    spec = deny[0]["spec"]
    assert spec["podSelector"] == {}
    assert set(spec["policyTypes"]) == {"Ingress", "Egress"}
    assert "egress" not in spec and "ingress" not in spec


def test_no_policy_allows_egress_to_anywhere():
    for pol in of_kind(render("netpol.apiServerCIDR=10.0.0.1/32"), "NetworkPolicy"):
        for rule in pol["spec"].get("egress", []):
            assert rule.get("to"), f"{pol['metadata']['name']} has an allow-all egress rule"
            for peer in rule["to"]:
                assert peer.get("ipBlock", {}).get("cidr") not in ("0.0.0.0/0", "::/0")


def test_api_server_egress_is_a_single_host_cidr_and_off_by_default():
    assert "ipBlock" not in yaml.dump(of_kind(render(), "NetworkPolicy"))
    docs = render("netpol.apiServerCIDR=10.0.0.1/32")
    blocks = [p["ipBlock"]["cidr"] for pol in of_kind(docs, "NetworkPolicy") for r in pol["spec"].get("egress", []) for p in r["to"] if "ipBlock" in p]
    assert blocks == ["10.0.0.1/32"]


def test_netpol_can_be_disabled():
    assert of_kind(render("netpol.enabled=false"), "NetworkPolicy") == []


def test_only_clients_reach_backends():
    pol = next(p for p in of_kind(render(), "NetworkPolicy") if p["metadata"]["name"].endswith("backends-ingress"))
    assert pol["spec"]["ingress"] == [{"from": [{"podSelector": {"matchLabels": {"airgap/role": "client"}}}]}]


def test_every_pod_runs_non_root_and_drops_privileges():
    for name, spec in pod_specs(render()):
        assert spec["securityContext"]["runAsNonRoot"] is True, name
        for c in spec["containers"]:
            sc = c["securityContext"]
            assert sc["allowPrivilegeEscalation"] is False, f"{name}/{c['name']}"
            assert sc["capabilities"]["drop"] == ["ALL"], f"{name}/{c['name']}"


def test_agent_and_ingest_have_read_only_rootfs():
    for name, spec in pod_specs(render()):
        if "agent" in name or "ingest" in name:
            assert all(c["securityContext"]["readOnlyRootFilesystem"] for c in spec["containers"]), name


def test_images_are_pinned_not_latest():
    for name, spec in pod_specs(render()):
        for c in spec["containers"]:
            assert ":" in c["image"] and not c["image"].endswith(":latest"), f"{name}: {c['image']}"


def test_pull_policy_never_forces_a_registry_pull():
    for _, spec in pod_specs(render()):
        assert all(c["imagePullPolicy"] in ("IfNotPresent", "Never") for c in spec["containers"])


def test_api_key_comes_from_a_secret_never_a_literal():
    docs = render()
    agent = next(s for n, s in pod_specs(docs) if n.endswith("-agent"))
    env = {e["name"]: e for e in agent["containers"][0]["env"]}
    assert "value" not in env["AGENT_API_KEY"] and "secretKeyRef" in env["AGENT_API_KEY"]["valueFrom"]
    assert len(of_kind(docs, "Secret")) == 1


def test_existing_secret_is_used_and_no_secret_is_generated():
    docs = render("secret.existingSecret=my-key")
    assert of_kind(docs, "Secret") == []
    agent = next(s for n, s in pod_specs(docs) if n.endswith("-agent"))
    ref = next(e for e in agent["containers"][0]["env"] if e["name"] == "AGENT_API_KEY")["valueFrom"]["secretKeyRef"]
    assert ref["name"] == "my-key"


def test_service_urls_stay_inside_the_namespace():
    for _, spec in pod_specs(render()):
        for c in spec["containers"]:
            for e in c.get("env", []):
                if e["name"].endswith("_URL"):
                    host = e["value"].split("//")[1].split(":")[0]
                    assert "." not in host, f"{e['name']} points outside the namespace: {host}"


def test_ingest_can_be_disabled():
    assert of_kind(render("ingest.enabled=false"), "Job") == []
    assert len(of_kind(render(), "Job")) == 1


def test_rbac_is_read_only_and_namespaced():
    docs = render()
    assert of_kind(docs, "ClusterRole") == []
    (role,) = of_kind(docs, "Role")
    assert all(set(r["verbs"]) <= {"get", "list"} for r in role["rules"])
