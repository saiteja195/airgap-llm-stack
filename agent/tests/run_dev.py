"""Dev server: mock Ollama/Qdrant on :11500 and the real agent on :8080 (no cluster needed)."""

import asyncio
import threading
import time
from pathlib import Path

import httpx
import uvicorn

from app import config
from app.rag import ingest_dir

from . import mock_backends

config.OLLAMA_URL = config.QDRANT_URL = "http://127.0.0.1:11500"


def main() -> None:
    mock = uvicorn.Server(uvicorn.Config(mock_backends.app, port=11500, log_level="warning"))
    threading.Thread(target=mock.run, daemon=True).start()
    while not mock.started:
        time.sleep(0.05)

    async def seed():
        async with httpx.AsyncClient() as c:
            return await ingest_dir(c, Path(__file__).resolve().parents[2] / "docs-corpus")

    print("seeded", asyncio.run(seed()), "chunks; UI at http://127.0.0.1:8080")
    uvicorn.run("app.main:app", port=8080, log_level="warning")


if __name__ == "__main__":
    main()
