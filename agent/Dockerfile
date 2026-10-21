# Build from the repo root:  docker build -f agent/Dockerfile -t airgap/agent:dev .
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
COPY agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY agent/app ./app
COPY agent/static ./static
# Demo knowledge base; the ingest Job reads /corpus (override with ingest.corpusConfigMap).
COPY docs-corpus /corpus
RUN useradd -u 10001 -r agent
USER 10001
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
