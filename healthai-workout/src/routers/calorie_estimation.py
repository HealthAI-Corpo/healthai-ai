import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from src.schemas import (
    CalorieEstimationRequest,
    CalorieEstimationResponse,
    CalorieEstimationWithDefaultsRequest,
    CalorieEstimationWithDefaultsResponse,
    MetricsResponse,
    ModelInfoResponse,
)
from src.services.calorie_service import CalorieService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/calorie-estimation", tags=["Calorie ML"])


def get_calorie_service(request: Request) -> CalorieService:
    service = getattr(request.app.state, "calorie_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Modèle non chargé. Veuillez redémarrer l'API.")
    return service


@router.get(
    "/model-info",
    response_model=ModelInfoResponse,
    summary="Métadonnées du modèle calories",
)
async def get_model_info(
    service: CalorieService = Depends(get_calorie_service),
) -> ModelInfoResponse:
    features = service.metadata.get("features_cols_order", [])
    return ModelInfoResponse(
        model_name="CaloriesIA_1_0_0",
        model_version="1.0.0",
        features_required=features,
        model_type="RandomForest",
        training_date="2026-05-22",
        status="PRODUCTION",
        n_samples_test=491,
    )


@router.get(
    "/metrics",
    response_model=MetricsResponse,
    summary="Métriques d'évaluation du modèle",
)
async def get_metrics() -> MetricsResponse:
    # TODO : recup de healthai-workout\models\CaloriesIA_1_0_0\random_forest\metrics.json
    return MetricsResponse(
        r2_score=0.1751498562391377,
        mae=200.38720793270784,
        rmse=280.22221121281746,
        mape=24.592865626059794,
        model_version="1.0.0",
    )


@router.post(
    "/predict",
    response_model=CalorieEstimationResponse,
    summary="Prédiction de calories (toutes features fournies)",
    description=(
        "Estimation des calories brûlées à partir des 11 features biométriques + séance. "
        "Aucune écriture en base, c'est une simulation."
    ),
)
async def predict_calories(
    request: CalorieEstimationRequest,
    service: CalorieService = Depends(get_calorie_service),
) -> CalorieEstimationResponse:
    prediction = service.predict(request.model_dump())
    return CalorieEstimationResponse(
        prediction=round(prediction, 2),
        model_version="1.0.0",
        features_used=11,
        model_name="CaloriesIA_1_0_0",
    )


@router.post(
    "/predict-with-defaults",
    response_model=CalorieEstimationWithDefaultsResponse,
    summary="Prédiction avec imputation automatique",
    description=(
        "Identique à `/predict` mais tous les champs sont optionnels — les valeurs absentes "
        "ou null sont imputées par la moyenne du dataset d'entraînement. Utile depuis "
        "un formulaire front partiellement rempli."
    ),
)
async def predict_calories_with_defaults(
    request: CalorieEstimationWithDefaultsRequest,
    service: CalorieService = Depends(get_calorie_service),
) -> CalorieEstimationWithDefaultsResponse:
    prediction, imputed_features, original_values = service.predict_with_defaults(
        request.model_dump()
    )
    return CalorieEstimationWithDefaultsResponse(
        prediction=round(prediction, 2),
        model_version="1.0.0",
        features_used=11,
        model_name="CaloriesIA_1_0_0",
        imputed_features=imputed_features,
        original_values=original_values,
    )
