"""Schémas Pydantic du service Vision.

Centralisés ici pour que Swagger expose des exemples et descriptions clairs.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class NutritionMacros(BaseModel):
    calories: float = Field(0.0, description="kcal cumulées pour la portion détectée")
    proteines: float = Field(0.0, description="grammes de protéines")
    glucides: float = Field(0.0, description="grammes de glucides")
    lipides: float = Field(0.0, description="grammes de lipides")
    eau_ml: float = Field(0.0, alias="eau", description="mL d'eau (champ aliasé)")


class DetectionItem(BaseModel):
    """Aliment détecté par YOLO + enrichi via la table `aliment`."""

    label: str = Field(..., description="Label brut renvoyé par le modèle")
    confidence: float | None = Field(None, ge=0, le=1)
    id_aliment: int | None = None
    display_name: str | None = None
    nutrition: NutritionMacros | None = None


class AnalyzeResponse(BaseModel):
    filename: str | None
    user_id: str
    consumption_id: str | None = Field(
        None,
        description="ObjectId Mongo du document `consumptions`. None si Mongo indispo.",
    )
    count: int
    total_repas: dict[str, float]
    detections: list[dict[str, Any]]


# --- Advice (conseils nutritionnels asynchrones) --------------------------------


class AdviceRequest(BaseModel):
    consumption_id: str = Field(
        ...,
        description="ObjectId Mongo renvoyé par /analyze pour le repas concerné.",
        examples=["6a13684c67a8a0c84da543fb"],
    )


class AdviceAccepted(BaseModel):
    status: str = "processing"
    message: str
    consumption_id: str


class ConsumptionStatus(BaseModel):
    consumption_id: str
    status: str = Field(
        ...,
        description="processing tant que `recommandation_ia` absent, sinon completed",
    )
    total_repas: dict[str, float] | None = None
    detections: list[dict[str, Any]] | None = None
    recommandation_ia: dict[str, Any] | None = None


# --- Suggestion de repas --------------------------------------------------------


class SuggestMealAccepted(BaseModel):
    status: str = "processing"
    message: str
    suggestion_id: str = Field(
        ...,
        description="ObjectId Mongo à interroger via GET /nutrition/suggestion/{id}",
    )


class SuggestionStatus(BaseModel):
    suggestion_id: str
    status: str = Field(..., description="processing | completed | failed")
    validation_status: str | None = Field(None, description="pending | approved")
    resultat: dict[str, Any] | None = None


class ValidateSuggestionRequest(BaseModel):
    suggestion_id: str = Field(..., examples=["6a13684c67a8a0c84da543fb"])


class ValidateSuggestionResponse(BaseModel):
    message: str
    suggestion_id: str
