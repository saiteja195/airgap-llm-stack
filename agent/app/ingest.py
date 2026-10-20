"""CLI: python -m app.ingest /path/to/docs  (run by the chart's ingest Job)."""

import asyncio
import sys
from pathlib import Path

import httpx

from .rag import ingest_dir


async def main(root: str) -> None:
    async with httpx.AsyncClient(timeout=httpx.Timeout(600.0, connect=5.0)) as client:
        n = await ingest_dir(client, Path(root))
    print(f"ingested {n} chunks from {root}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "/corpus"))
