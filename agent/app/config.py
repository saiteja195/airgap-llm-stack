"""Runtime configuration, read from the environment (set by the Helm chart)."""

import os
import time

PROCESS_START = time.time()

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
GEN_MODEL = os.getenv("GEN_MODEL", "gemma4:e2b")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
COLLECTION = os.getenv("COLLECTION", "docs")
TOP_K = int(os.getenv("TOP_K", "4"))
API_KEY = os.getenv("AGENT_API_KEY", "")
INSTALL_STEPS = int(os.getenv("INSTALL_STEPS", "3"))
NAMESPACE = os.getenv("POD_NAMESPACE", "airgap")
# Hosts the air-gap probe must NOT be able to reach.
EGRESS_PROBES = [
    p.strip()
    for p in os.getenv("EGRESS_PROBES", "1.1.1.1:443,8.8.8.8:53,example.com:443").split(",")
    if p.strip()
]
