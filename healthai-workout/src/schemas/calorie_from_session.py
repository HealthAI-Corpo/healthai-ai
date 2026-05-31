from pydantic import BaseModel, Field


class PredictFromSessionRequest(BaseModel):
    id_seance: int = Field(..., description="id_seance_log de la séance dans log_seance")


class PredictFromSessionResponse(BaseModel):
    id_seance: int
    calories_estimees: float
    calorie_brulee_avant: float | None
    champs_utilises: dict
