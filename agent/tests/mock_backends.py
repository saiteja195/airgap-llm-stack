"""In-memory stand-ins for Ollama + Qdrant, for tests and UI development without a cluster."""

import hashlib
import json
import math
import re

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

app = FastAPI()
DIM = 64
POINTS: dict[str, dict] = {}
GEN_MODEL = "gemma4:e2b"
EMBED_MODEL = "nomic-embed-text"


def _vec(text: str) -> list[float]:
    v = [0.0] * DIM
    for w in re.findall(r"[a-z0-9]+", text.lower()):
        v[int(hashlib.md5(w.encode()).hexdigest(), 16) % DIM] += 1.0
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


@app.get("/api/tags")
def tags():
    return {"models": [{"name": GEN_MODEL}, {"name": EMBED_MODEL + ":latest"}]}


@app.post("/api/embed")
async def embed(req: Request):
    body = await req.json()
    return {"embeddings": [_vec(t) for t in body["input"]]}


@app.post("/api/chat")
async def chat(req: Request):
    body = await req.json()
    ctx = body["messages"][-1]["content"]
    if body.get("format") == "json":  # gate classifier call
        label = "out_of_scope" if "capital of" in ctx.lower() else "in_scope"
        return {"message": {"content": json.dumps({"label": label, "confidence": 0.9})}}
    first = re.search(r"\[1\][^\n]*\n(.+)", ctx)
    text = (first.group(1) if first else "I don't know.")[:160] + " [1]"

    def gen():
        for w in text.split(" "):
            yield json.dumps({"message": {"content": w + " "}, "done": False}) + "\n"
        yield json.dumps({"done": True, "eval_count": len(text.split()), "eval_duration": int(1e9)}) + "\n"

    return StreamingResponse(gen(), media_type="application/x-ndjson")


@app.get("/collections/{name}")
def get_collection(name: str):
    if not POINTS:
        return StreamingResponse(iter([b"{}"]), status_code=404)
    return {"result": {"points_count": len(POINTS)}}


@app.put("/collections/{name}")
async def put_collection(name: str):
    return {"result": True}


@app.put("/collections/{name}/points")
async def upsert(name: str, req: Request):
    for p in (await req.json())["points"]:
        POINTS[p["id"]] = p
    return {"result": {"status": "completed"}}


@app.post("/collections/{name}/points/search")
async def search(name: str, req: Request):
    body = await req.json()
    q = body["vector"]
    scored = sorted(
        (
            {"score": sum(a * b for a, b in zip(q, p["vector"], strict=True)), "payload": p["payload"]}
            for p in POINTS.values()
        ),
        key=lambda h: -h["score"],
    )
    return {"result": scored[: body["limit"]]}
