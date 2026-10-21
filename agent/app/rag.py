"""Retrieval-augmented answering over Qdrant + Ollama, using plain REST (no heavy SDKs)."""

import json
import re
import time
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import httpx

from . import config, gate
from .metrics import METRICS

SYSTEM_PROMPT = (
    "You are an assistant running inside an air-gapped environment. Answer ONLY from the "
    "provided context. If the context does not contain the answer, say you don't know. "
    "Be concise and cite sources as [n]."
)


def chunk_markdown(text: str, max_chars: int = 800) -> list[str]:
    """Split on headings/paragraphs, packing paragraphs up to max_chars."""
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    chunks, cur = [], ""
    for b in blocks:
        if cur and (len(cur) + len(b) > max_chars or b.startswith("#")):
            chunks.append(cur)
            cur = ""
        cur = f"{cur}\n\n{b}".strip()
    if cur:
        chunks.append(cur)
    return chunks


async def embed(client: httpx.AsyncClient, texts: list[str]) -> list[list[float]]:
    r = await client.post(
        f"{config.OLLAMA_URL}/api/embed", json={"model": config.EMBED_MODEL, "input": texts}
    )
    r.raise_for_status()
    return r.json()["embeddings"]


async def ensure_collection(client: httpx.AsyncClient, dim: int) -> None:
    url = f"{config.QDRANT_URL}/collections/{config.COLLECTION}"
    if (await client.get(url)).status_code == 200:
        return
    r = await client.put(url, json={"vectors": {"size": dim, "distance": "Cosine"}})
    r.raise_for_status()


async def ingest_dir(client: httpx.AsyncClient, root: Path) -> int:
    """Embed every .md file under root and upsert into Qdrant. Idempotent (deterministic ids)."""
    points = []
    for path in sorted(root.rglob("*.md")):
        rel = str(path.relative_to(root))
        for i, chunk in enumerate(chunk_markdown(path.read_text(encoding="utf-8"))):
            points.append((rel, i, chunk))
    if not points:
        return 0
    vectors = await embed(client, [p[2] for p in points])
    await ensure_collection(client, len(vectors[0]))
    body = {
        "points": [
            {
                "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{rel}#{i}")),
                "vector": vec,
                "payload": {"source": rel, "chunk": i, "text": text},
            }
            for (rel, i, text), vec in zip(points, vectors, strict=True)
        ]
    }
    r = await client.put(f"{config.QDRANT_URL}/collections/{config.COLLECTION}/points?wait=true", json=body)
    r.raise_for_status()
    return len(points)


async def retrieve(client: httpx.AsyncClient, question: str) -> list[dict]:
    [vec] = await embed(client, [question])
    r = await client.post(
        f"{config.QDRANT_URL}/collections/{config.COLLECTION}/points/search",
        json={"vector": vec, "limit": config.TOP_K, "with_payload": True},
    )
    r.raise_for_status()
    return [
        {"n": i + 1, "source": h["payload"]["source"], "text": h["payload"]["text"], "score": h["score"]}
        for i, h in enumerate(r.json()["result"])
    ]


def build_messages(question: str, hits: list[dict]) -> list[dict]:
    context = "\n\n".join(f"[{h['n']}] ({h['source']})\n{h['text']}" for h in hits)
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
    ]


async def answer_stream(question: str) -> AsyncIterator[dict]:
    """Yield events: citations, token*, done (with timing). Errors become an error event."""
    t0 = time.perf_counter()
    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=5.0)) as client:
        try:
            hits = await retrieve(client, question)
            yield {"type": "citations", "citations": hits}
            verdict = await gate.evaluate(client, question, hits)
            if verdict:
                METRICS.record_gate(verdict["verdict"])
                yield {"type": "gate", **verdict}
                if verdict["verdict"] != gate.IN_SCOPE:
                    total = time.perf_counter() - t0
                    METRICS.record_answer(0, 0.0, total, time.time() - config.PROCESS_START)
                    yield {"type": "token", "text": gate.REFUSALS[verdict["verdict"]]}
                    yield {
                        "type": "done",
                        "tokens": 0,
                        "tokens_per_s": 0,
                        "latency_s": round(total, 3),
                        "gated": True,
                    }
                    return
            payload = {
                "model": config.GEN_MODEL,
                "messages": build_messages(question, hits),
                "stream": True,
            }
            tokens, gen_s = 0, 0.0
            async with client.stream("POST", f"{config.OLLAMA_URL}/api/chat", json=payload) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line:
                        continue
                    chunk = json.loads(line)
                    if chunk.get("done"):
                        tokens = chunk.get("eval_count", 0)
                        gen_s = chunk.get("eval_duration", 0) / 1e9
                        break
                    piece = chunk.get("message", {}).get("content", "")
                    if piece:
                        yield {"type": "token", "text": piece}
            total = time.perf_counter() - t0
            METRICS.record_answer(tokens, gen_s, total, time.time() - config.PROCESS_START)
            yield {
                "type": "done",
                "tokens": tokens,
                "tokens_per_s": round(tokens / gen_s, 2) if gen_s else 0,
                "latency_s": round(total, 3),
            }
        except (httpx.HTTPError, KeyError, json.JSONDecodeError) as e:
            METRICS.record_error()
            yield {"type": "error", "message": f"{type(e).__name__}: {e}"}
