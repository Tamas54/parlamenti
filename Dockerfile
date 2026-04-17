# ===========================================================================
# Parlamentaris Kompendium MCP — Dockerfile
# ===========================================================================
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Rendszerfüggőségek (Sprint 3-ban kellhet chromadb-hez)
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     build-essential \
#     && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src/ ./src/

ENV PYTHONPATH=/app/src
ENV HOST=0.0.0.0
ENV PORT=8000

EXPOSE 8000

CMD ["python", "src/server.py"]
