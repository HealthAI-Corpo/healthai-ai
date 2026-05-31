"""Jobs IA asynchrones (mode "fire-and-forget" + polling).

Les appels Ollama sont lents (chargement modèle CPU, jusqu'à 180 s). Plutôt que de
bloquer la requête, les routes créent un job (status="processing"), délèguent le
travail à une BackgroundTask, et renvoient immédiatement un job_id. Le front interroge
ensuite GET /ai/jobs/{job_id} jusqu'à status="completed" (ou "failed").

Le résultat est stocké dans Mongo (collection `ai_jobs`). Ce stockage est donc REQUIS
pour le mode async : `require_mongo` renvoie 503 si Mongo est indisponible.

Le document Mongo porte aussi `id_utilisateur` (propriétaire) et un historique
`llm_calls` (prompts envoyés + réponses brutes du LLM, succès et échecs) pour le
debug et la traçabilité.
"""

from collections.abc import Awaitable, Callable
from datetime import datetime

from bson import ObjectId
from fastapi import HTTPException
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import AsyncSessionLocal
from src.database_mongo import mongo_db

JOBS_COLLECTION = "ai_jobs"


def require_mongo() -> None:
    """Dépendance FastAPI : le mode asynchrone exige Mongo pour stocker les jobs."""
    if mongo_db.db is None:
        raise HTTPException(
            status_code=503,
            detail="Stockage des jobs IA indisponible (MongoDB requis pour le mode asynchrone).",
        )


async def create_job(job_type: str, user_id: int) -> str:
    now = datetime.utcnow()
    res = await mongo_db.db[JOBS_COLLECTION].insert_one(
        {
            "type": job_type,
            "id_utilisateur": user_id,
            "status": "processing",
            "result": None,
            "error": None,
            "llm_calls": [],
            "created_at": now,
            "updated_at": now,
        }
    )
    return str(res.inserted_id)


async def get_job(job_id: str) -> dict | None:
    """Charge un job sans vérifier la propriété (usage interne / admin)."""
    try:
        doc = await mongo_db.db[JOBS_COLLECTION].find_one({"_id": ObjectId(job_id)})
    except Exception:  # noqa: BLE001 - ObjectId mal formé
        return None
    if not doc:
        return None
    doc["job_id"] = str(doc.pop("_id"))
    return doc


async def get_job_for_user(job_id: str, user_id: int) -> dict | None:
    """Charge un job s'il existe ET appartient à `user_id`. Sinon renvoie None.

    Ne distingue pas "job inconnu" de "job non possédé" — l'appelant doit renvoyer
    un 404 unique pour éviter l'énumération des job_id par un attaquant.
    """
    job = await get_job(job_id)
    if job is None or job.get("id_utilisateur") != user_id:
        return None
    return job


async def _patch(job_id: str, fields: dict) -> None:
    fields["updated_at"] = datetime.utcnow()
    try:
        await mongo_db.db[JOBS_COLLECTION].update_one({"_id": ObjectId(job_id)}, {"$set": fields})
    except Exception as e:  # noqa: BLE001
        logger.warning("MAJ du job {} échouée : {}", job_id, e)


async def record_llm_call(
    job_id: str,
    *,
    system_prompt: str,
    user_prompt: str,
    raw_response: str | None,
    parsed_ok: bool,
    error: str | None = None,
) -> None:
    """Ajoute la trace d'un appel LLM (prompt + réponse brute) au job.

    Appelé pour CHAQUE appel Ollama, succès ou échec — c'est ce qui permet de
    diagnostiquer une sortie JSON invalide (`raw_response` contient le texte brut
    renvoyé par le modèle) sans rejouer la requête.
    """
    entry = {
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "raw_response": raw_response,
        "parsed_ok": parsed_ok,
        "error": error,
        "timestamp": datetime.utcnow(),
    }
    try:
        await mongo_db.db[JOBS_COLLECTION].update_one(
            {"_id": ObjectId(job_id)},
            {"$push": {"llm_calls": entry}, "$set": {"updated_at": datetime.utcnow()}},
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("Trace LLM du job {} échouée : {}", job_id, e)


async def run_in_background(job_id: str, work: Callable[[AsyncSession], Awaitable[dict]]) -> None:
    """Exécute le travail IA hors requête et enregistre le résultat dans le job.

    Ouvre sa PROPRE session DB : la session de la requête est fermée dès la réponse 202
    envoyée. Les erreurs métier (HTTPException 404/403/502) sont stockées dans le job
    (status="failed", error_code) au lieu de remonter en HTTP.
    """
    async with AsyncSessionLocal() as db:
        try:
            result = await work(db)
            await _patch(job_id, {"status": "completed", "result": result, "error": None})
        except HTTPException as e:
            await _patch(
                job_id,
                {"status": "failed", "error": str(e.detail), "error_code": e.status_code},
            )
        except Exception as e:  # noqa: BLE001
            logger.exception("Job IA {} échoué", job_id)
            await _patch(job_id, {"status": "failed", "error": str(e), "error_code": 500})
