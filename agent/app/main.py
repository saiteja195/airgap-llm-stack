import json
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field

from . import config
from .airgap import egress_report, network_policies
from .metrics import METRICS
from .preflight import runtime_checks
from .rag import answer_stream

STATIC = Path(__file__).resolve().parent.parent / "static"
app = FastAPI(title="airgap-llm-stack agent", docs_url=None, redoc_url=None)


def require_key(x_api_key: str = Header(default="")) -> None:
    if config.API_KEY and x_api_key != config.API_KEY:
        raise HTTPException(401, "invalid or missing X-API-Key")


class Ask(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


@app.get("/metrics", response_class=PlainTextResponse)
def metrics() -> str:
    return METRICS.prometheus()


@app.get("/api/meta", dependencies=[Depends(require_key)])
def meta() -> dict:
    return {
        "model": config.GEN_MODEL,
        "embed_model": config.EMBED_MODEL,
        "install_steps": config.INSTALL_STEPS,
        "auth_required": bool(config.API_KEY),
        **METRICS.snapshot(),
    }


@app.get("/api/auth-required")
def auth_required() -> dict:
    return {"auth_required": bool(config.API_KEY)}


@app.post("/api/ask", dependencies=[Depends(require_key)])
async def ask(body: Ask) -> StreamingResponse:
    async def gen():
        async for ev in answer_stream(body.question):
            yield json.dumps(ev) + "\n"

    return StreamingResponse(gen(), media_type="application/x-ndjson")


@app.get("/api/preflight", dependencies=[Depends(require_key)])
async def preflight() -> list[dict]:
    return await runtime_checks()


@app.get("/api/airgap", dependencies=[Depends(require_key)])
async def airgap() -> dict:
    return {"egress": await egress_report(), "network_policies": await network_policies()}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")
