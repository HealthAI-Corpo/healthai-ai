import asyncio
import json
import pickle
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import joblib
from fastapi import FastAPI
from loguru import logger

from src.core.config import settings
from src.core.rabbitmq import close as rmq_close
from src.core.rabbitmq import connect as rmq_connect
from src.core.rabbitmq import is_available as rmq_available
from src.core.rabbitmq import start_worker
from src.database_mongo import mongo_db
from src.routers.ai_sessions import router as ai_sessions_router
from src.routers.calorie_estimation import router as calorie_router
from src.routers.calorie_from_session import router as calorie_from_session_router
from src.routers.recommendations import router as recommendations_router
from src.services.calorie_service import CalorieService
from src.services.recommendation_service import load_recommendation_service


def _load_artifact(path: Path):
    """Charge un artefact pkl via joblib avec fallback pickle."""
    try:
        return joblib.load(path)
    except Exception:
        with open(path, "rb") as f:
            return pickle.load(f)


async def _dispatch_job(message: dict) -> None:
    """Dispatch un message RabbitMQ vers le service métier correspondant."""
    from src.services import ai_session_service, job_service  # import local

    job_id = message["job_id"]
    job_type = message["job_type"]
    user_id = message["user_id"]
    payload = message.get("payload", {})

    dispatch_map = {
        "generate-session": lambda db: ai_session_service.generate_session(
            db=db,
            user_id=user_id,
            contraintes=payload.get("contraintes", {}),
            sauvegarder=payload.get("sauvegarder", False),
            job_id=job_id,
        ),
        "evaluate-sessions": lambda db: ai_session_service.evaluate_sessions_by_ids(
            db=db,
            user_id=user_id,
            ids_seances=payload.get("ids_seances", []),
            job_id=job_id,
        ),
        "evaluate-recent-sessions": lambda db: ai_session_service.evaluate_recent_sessions(
            db=db, user_id=user_id, job_id=job_id
        ),
        "explain-exercises": lambda db: ai_session_service.explain_exercises(
            db=db,
            user_id=user_id,
            exercices=payload.get("exercices", []),
            job_id=job_id,
        ),
        "recommend-workout": lambda db: _dispatch_recommendation(db, user_id, job_id),
    }

    work = dispatch_map.get(job_type)
    if work is None:
        logger.warning("Type de job inconnu : {}", job_type)
        return
    await job_service.run_in_background(job_id, work)


async def _dispatch_recommendation(db, user_id: int, job_id: str) -> dict:
    from src.services.context_service import build_recommendation_profile
    from fastapi import HTTPException

    service = getattr(_app_state, "recommendation_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Modèle de recommandation non chargé.")
    profile = await build_recommendation_profile(db, user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    result = await service.generate(profile, job_id=job_id)
    from src.schemas.recommendation import WorkoutRecommendationResponse
    return WorkoutRecommendationResponse(
        status="success",
        predictions_classifier=result["predictions_classifier"],
        seance=result["seance"],
    ).model_dump()


_app_state = None  # référence à app.state pour le dispatch recommendation


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _app_state
    _app_state = app.state
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
    with open(metadata_path, encoding="utf-8") as f:
        metadata = json.load(f)

    app.state.calorie_service = CalorieService(model, scaler, metadata)
    features = metadata.get("features_cols_order", [])
    logger.info("CalorieService initialisé — {} features: {}", len(features), ", ".join(features))

    # Service de reco = bonus optionnel : une erreur de chargement (modèle manquant,
    # fichier corrompu/mal encodé...) ne doit pas empêcher le service calories de démarrer.
    try:
        app.state.recommendation_service = load_recommendation_service(base_dir / "models")
    except Exception as e:  # noqa: BLE001
        logger.warning("RecommendationService non chargé : {}", e)
        app.state.recommendation_service = None

    # RabbitMQ — connexion + worker en tâche de fond
    await rmq_connect()
    worker_task: asyncio.Task | None = None
    if rmq_available():
        worker_task = asyncio.create_task(start_worker(_dispatch_job))
        logger.info("Worker RabbitMQ lancé")

    yield

    if worker_task and not worker_task.done():
        worker_task.cancel()
    await rmq_close()
    mongo_db.close()
    logger.info("Shutdown complet")


app = FastAPI(
    title="HealthAI Workout",
    version="1.0.0",
    description=(
        "Service IA d'estimation de calories (RandomForest) et de génération de séances "
        "/ recommandations / évaluations via Ollama. Toutes les routes exigent le header "
        "`X-User-Id` injecté par la gateway. Les routes LLM sont asynchrones : 202 + "
        "polling via `GET /ai/jobs/{job_id}`."
    ),
    lifespan=lifespan,
)
app.include_router(calorie_router)
app.include_router(calorie_from_session_router)
app.include_router(recommendations_router)
app.include_router(ai_sessions_router)


@app.get("/", include_in_schema=False)
async def root():
    return {"message": "Workout Service is up and running"}


@app.get("/health", tags=["Diagnostics"])
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
