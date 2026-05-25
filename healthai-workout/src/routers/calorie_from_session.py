from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.routers.calorie_estimation import get_calorie_service
from src.schemas.calorie_from_session import (
    PredictFromSessionRequest,
    PredictFromSessionResponse,
)
from src.services.calorie_from_session_service import predict_from_session
from src.services.calorie_service import CalorieService

router = APIRouter(prefix="/calorie-estimation", tags=["CaloriesIA"])


@router.post("/predict-from-session", response_model=PredictFromSessionResponse)
async def predict_calories_from_session(
    payload: PredictFromSessionRequest,
    user_id: int,  # TODO: extraire depuis le JWT ZITADEL au lieu d'un paramètre
    service: CalorieService = Depends(get_calorie_service),
    db: AsyncSession = Depends(get_db),
) -> PredictFromSessionResponse:
    result = await predict_from_session(
        service=service,
        id_seance=payload.id_seance,
        id_utilisateur=user_id,
        db=db,
    )
    return PredictFromSessionResponse(**result)
