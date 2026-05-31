"""Conseils nutritionnels asynchrones.

POST /nutrition/ai/advice déclenche le calcul Ollama en tâche de fond ; le résultat
arrive dans `consumptions.recommandation_ia` (Mongo) interrogé via GET.
"""

from __future__ import annotations

from bson import ObjectId
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException

from src.database_mongo import mongo_db
from src.schemas.vision import (
    AdviceAccepted,
    AdviceRequest,
    ConsumptionStatus,
)
from src.services.recommandation_service import run_ollama_in_background

router = APIRouter(prefix="/nutrition", tags=["Nutrition Advice"])


def _require_owner(doc: dict | None, x_user_id: str, kind: str) -> dict:
    """Retourne le doc s'il existe ET appartient à l'utilisateur, sinon 404 silencieux."""
    if doc is None or doc.get("user_id") != x_user_id:
        raise HTTPException(status_code=404, detail=f"{kind.capitalize()} introuvable.")
    return doc


@router.post(
    "/ai/advice",
    response_model=AdviceAccepted,
    summary="Demande des conseils nutritionnels (asynchrone)",
    description=(
        "Lance un calcul Ollama en tâche de fond pour générer des conseils sur le repas "
        "désigné par `consumption_id`. Vérifier l'avancement via "
        "`GET /nutrition/consumption/{consumption_id}` jusqu'à ce que `recommandation_ia` "
        "soit rempli."
    ),
)
async def get_nutritional_advice_endpoint(
    payload: AdviceRequest,
    background_tasks: BackgroundTasks,
    x_user_id: str = Header(..., alias="X-User-Id"),
) -> AdviceAccepted:
    if mongo_db.db is None:
        raise HTTPException(status_code=503, detail="MongoDB indisponible.")

    try:
        doc = await mongo_db.db.consumptions.find_one({"_id": ObjectId(payload.consumption_id)})
    except Exception as exc:  # noqa: BLE001 — ObjectId mal formé
        raise HTTPException(status_code=404, detail="Repas introuvable.") from exc
    _require_owner(doc, x_user_id, "repas")

    background_tasks.add_task(
        run_ollama_in_background,
        user_id=int(x_user_id),
        consumption_id=payload.consumption_id,
    )
    return AdviceAccepted(
        message="L'IA génère vos conseils personnalisés en tâche de fond.",
        consumption_id=payload.consumption_id,
    )


@router.get(
    "/consumption/{consumption_id}",
    response_model=ConsumptionStatus,
    summary="Polling du conseil nutritionnel",
    description=(
        "Lit le document `consumptions` ; tant que `recommandation_ia` est `null`, le "
        "statut renvoyé est `processing`. Renvoie 404 si l'utilisateur n'est pas le "
        "propriétaire du document."
    ),
)
async def get_consumption_status(
    consumption_id: str,
    x_user_id: str = Header(..., alias="X-User-Id"),
) -> ConsumptionStatus:
    if mongo_db.db is None:
        raise HTTPException(status_code=503, detail="MongoDB indisponible.")
    try:
        doc = await mongo_db.db.consumptions.find_one({"_id": ObjectId(consumption_id)})
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail="Repas introuvable.") from exc
    doc = _require_owner(doc, x_user_id, "repas")

    advice = doc.get("recommandation_ia")
    return ConsumptionStatus(
        consumption_id=consumption_id,
        status="completed" if advice else "processing",
        total_repas=doc.get("summary"),
        detections=doc.get("details"),
        recommandation_ia=advice,
    )
