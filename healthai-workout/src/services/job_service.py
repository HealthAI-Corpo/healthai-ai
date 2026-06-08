"""Jobs IA asynchrones (mode "fire-and-forget" + polling).

Les appels Ollama sont lents (chargement modèle CPU, jusqu'à 180 s). Plutôt que de
bloquer la requête, les routes créent un job (status="processing"), délèguent le
travail à une BackgroundTask ou à RabbitMQ, et renvoient immédiatement un job_id.
Le front interroge ensuite GET /ai/jobs/{job_id} jusqu'à status="completed" (ou "failed").

Deux modes selon la disponibilité de RabbitMQ (RABBITMQ_URL) :
  - RabbitMQ disponible : le message est publié dans la queue `healthai.ai.jobs.workout`,
    consommé par le worker interne avec prefetch_count=1 (Ollama ne sature pas sous charge).
  - RabbitMQ absent     : fallback sur FastAPI BackgroundTasks (dev sans broker).

Le résultat est stocké dans Mongo (collection `ai_jobs`) dans les deux cas.
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


async def publish_job(job_id: str, job_type: str, user_id: int, payload: dict) -> None:
    """Publie le job dans RabbitMQ pour traitement par le worker."""
    from src.core.rabbitmq import publish  # import local pour éviter le circular

    await publish(
        {"job_id": job_id, "job_type": job_type, "user_id": user_id, "payload": payload}
    )


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
