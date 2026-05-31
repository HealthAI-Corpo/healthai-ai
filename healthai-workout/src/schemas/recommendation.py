from pydantic import BaseModel


class ClassifierPredictions(BaseModel):
    type_seance: str
    intensite: str
    muscles_cibles: list[str]
    confidence: dict[str, float]


class WorkoutRecommendationResponse(BaseModel):
    status: str
    predictions_classifier: ClassifierPredictions
    seance: dict
