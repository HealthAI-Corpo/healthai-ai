from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.schemas.recommendation import WorkoutRecommendationResponse
from src.services.context_service import build_recommendation_profile
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


@router.post("/workout", response_model=WorkoutRecommendationResponse)
async def recommend_workout(
    x_user_id: int = Header(..., alias="X-User-Id"),
    service: RecommendationService = Depends(get_recommendation_service),
    db: AsyncSession = Depends(get_db),
) -> WorkoutRecommendationResponse:
    """
    Génère un programme d'entraînement personnalisé via le moteur hybride.

    Entrée : header `X-User-Id` uniquement. Le profil (biométrie, objectif, limitations)
    et l'historique récent des séances sont récupérés en base à partir de cet id.

    Pipeline :
    1. Classifier sklearn (RandomForest multi-output) prédit type, intensité et muscles cibles
    2. LLM Ollama structure la séance complète à partir de ces prédictions

    Sortie : `status`, les prédictions brutes du classifier, et la `seance` structurée par le LLM.
    """
    profile = await build_recommendation_profile(db, x_user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    try:
        result = await service.generate(profile)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la génération : {e}",
        ) from e

    return WorkoutRecommendationResponse(
        status="success",
        predictions_classifier=result["predictions_classifier"],
        seance=result["seance"],
    )
