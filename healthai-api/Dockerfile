FROM python:3.12-slim

WORKDIR /app

# Dépendances système minimales
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Installation de uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Installation des dépendances via lockfile
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen

# Copie du code source
COPY src/ ./src/

# Variables d'environnement pour Python
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

EXPOSE 8000

# Lancement via uv pour garantir l'usage du venv synchronisé
CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]