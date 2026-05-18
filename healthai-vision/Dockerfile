# ── Builder ───────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
WORKDIR /app

COPY pyproject.toml uv.lock* ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --frozen

# ── Runner ────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runner

# Dépendances runtime OpenCV (libgl1 / libglib2.0-0 nécessaires au runner)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /app/.venv ./.venv
COPY src/ ./src/

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

EXPOSE 8001
CMD ["uvicorn", "src.server:app", "--host", "0.0.0.0", "--port", "8001"]
