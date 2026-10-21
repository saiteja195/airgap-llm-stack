import asyncio
import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.preflight import PASS, resource_checks, runtime_checks
from app.rag import answer_stream, build_messages, chunk_markdown, ingest_dir

CORPUS = Path(__file__).resolve().parents[2] / "docs-corpus"


def test_chunk_markdown_splits_on_headings_and_size():
    text = "# A\n\none\n\n## B\n\n" + "x" * 500 + "\n\n" + "y" * 500
    chunks = chunk_markdown(text, max_chars=600)
    assert len(chunks) >= 3
    assert all(len(c) <= 1100 for c in chunks)
    assert chunks[0].startswith("# A")


def test_build_messages_numbers_citations():
    msgs = build_messages("q?", [{"n": 1, "source": "a.md", "text": "t"}])
    assert "[1] (a.md)" in msgs[1]["content"] and msgs[0]["role"] == "system"


@pytest.fixture
def ingested(backends):
    async def run():
        async with httpx.AsyncClient() as c:
            return await ingest_dir(c, CORPUS)

    assert asyncio.run(run()) > 0


def test_ask_streams_citations_tokens_done(ingested):
    async def run():
        return [e async for e in answer_stream("How do I run the preflight checker?")]

    events = asyncio.run(run())
    kinds = [e["type"] for e in events]
    assert kinds[0] == "citations" and kinds[-1] == "done" and "token" in kinds
    assert events[0]["citations"][0]["source"] == "runbook.md"
    assert events[-1]["tokens_per_s"] > 0


def test_api_ask_and_auth(ingested, monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr(config, "API_KEY", "secret")
    assert client.post("/api/ask", json={"question": "hi"}).status_code == 401
    r = client.post("/api/ask", json={"question": "network policy"}, headers={"X-API-Key": "secret"})
    assert r.status_code == 200
    assert json.loads(r.text.splitlines()[0])["type"] == "citations"
    assert "airgap_requests_total" in client.get("/metrics").text


def test_preflight_runtime_reports_models_and_vectors(ingested, monkeypatch):
    monkeypatch.setattr(config, "EGRESS_PROBES", ["127.0.0.1:1"])  # closed port == "blocked"
    results = {r["id"]: r for r in asyncio.run(runtime_checks())}
    assert results["egress-blocked"]["status"] == PASS
    assert results["model-generation"]["status"] == PASS
    assert results["vector-db"]["status"] == PASS


def test_preflight_flags_leaky_egress(backends, monkeypatch):
    # The mock backend port is open, so probing it simulates an egress leak.
    monkeypatch.setattr(config, "EGRESS_PROBES", [config.OLLAMA_URL.removeprefix("http://")])
    results = {r["id"]: r for r in asyncio.run(runtime_checks())}
    assert results["egress-blocked"]["status"] == "fail"
    assert results["egress-blocked"]["fix"]


def test_resource_checks_have_fix_text():
    assert all("fix" in r for r in resource_checks())
