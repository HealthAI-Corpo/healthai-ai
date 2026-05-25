from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.schemas.ai_sessions import (
    EvaluateSessionsRequest,
    EvaluateSessionsResponse,
    ExplainExercisesRequest,
    ExplainExercisesResponse,
    GenerateSessionRequest,
    GenerateSessionResponse,
)
from src.services import ai_session_service

router = APIRouter(prefix="/ai", tags=["AI Sessions (Ollama)"])

# TODO: remplacer le header X-User-Id par l'extraction de l'identité depuis le JWT ZITADEL.


@router.post("/generate-session", response_model=GenerateSessionResponse)
async def generate_session(
    payload: GenerateSessionRequest,
    x_user_id: int = Header(..., alias="X-User-Id"),
    sauvegarder: bool = False,
    db: AsyncSession = Depends(get_db),
) -> GenerateSessionResponse:
    result = await ai_session_service.generate_session(
        db=db,
        user_id=x_user_id,
        contraintes=payload.model_dump(),
        sauvegarder=sauvegarder,
    )
    return GenerateSessionResponse(**result)


@router.post("/evaluate-sessions", response_model=EvaluateSessionsResponse)
async def evaluate_sessions(
    payload: EvaluateSessionsRequest,
    x_user_id: int = Header(..., alias="X-User-Id"),
    db: AsyncSession = Depends(get_db),
) -> EvaluateSessionsResponse:
    """Évalue des séances existantes désignées par leurs ids."""
    result = await ai_session_service.evaluate_sessions_by_ids(
        db=db, user_id=x_user_id, ids_seances=payload.ids_seances
    )
    return EvaluateSessionsResponse(**result)


@router.get("/evaluate-my-recent-sessions", response_model=EvaluateSessionsResponse)
async def evaluate_my_recent_sessions(
    x_user_id: int = Header(..., alias="X-User-Id"),
    db: AsyncSession = Depends(get_db),
) -> EvaluateSessionsResponse:
    """Évalue les dernières séances terminées + les séances prévues de l'utilisateur."""
    result = await ai_session_service.evaluate_recent_sessions(db=db, user_id=x_user_id)
    return EvaluateSessionsResponse(**result)


@router.post("/explain-exercises", response_model=ExplainExercisesResponse)
async def explain_exercises(
    payload: ExplainExercisesRequest,
    x_user_id: int = Header(..., alias="X-User-Id"),
    db: AsyncSession = Depends(get_db),
) -> ExplainExercisesResponse:
    exercices = [e.model_dump() for e in payload.exercices]
    result = await ai_session_service.explain_exercises(
        db=db, user_id=x_user_id, exercices=exercices
    )
    return ExplainExercisesResponse(**result)
