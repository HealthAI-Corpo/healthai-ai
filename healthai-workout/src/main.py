import json
import pickle
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import joblib
from fastapi import FastAPI
from loguru import logger

from src.core.config import settings
from src.database_mongo import mongo_db
from src.routers.calorie_estimation import router as calorie_router
from src.routers.recommendations import router as recommendations_router
from src.routers.sessions import router as sessions_router
from src.services.calorie_service import CalorieService
from src.services.recommendation_service import load_recommendation_service


def _load_artifact(path: Path):
    """Charge un artefact pkl via joblib avec fallback pickle."""
    try:
        return joblib.load(path)
    except Exception:
        with open(path, "rb") as f:
            return pickle.load(f)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await mongo_db.connect()

    base_dir = Path(__file__).parent.parent
    model_dir = base_dir / "models" / "CaloriesIA_1_0_0"
    model_path = model_dir / "random_forest" / "model.pkl"
    scaler_path = model_dir / "scaler.pkl"
    metadata_path = model_dir / "transformation_metadata.json"

    for path in (model_path, scaler_path, metadata_path):
        if not path.exists():
            raise FileNotFoundError(
                f"Fichier modèle introuvable: {path}\n"
                "Générez les modèles avec: uv run python scripts/train_calorie_model.py"
            )

    model = _load_artifact(model_path)
    scaler = _load_artifact(scaler_path)
    with open(metadata_path) as f:
        metadata = json.load(f)

    app.state.calorie_service = CalorieService(model, scaler, metadata)
    features = metadata.get("features_cols_order", [])
    logger.info("CalorieService initialisé — {} features: {}", len(features), ", ".join(features))

    try:
        app.state.recommendation_service = load_recommendation_service(base_dir / "models")
    except FileNotFoundError as e:
        logger.warning("RecommendationService non chargé (modèle manquant) : {}", e)
        app.state.recommendation_service = None

    yield

    mongo_db.close()
    logger.info("Shutdown complet")


app = FastAPI(title="HealthAI Workout Service", version="1.0.0", lifespan=lifespan)
app.include_router(sessions_router)
app.include_router(calorie_router)
app.include_router(recommendations_router)


@app.get("/")
async def root():
    return {"message": "Workout Service is up and running"}


@app.get("/health")
async def health():
    """Vérifie la connectivité avec Ollama."""
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            ollama_status = "connected" if response.status_code == 200 else "error"
    except Exception:
        ollama_status = "disconnected"

    return {
        "status": "online",
        "service": "healthai-workout",
        "ollama_integration": ollama_status,
    }
