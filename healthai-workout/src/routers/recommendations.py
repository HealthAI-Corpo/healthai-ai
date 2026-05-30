from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.schemas.ai_sessions import JobCreatedResponse
from src.schemas.recommendation import WorkoutRecommendationResponse
from src.services import job_service
from src.services.context_service import build_recommendation_profile
from src.services.job_service import require_mongo
from src.services.recommendation_service import RecommendationService

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])


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


@router.post(
    "/workout",
    response_model=JobCreatedResponse,
    status_code=202,
    summary="Programme d'entraînement personnalisé (asynchrone, hybride)",
    description=(
        "Moteur hybride : un classifieur sklearn prédit `type_seance` / `intensite` / "
        "`muscles_cibles` depuis le profil, puis Ollama structure la séance complète "
        "(schéma JSON imposé). Le profil et l'historique récent sont lus en base — "
        "aucun body requis. 503 immédiat si le modèle reco n'est pas chargé ; les "
        "autres erreurs sont reportées dans le job."
    ),
)
async def recommend_workout(
    background_tasks: BackgroundTasks,
    x_user_id: int = Header(..., alias="X-User-Id"),
    service: RecommendationService = Depends(get_recommendation_service),
    _: None = Depends(require_mongo),
) -> JobCreatedResponse:
    job_id = await job_service.create_job("recommend-workout", x_user_id)
    background_tasks.add_task(
        job_service.run_in_background,
        job_id,
        lambda db: _recommend(db, x_user_id, service, job_id),
    )
    return JobCreatedResponse(job_id=job_id)
