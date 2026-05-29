from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.schemas.ai_sessions import JobCreatedResponse
from src.schemas.recommendation import WorkoutRecommendationResponse
from src.services import job_service
from src.services.context_service import build_recommendation_profile
from src.services.job_service import require_mongo
from src.services.recommendation_service import RecommendationService

router = APIRouter(prefix="/recommendations", tags=["recommendations"])

# TODO: remplacer le header X-User-Id par l'extraction de l'identité depuis le JWT ZITADEL.


def get_recommendation_service(request: Request) -> RecommendationService:
    service = getattr(request.app.state, "recommendation_service", None)
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="Modèle de recommandation non chargé. Lancez scripts/train_recommendation_model.py puis redémarrez.",
        )
    return service


async def _recommend(
    db: AsyncSession, user_id: int, service: RecommendationService, job_id: str
) -> dict:
    """Travail de fond : profil depuis la base (404 si introuvable) → classifier → LLM."""
    profile = await build_recommendation_profile(db, user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    result = await service.generate(profile, job_id=job_id)
    resp = WorkoutRecommendationResponse(
        status="success",
        predictions_classifier=result["predictions_classifier"],
        seance=result["seance"],
    )
    return resp.model_dump()


@router.post("/workout", response_model=JobCreatedResponse, status_code=202)
async def recommend_workout(
    background_tasks: BackgroundTasks,
    x_user_id: int = Header(..., alias="X-User-Id"),
    service: RecommendationService = Depends(get_recommendation_service),
    _: None = Depends(require_mongo),
) -> JobCreatedResponse:
    """Génère un programme d'entraînement personnalisé (moteur hybride classifier + LLM).

    Entrée : header `X-User-Id` uniquement ; le profil (biométrie, objectif, limitations)
    et l'historique récent sont lus en base. L'appel Ollama étant lent, le travail tourne
    en tâche de fond : récupère le job via GET /ai/jobs/{job_id}.

    Le modèle de reco (503) est vérifié immédiatement ; l'utilisateur introuvable (404)
    est reporté dans le job (status="failed", error_code=404).
    """
    job_id = await job_service.create_job("recommend-workout", x_user_id)
    background_tasks.add_task(
        job_service.run_in_background,
        job_id,
        lambda db: _recommend(db, x_user_id, service, job_id),
    )
    return JobCreatedResponse(job_id=job_id)
