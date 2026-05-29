from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException

from src.schemas.ai_sessions import (
    EvaluateSessionsRequest,
    ExplainExercisesRequest,
    GenerateSessionRequest,
    JobCreatedResponse,
    JobStatusResponse,
)
from src.services import ai_session_service, job_service
from src.services.job_service import require_mongo

router = APIRouter(prefix="/ai", tags=["AI Sessions"])

# Le header X-User-Id est injecté par la gateway après validation JWT Zitadel.

# Les appels Ollama sont lents : ces routes ne bloquent pas. Elles créent un job, lancent
# le travail en tâche de fond et renvoient un job_id (202). Le front interroge ensuite
# GET /ai/jobs/{job_id} jusqu'à status="completed". Mongo est requis (sinon 503).


@router.post(
    "/generate-session",
    response_model=JobCreatedResponse,
    status_code=202,
    summary="Génère une séance personnalisée (asynchrone)",
    description=(
        "Crée un job qui : reconstruit le profil utilisateur + historique récent depuis "
        "la base, envoie un prompt à Ollama, valide la sortie. Si `sauvegarder=true`, "
        "la séance est insérée dans `log_seance` avec statut `proposee`. "
        "Le résultat est récupéré via `GET /ai/jobs/{job_id}`."
    ),
)
async def generate_session(
    payload: GenerateSessionRequest,
    background_tasks: BackgroundTasks,
    x_user_id: int = Header(..., alias="X-User-Id"),
    sauvegarder: bool = False,
    _: None = Depends(require_mongo),
) -> JobCreatedResponse:
    job_id = await job_service.create_job("generate-session", x_user_id)
    contraintes = payload.model_dump()
    background_tasks.add_task(
        job_service.run_in_background,
        job_id,
        lambda db: ai_session_service.generate_session(
            db=db,
            user_id=x_user_id,
            contraintes=contraintes,
            sauvegarder=sauvegarder,
            job_id=job_id,
        ),
    )
    return JobCreatedResponse(job_id=job_id)


@router.post(
    "/evaluate-sessions",
    response_model=JobCreatedResponse,
    status_code=202,
    summary="Évalue des séances par ids (asynchrone)",
    description=(
        "Évalue des séances **déjà enregistrées** désignées par leurs ids. "
        "404 reporté dans le job si une séance est absente, 403 si elle n'appartient "
        "pas à l'utilisateur. Aucune écriture Postgres."
    ),
)
async def evaluate_sessions(
    payload: EvaluateSessionsRequest,
    background_tasks: BackgroundTasks,
    x_user_id: int = Header(..., alias="X-User-Id"),
    _: None = Depends(require_mongo),
) -> JobCreatedResponse:
    job_id = await job_service.create_job("evaluate-sessions", x_user_id)
    ids = payload.ids_seances
    background_tasks.add_task(
        job_service.run_in_background,
        job_id,
        lambda db: ai_session_service.evaluate_sessions_by_ids(
            db=db, user_id=x_user_id, ids_seances=ids, job_id=job_id
        ),
    )
    return JobCreatedResponse(job_id=job_id)


@router.get(
    "/evaluate-my-recent-sessions",
    response_model=JobCreatedResponse,
    status_code=202,
    summary="Évalue automatiquement les dernières séances (asynchrone)",
    description=(
        "Sélectionne les 7 dernières séances `terminee` + jusqu'à 5 séances `prevue` "
        "les plus proches, et les envoie à Ollama pour évaluation. Aucune écriture "
        "Postgres. 404 reporté dans le job si aucune séance à évaluer."
    ),
)
async def evaluate_my_recent_sessions(
    background_tasks: BackgroundTasks,
    x_user_id: int = Header(..., alias="X-User-Id"),
    _: None = Depends(require_mongo),
) -> JobCreatedResponse:
    job_id = await job_service.create_job("evaluate-recent-sessions", x_user_id)
    background_tasks.add_task(
        job_service.run_in_background,
        job_id,
        lambda db: ai_session_service.evaluate_recent_sessions(
            db=db, user_id=x_user_id, job_id=job_id
        ),
    )
    return JobCreatedResponse(job_id=job_id)


@router.post(
    "/explain-exercises",
    response_model=JobCreatedResponse,
    status_code=202,
    summary="Explique une liste d'exercices (asynchrone)",
    description=(
        "Pour chaque exercice (nom obligatoire, autres champs enrichissants), retourne "
        "technique, erreurs courantes, variantes et conseils de sécurité. Aucune "
        "écriture Postgres."
    ),
)
async def explain_exercises(
    payload: ExplainExercisesRequest,
    background_tasks: BackgroundTasks,
    x_user_id: int = Header(..., alias="X-User-Id"),
    _: None = Depends(require_mongo),
) -> JobCreatedResponse:
    job_id = await job_service.create_job("explain-exercises", x_user_id)
    exercices = [e.model_dump() for e in payload.exercices]
    background_tasks.add_task(
        job_service.run_in_background,
        job_id,
        lambda db: ai_session_service.explain_exercises(
            db=db, user_id=x_user_id, exercices=exercices, job_id=job_id
        ),
    )
    return JobCreatedResponse(job_id=job_id)


@router.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    tags=["Jobs"],
    summary="Polling : état d'un job IA",
    description=(
        "Endpoint partagé par toutes les routes asynchrones du service (les 4 `/ai/*` "
        "**et** `/recommendations/workout`). Le champ `llm_calls` contient les prompts "
        "envoyés à Ollama et la réponse brute (succès ou échec JSON) pour le debug. "
        "404 silencieux si l'utilisateur n'est pas propriétaire du job."
    ),
)
async def get_job_status(
    job_id: str,
    x_user_id: int = Header(..., alias="X-User-Id"),
    _: None = Depends(require_mongo),
) -> JobStatusResponse:
    job = await job_service.get_job_for_user(job_id, x_user_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job introuvable")
    return JobStatusResponse(**job)
