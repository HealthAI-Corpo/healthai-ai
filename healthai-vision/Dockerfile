FROM python:3.12-slim

# 1. Installation des dépendances système nécessaires pour OpenCV et le compilateur
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 2. Installation de UV globalement dans l'image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# 3. Injection de la bibliothèque partagée (Chemin absolu simulé dans Docker)
COPY healthai-common /healthai-common

# 4. Injection des fichiers de configuration de la Vision
COPY healthai-vision/pyproject.toml healthai-vision/uv.lock* ./

# 5. Synchronisation UV avec cache persistant (Finit les téléchargements de 8 minutes !)
# On monte un cache Docker dédié à UV ; timeout réseau allongé via UV_HTTP_TIMEOUT
# (uv sync n'a pas de flag --timeout).
RUN --mount=type=cache,target=/root/.cache/uv \
    UV_HTTP_TIMEOUT=600 uv sync --no-dev

# 6. Copie du code source du micro-service
COPY healthai-vision/src/ ./src/

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

EXPOSE 8001

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8001"]