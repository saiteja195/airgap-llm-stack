# Ollama with model weights baked in, so the cluster never pulls anything at runtime.
# Built ONLY on the connected machine by scripts/bundle.sh.
ARG OLLAMA_IMAGE=ollama/ollama:latest
FROM ${OLLAMA_IMAGE}
ARG GEN_MODEL
ARG EMBED_MODEL
ENV OLLAMA_MODELS=/models
RUN ollama serve & \
    for i in $(seq 1 30); do ollama list >/dev/null 2>&1 && break; sleep 1; done; \
    ollama pull "${GEN_MODEL}" && ollama pull "${EMBED_MODEL}" && \
    chmod -R a+rX /models && kill %1 || true
