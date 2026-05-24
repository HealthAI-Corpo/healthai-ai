from fastapi import APIRouter, Depends, HTTPException, Request

from src.schemas.recommendation import WorkoutRecommendationRequest, WorkoutRecommendationResponse
from src.services.recommendation_service import RecommendationService

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


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
    payload: WorkoutRecommendationRequest,
    service: RecommendationService = Depends(get_recommendation_service),
) -> WorkoutRecommendationResponse:
    """
    Génère un programme d'entraînement personnalisé via le moteur hybride :
    1. Classifier sklearn (RandomForest multi-output) prédit type, intensité et muscles cibles
    2. LLM Ollama structure la séance complète à partir de ces prédictions
    """
    try:
        result = await service.generate(payload.model_dump())
        return WorkoutRecommendationResponse(
            status="success",
            predictions_classifier=result["predictions_classifier"],
            seance=result["seance"],
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la génération : {e}",
        ) from e
