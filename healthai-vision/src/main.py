"""HealthAI Vision — détection d'aliments + conseils + suggestions de repas.

Entry-point FastAPI : inclut les 3 routers (analyze, advice, suggestion) et expose
un endpoint de santé. La gateway IA (`healthai-api`) est censée préfixer toutes
les routes par `/vision/`.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from os import getenv

import httpx
from fastapi import FastAPI

from src.database_mongo import mongo_db
from src.routers.analyze import router as analyze_router
from src.routers.nutrition_advice import router as advice_router
from src.routers.nutrition_suggestion import router as suggestion_router
from src.services.ai_service import ai_service

OLLAMA_BASE_URL = getenv("OLLAMA_BASE_URL", "http://healthai-ollama:11434")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await mongo_db.connect()
    yield
    mongo_db.close()


app = FastAPI(
    title="HealthAI Vision",
    version="1.0.0",
    description=(
        "Service IA d'analyse de repas (YOLOv8 + macros Postgres) et de génération de "
        "conseils nutritionnels / suggestions de recettes via Ollama. Toutes les routes "
        "exigent le header `X-User-Id` injecté par la gateway."
    ),
    lifespan=lifespan,
)

app.include_router(analyze_router)
app.include_router(advice_router)
app.include_router(suggestion_router)


@app.get("/health", tags=["Diagnostics"])
async def health() -> dict:
    """Indique si Ollama, Mongo et le modèle YOLO sont prêts."""
    ollama_online = False
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{OLLAMA_BASE_URL}/")
            ollama_online = response.status_code == 200 and "Ollama is running" in response.text
    except Exception:  # noqa: BLE001
        ollama_online = False

    return {
        "status": "online",
        "service": "healthai-vision",
        "model_loaded": ai_service.model is not None,
        "mongodb_connected": mongo_db.db is not None,
        "ollama_connected": ollama_online,
    }
