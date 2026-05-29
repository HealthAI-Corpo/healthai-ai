FROM python:3.12-slim

WORKDIR /app

# Récupération de UV
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Plus de "..", on part de la racine globale !
COPY healthai-common /healthai-common
COPY healthai-api/pyproject.toml healthai-api/uv.lock* ./

# Installation globale (évite le bug du uvicorn introuvable avec les volumes)
ENV UV_SYSTEM_PYTHON=1
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev

# Copie du code source
COPY healthai-api/src/ ./src/

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]