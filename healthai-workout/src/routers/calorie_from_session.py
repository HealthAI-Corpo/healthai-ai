from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.routers.calorie_estimation import get_calorie_service
from src.schemas.calorie_from_session import (
    PredictFromSessionRequest,
    PredictFromSessionResponse,
)
from src.services.calorie_from_session_service import predict_from_session
from src.services.calorie_service import CalorieService

router = APIRouter(prefix="/calorie-estimation", tags=["Calorie ML"])


@router.post(
    "/predict-from-session",
    response_model=PredictFromSessionResponse,
    summary="Prédiction et écriture en base depuis une séance enregistrée",
    description=(
        "Reconstruit les 11 features depuis `log_seance` + `log_sante` + `utilisateur` "
        "pour la séance désignée, prédit les calories, et **met à jour** "
        "`log_seance.calorie_brulee`. Renvoie 404 si la séance n'existe pas, 403 si elle "
        "n'appartient pas à l'utilisateur."
    ),
)
async def predict_calories_from_session(
    payload: PredictFromSessionRequest,
    x_user_id: int = Header(..., alias="X-User-Id"),
    service: CalorieService = Depends(get_calorie_service),
    db: AsyncSession = Depends(get_db),
) -> PredictFromSessionResponse:
    result = await predict_from_session(
        service=service,
        id_seance=payload.id_seance,
        id_utilisateur=x_user_id,
        db=db,
    )
    return PredictFromSessionResponse(**result)
