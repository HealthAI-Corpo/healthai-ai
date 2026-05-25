FROM python:3.12-slim

# gcc requis pour compiler les extensions C de scikit-learn / numpy
RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

# UV (gestionnaire de paquets)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Bibliothèque partagée (client LLM Ollama commun) — résolue via ../healthai-common
COPY healthai-common /healthai-common

# Dépendances du micro-service
COPY healthai-workout/pyproject.toml healthai-workout/uv.lock* ./
# Sans --frozen pour éviter les conflits de lock Windows/Linux
RUN uv sync --no-dev

# Code source + artefacts modèles
COPY healthai-workout/src/ ./src/
COPY healthai-workout/models/ ./models/

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

EXPOSE 8002

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8002"]
