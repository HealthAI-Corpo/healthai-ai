from pydantic import BaseModel, Field


class WorkoutRecommendationRequest(BaseModel):
    age: int = Field(..., ge=15, le=100)
    poids_kg: float = Field(..., gt=0)
    taille_cm: float = Field(..., gt=0)
    niveau_experience: int = Field(default=1, ge=1, le=3)
    frequence_sport_jour_semaine: int = Field(default=3, ge=0, le=7)
    bpm_repos: int = Field(default=65, ge=30, le=120)
    objectif: str = Field(default="Forme générale")
    limitations: str = Field(default="Aucune")
    historique_seances: list[str] = Field(default_factory=list)


class ClassifierPredictions(BaseModel):
    type_seance: str
    intensite: str
    muscles_cibles: list[str]
    confidence: dict[str, float]


class WorkoutRecommendationResponse(BaseModel):
    status: str
    predictions_classifier: ClassifierPredictions
    seance: dict
