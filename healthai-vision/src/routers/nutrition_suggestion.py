"""Suggestion + validation de recettes (asynchrone).

Flux : POST /nutrition/ai/suggest-meal → tâche de fond → Mongo `suggestions`.
Le front interroge GET /nutrition/suggestion/{id} jusqu'à `status=completed`, puis
appelle POST /nutrition/ai/validate-suggestion pour persister la recette en Postgres.
"""

from __future__ import annotations

from datetime import datetime

from bson import ObjectId
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException

from src.database import AsyncSessionLocal
from src.database_mongo import mongo_db
from src.schemas.vision import (
    SuggestionStatus,
    SuggestMealAccepted,
    ValidateSuggestionRequest,
    ValidateSuggestionResponse,
)
from src.services.suggestion_service import (
    suggest_meal_from_db,
    validate_and_log_meal_to_postgres,
)

router = APIRouter(prefix="/nutrition", tags=["Meal Suggestion"])


def _require_owner(doc: dict | None, x_user_id: str) -> dict:
    if doc is None or doc.get("user_id") != x_user_id:
        raise HTTPException(status_code=404, detail="Suggestion introuvable.")
    return doc


async def _run_meal_suggestion_in_background(user_id: int, suggestion_id: str) -> None:
    async with AsyncSessionLocal() as db_sql:
        try:
            suggestion_json = await suggest_meal_from_db(user_id=user_id, db_sql=db_sql)
            await mongo_db.db.suggestions.update_one(
                {"_id": ObjectId(suggestion_id)},
                {
                    "$set": {
                        "status": "completed",
                        "validation_status": "pending",
                        "suggestion": suggestion_json,
                    }
                },
            )
        except Exception as exc:  # noqa: BLE001
            await mongo_db.db.suggestions.update_one(
                {"_id": ObjectId(suggestion_id)},
                {"$set": {"status": "failed", "error": str(exc)}},
            )


@router.post(
    "/ai/suggest-meal",
    response_model=SuggestMealAccepted,
    summary="Demande une recette personnalisée (asynchrone)",
    description=(
        "Calcule le besoin calorique restant de la journée à partir du profil et de "
        "l'historique Mongo, puis génère une recette via Ollama en tâche de fond. "
        "Récupérer le résultat via `GET /nutrition/suggestion/{suggestion_id}`."
    ),
)
async def suggest_meal_endpoint(
    background_tasks: BackgroundTasks,
    x_user_id: str = Header(..., alias="X-User-Id"),
) -> SuggestMealAccepted:
    if mongo_db.db is None:
        raise HTTPException(status_code=503, detail="MongoDB indisponible.")

    new_suggestion = {
        "user_id": x_user_id,
        "timestamp": datetime.utcnow(),
        "status": "processing",
        "validation_status": "pending",
        "suggestion": None,
    }
    result = await mongo_db.db.suggestions.insert_one(new_suggestion)
    suggestion_id = str(result.inserted_id)

    background_tasks.add_task(
        _run_meal_suggestion_in_background,
        user_id=int(x_user_id),
        suggestion_id=suggestion_id,
    )

    return SuggestMealAccepted(
        message="L'IA concocte votre recette personnalisée...",
        suggestion_id=suggestion_id,
    )


@router.get(
    "/suggestion/{suggestion_id}",
    response_model=SuggestionStatus,
    summary="Polling de la suggestion de recette",
    description=(
        "Renvoie l'état actuel de la suggestion. 404 si elle n'appartient pas à "
        "l'utilisateur (réponse identique à un id inconnu)."
    ),
)
async def get_suggestion_endpoint_status(
    suggestion_id: str,
    x_user_id: str = Header(..., alias="X-User-Id"),
) -> SuggestionStatus:
    if mongo_db.db is None:
        raise HTTPException(status_code=503, detail="MongoDB indisponible.")
    try:
        doc = await mongo_db.db.suggestions.find_one({"_id": ObjectId(suggestion_id)})
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail="Suggestion introuvable.") from exc
    doc = _require_owner(doc, x_user_id)
    return SuggestionStatus(
        suggestion_id=suggestion_id,
        status=doc.get("status", "processing"),
        validation_status=doc.get("validation_status"),
        resultat=doc.get("suggestion"),
    )


@router.post(
    "/ai/validate-suggestion",
    response_model=ValidateSuggestionResponse,
    summary="Valide la recette suggérée (Mongo → Postgres)",
    description=(
        "Marque la suggestion comme `approved` dans Mongo et insère un log de repas dans "
        "Postgres pour l'utilisateur. 404 si la suggestion n'existe pas ou n'appartient "
        "pas à l'utilisateur."
    ),
)
async def validate_suggestion_endpoint(
    payload: ValidateSuggestionRequest,
    x_user_id: str = Header(..., alias="X-User-Id"),
) -> ValidateSuggestionResponse:
    if mongo_db.db is None:
        raise HTTPException(status_code=503, detail="MongoDB indisponible.")

    try:
        doc = await mongo_db.db.suggestions.find_one({"_id": ObjectId(payload.suggestion_id)})
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail="Suggestion introuvable.") from exc
    _require_owner(doc, x_user_id)

    async with AsyncSessionLocal() as db_sql:
        res = await validate_and_log_meal_to_postgres(payload.suggestion_id, db_sql)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return ValidateSuggestionResponse(**res)
