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

router = APIRouter(prefix="/ai", tags=["AI Sessions (Ollama)"])

# TODO: remplacer le header X-User-Id par l'extraction de l'identité depuis le JWT ZITADEL.

# Les appels Ollama sont lents : ces routes ne bloquent pas. Elles créent un job, lancent
# le travail en tâche de fond et renvoient un job_id (202). Le front interroge ensuite
# GET /ai/jobs/{job_id} jusqu'à status="completed". Mongo est requis (sinon 503).


@router.post("/generate-session", response_model=JobCreatedResponse, status_code=202)
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


@router.post("/evaluate-sessions", response_model=JobCreatedResponse, status_code=202)
async def evaluate_sessions(
    payload: EvaluateSessionsRequest,
    background_tasks: BackgroundTasks,
    x_user_id: int = Header(..., alias="X-User-Id"),
    _: None = Depends(require_mongo),
) -> JobCreatedResponse:
    """Évalue des séances existantes désignées par leurs ids (404/403 reportés dans le job)."""
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


@router.get("/evaluate-my-recent-sessions", response_model=JobCreatedResponse, status_code=202)
async def evaluate_my_recent_sessions(
    background_tasks: BackgroundTasks,
    x_user_id: int = Header(..., alias="X-User-Id"),
    _: None = Depends(require_mongo),
) -> JobCreatedResponse:
    """Évalue les dernières séances terminées + les séances prévues de l'utilisateur."""
    job_id = await job_service.create_job("evaluate-recent-sessions", x_user_id)
    background_tasks.add_task(
        job_service.run_in_background,
        job_id,
        lambda db: ai_session_service.evaluate_recent_sessions(
            db=db, user_id=x_user_id, job_id=job_id
        ),
    )
    return JobCreatedResponse(job_id=job_id)


@router.post("/explain-exercises", response_model=JobCreatedResponse, status_code=202)
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


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    x_user_id: int = Header(..., alias="X-User-Id"),
    _: None = Depends(require_mongo),
) -> JobStatusResponse:
    """Polling : état et résultat d'un job IA (toutes routes async workout, reco incluse).

    Renvoie 404 si le job n'existe pas OU si l'utilisateur n'en est pas propriétaire
    (réponse identique pour éviter l'énumération des job_id).
    """
    job = await job_service.get_job_for_user(job_id, x_user_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job introuvable")
    return JobStatusResponse(**job)
