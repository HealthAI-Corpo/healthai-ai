from datetime import datetime

from pydantic import BaseModel, field_validator


class ExerciceItem(BaseModel):
    nom: str
    series: int
    repetitions: int
    repos_sec: int


class SessionCreate(BaseModel):
    user_id: int
    exercices: list[ExerciceItem]
    calories_estimees: float | None = None
    duree_min: int
    recommendation_id: str | None = None

    @field_validator("exercices")
    @classmethod
    def exercices_not_empty(cls, v: list) -> list:
        if not v:
            raise ValueError("La liste d'exercices ne peut pas être vide")
        return v


class SessionResponse(BaseModel):
    id: int
    user_id: int
    exercices: list[ExerciceItem]
    calories_estimees: float | None
    duree_min: int
    timestamp: datetime
    recommendation_id: str | None

    model_config = {"from_attributes": True}


class AICorpsExercice(BaseModel):
    exercice: str
    series: int
    repetitions: str
    conseil: str


class AIWorkoutResponse(BaseModel):
    status: str
    meta_data_used: dict
    generated_workout: dict
