from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models.session import Session
from src.schemas.session import AIWorkoutResponse, SessionCreate, SessionResponse
from src.services.user_service import verify_user_exists
from src.services.workout_generation import generate_ai_workout_session

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionResponse])
async def list_sessions(user_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Session).where(Session.user_id == user_id).order_by(Session.timestamp.desc())
    )
    return result.scalars().all()


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Séance introuvable")
    return session


@router.post("", response_model=SessionResponse, status_code=201)
async def create_session(payload: SessionCreate, db: AsyncSession = Depends(get_db)):
    if not await verify_user_exists(payload.user_id):
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    session = Session(
        user_id=payload.user_id,
        exercices=[e.model_dump() for e in payload.exercices],
        calories_estimees=payload.calories_estimees,
        duree_min=payload.duree_min,
        recommendation_id=payload.recommendation_id,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


@router.delete("/{session_id}", status_code=204)
async def delete_session(session_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Séance introuvable")
    await db.delete(session)
    await db.commit()


@router.post("/generate-mock", response_model=AIWorkoutResponse, status_code=200)
async def generate_mock_workout():
    """Route de test pour la génération IA : profil et historique mockés."""
    mock_profile = {
        "objectif": "Prise de masse musculaire",
        "niveau": "Intermédiaire",
        "restrictions": "Légère douleur au genou droit (éviter les squats lourds)",
    }
    mock_past_sessions = [
        {
            "date": "2026-05-21",
            "nom_seance": "Déchirure des Pectoraux",
            "focus": "Pectoraux et Triceps",
        }
    ]

    try:
        ai_workout = await generate_ai_workout_session(
            user_profile=mock_profile,
            past_sessions=mock_past_sessions,
        )
        return {
            "status": "success",
            "meta_data_used": {"profile": mock_profile, "history_simulated": mock_past_sessions},
            "generated_workout": ai_workout,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la génération de la séance : {e}",
        ) from e
