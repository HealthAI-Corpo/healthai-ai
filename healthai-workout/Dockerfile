FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

COPY healthai-common /healthai-common
COPY healthai-workout/pyproject.toml healthai-workout/uv.lock* ./

# Installation système pour éviter le bug de chemin du .venv
ENV UV_SYSTEM_PYTHON=1
RUN uv sync --no-dev

COPY healthai-workout/src/ ./src/
COPY healthai-workout/models/ ./models/

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

EXPOSE 8002
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8002"]