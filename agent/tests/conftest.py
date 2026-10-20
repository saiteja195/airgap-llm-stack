import socket
import threading
import time

import pytest
import uvicorn

from . import mock_backends


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def backends():
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(mock_backends.app, port=port, log_level="warning"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    while not server.started:
        time.sleep(0.05)
    from app import config

    config.OLLAMA_URL = config.QDRANT_URL = f"http://127.0.0.1:{port}"
    yield
    server.should_exit = True
