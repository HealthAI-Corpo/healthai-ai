"""Endpoints IA Ollama : génération, évaluation et explication de séances.

Chaque fonction : reconstruit le contexte utilisateur depuis la DB, construit un prompt,
appelle Ollama (JSON strict), valide la sortie, trace dans Mongo, et renvoie un dict.
"""

import json
import time
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from loguru import logger
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database_mongo import mongo_db
from src.models.log_seance import LogSeance
from src.schemas.ai_sessions import (
    EvaluateSessionsResponse,
    ExplainExercisesResponse,
    GenerateSessionResponse,
)
from src.services.context_service import get_recent_sessions, get_user_context
from src.services.llm_service import generate_llm_prediction


async def _trace_mongo(
    endpoint: str, user_id: int, duree_ms: float, extra: dict | None = None
) -> None:
    if mongo_db.db is None:
        return
    try:
        await mongo_db.db.predictions.insert_one(
            {
                "endpoint": endpoint,
                "id_utilisateur": user_id,
                "duree_traitement_ms": duree_ms,
                "timestamp": datetime.utcnow(),
                **(extra or {}),
            }
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("Trace MongoDB {} échouée : {}", endpoint, e)


def _validate_llm(raw: dict, model: type[BaseModel], endpoint: str) -> BaseModel:
    """Valide la sortie brute du LLM dans le schéma attendu, sinon 502."""
    try:
        return model.model_validate(raw)
    except ValidationError as e:
        logger.warning("Sortie LLM invalide ({}): {}", endpoint, e)
        logger.warning("Clés reçues du LLM ({}): {}", endpoint, list(raw.keys()))
        raise HTTPException(
            status_code=502,
            detail=f"Le LLM a renvoyé une structure inattendue pour {endpoint}.",
        ) from e


async def _require_context(db: AsyncSession, user_id: int) -> dict:
    context = await get_user_context(db, user_id)
    if context is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    return context


def _format_historique(sessions: list[dict]) -> str:
    if not sessions:
        return "Aucune séance enregistrée (nouvel utilisateur)."
    return "\n".join(
        f"- {s.get('date')} : {s.get('type_seance') or 'séance'} "
        f"({s.get('duree_minutes')} min, statut={s.get('statut')})"
        for s in sessions
    )


# --- generate-session -----------------------------------------------------------

async def generate_session(
    db: AsyncSession,
    user_id: int,
    contraintes: dict,
    sauvegarder: bool,
) -> dict:
    start = time.perf_counter()
    context = await _require_context(db, user_id)
    historique = _format_historique(await get_recent_sessions(db, user_id))

    system_prompt = """
Tu es le coach sportif expert de l'application HealthAI.
Tu conçois une séance d'entraînement personnalisée, structurée et sûre.
Réponds UNIQUEMENT avec un objet JSON strict en français, sans aucun texte avant ou après.

Format JSON attendu (tous les champs sont obligatoires, pas de null) :
{
  "type_seance": "Cardio | Musculation | HIIT | Yoga | Mobilité",
  "titre_seance": "Nom court de la séance",
  "duree_minutes": 45,
  "difficulte": "Débutant | Intermédiaire | Avancé",
  "objectif": "Objectif principal de la séance",
  "conseils_generaux": "Échauffement, récupération, hydratation...",
  "exercices": [
    {
      "nom": "Nom de l'exercice",
      "type": "Cardio | Force | Mobilité",
      "series": 4,
      "repetitions": 12,
      "duree_secondes": 0,
      "repos_secondes": 90,
      "muscles_cibles": "Muscles travaillés"
    }
  ]
}
"""
    user_prompt = f"""
Profil de l'utilisateur :
- Âge : {context.get('age')} ans, sexe : {context.get('sexe')}
- IMC : {context.get('imc')}, niveau d'activité : {context.get('niveau_activite')}
- Expérience sportive : {context.get('experience_sportive')}
- Objectif principal : {context.get('objectif_principal')}
- Fréquence d'entraînement : {context.get('frequence_entrainement')} séances/semaine
- Santé : {context.get('type_maladie') or 'RAS'}

Contraintes pour cette séance :
- Durée souhaitée : {contraintes.get('duree_souhaitee_minutes') or 'libre'} minutes
- Équipement disponible : {contraintes.get('equipement_disponible') or 'non précisé'}
- Focus musculaire : {contraintes.get('focus_musculaire') or 'libre'}

Historique récent (propose une séance complémentaire, évite de répéter le même focus) :
{historique}

Génère la séance idéale en respectant strictement le format JSON demandé.
"""

    raw = await generate_llm_prediction(system_prompt=system_prompt, user_prompt=user_prompt)
    resp: GenerateSessionResponse = _validate_llm(raw, GenerateSessionResponse, "generate-session")

    result: dict[str, Any] = resp.model_dump()

    if sauvegarder:
        seance = LogSeance(
            log_date=datetime.utcnow(),
            type_seance=resp.type_seance,
            duree_minutes=resp.duree_minutes,
            exercices=[e.model_dump() for e in resp.exercices],
            statut="proposee",
            id_utilisateur=user_id,
        )
        db.add(seance)
        await db.commit()
        await db.refresh(seance)
        result["id_seance_log"] = seance.id_seance_log
        result["log_date"] = seance.log_date
        result["statut"] = seance.statut

    await _trace_mongo(
        "generate-session",
        user_id,
        round((time.perf_counter() - start) * 1000, 1),
        {"sauvegarde": sauvegarder, "id_seance_log": result.get("id_seance_log")},
    )
    return result


# --- evaluate-sessions ----------------------------------------------------------

async def evaluate_sessions(db: AsyncSession, user_id: int, seances: list[dict]) -> dict:
    start = time.perf_counter()
    context = await _require_context(db, user_id)
    historique = _format_historique(await get_recent_sessions(db, user_id))

    system_prompt = """
Tu es un coach sportif expert de l'application HealthAI.
Tu évalues des séances de sport au regard du profil et des objectifs de l'utilisateur.
Réponds UNIQUEMENT avec un objet JSON strict en français, sans texte avant ou après.

Format JSON attendu :
{
  "avis_global": "Résumé de l'évaluation",
  "note_globale": 4,
  "avis_par_seance": [
    {
      "index": 0,
      "points_positifs": ["..."],
      "points_amelioration": ["..."],
      "suggestion": "..."
    }
  ]
}
"index" correspond à la position de la séance dans la liste fournie (commence à 0).
"note_globale" est un entier de 1 à 5.
"""
    user_prompt = f"""
Profil de l'utilisateur :
- Âge : {context.get('age')} ans, IMC : {context.get('imc')}
- Objectif principal : {context.get('objectif_principal')}
- Expérience sportive : {context.get('experience_sportive')}

Historique récent :
{historique}

Séances à évaluer (JSON) :
{json.dumps(seances, ensure_ascii=False)}

Évalue chaque séance et renvoie le JSON demandé.
"""

    raw = await generate_llm_prediction(system_prompt=system_prompt, user_prompt=user_prompt)
    resp = _validate_llm(raw, EvaluateSessionsResponse, "evaluate-sessions")

    await _trace_mongo(
        "evaluate-sessions",
        user_id,
        round((time.perf_counter() - start) * 1000, 1),
        {"nb_seances": len(seances)},
    )
    return resp.model_dump()


def _seance_to_eval_dict(s: LogSeance) -> dict:
    """Transforme une ligne log_seance en données transmises au LLM pour évaluation."""
    return {
        "type_seance": s.type_seance,
        "duree_minutes": float(s.duree_minutes) if s.duree_minutes is not None else None,
        "exercices": s.exercices,
        "bpm_moyen": s.bpm_moyen,
    }


async def evaluate_sessions_by_ids(db: AsyncSession, user_id: int, ids_seances: list[int]) -> dict:
    """Évalue des séances existantes désignées par leurs ids (propriété vérifiée)."""
    rows = (
        (await db.execute(select(LogSeance).where(LogSeance.id_seance_log.in_(ids_seances))))
        .scalars()
        .all()
    )
    par_id = {s.id_seance_log: s for s in rows}

    manquants = [i for i in ids_seances if i not in par_id]
    if manquants:
        raise HTTPException(status_code=404, detail=f"Séance(s) introuvable(s) : {manquants}")

    non_proprietaire = [i for i in ids_seances if par_id[i].id_utilisateur != user_id]
    if non_proprietaire:
        raise HTTPException(
            status_code=403,
            detail=f"Séance(s) n'appartenant pas à l'utilisateur : {non_proprietaire}",
        )

    seances = [_seance_to_eval_dict(par_id[i]) for i in ids_seances]
    return await evaluate_sessions(db, user_id, seances)


async def evaluate_recent_sessions(db: AsyncSession, user_id: int) -> dict:
    """Évalue les 7 dernières séances terminées + jusqu'à 5 séances prévues (plus proches)."""
    terminees = (
        (
            await db.execute(
                select(LogSeance)
                .where(LogSeance.id_utilisateur == user_id, LogSeance.statut == "terminee")
                .order_by(LogSeance.log_date.desc())
                .limit(7)
            )
        )
        .scalars()
        .all()
    )
    prevues = (
        (
            await db.execute(
                select(LogSeance)
                .where(LogSeance.id_utilisateur == user_id, LogSeance.statut == "prevue")
                .order_by(LogSeance.log_date.asc())
                .limit(5)
            )
        )
        .scalars()
        .all()
    )

    rows = list(terminees) + list(prevues)
    if not rows:
        raise HTTPException(status_code=404, detail="Aucune séance terminée ou prévue à évaluer")

    seances = [_seance_to_eval_dict(s) for s in rows]
    return await evaluate_sessions(db, user_id, seances)


# --- explain-exercises ----------------------------------------------------------

async def explain_exercises(db: AsyncSession, user_id: int, exercices: list[dict]) -> dict:
    start = time.perf_counter()
    context = await _require_context(db, user_id)

    system_prompt = """
Tu es un coach sportif expert de l'application HealthAI.
Tu expliques des exercices : technique, erreurs courantes, variantes, sécurité.
Réponds UNIQUEMENT avec un objet JSON strict en français, sans texte avant ou après.

Format JSON attendu :
{
  "explications": [
    {
      "nom": "Nom de l'exercice",
      "description": "Description courte",
      "muscles_cibles": "Muscles travaillés",
      "technique": "Mouvement étape par étape",
      "erreurs_courantes": ["..."],
      "variantes": ["..."],
      "conseils_securite": "Précautions"
    }
  ]
}
"""
    user_prompt = f"""
Profil de l'utilisateur (pour adapter le niveau d'explication) :
- Expérience sportive : {context.get('experience_sportive')}
- Santé : {context.get('type_maladie') or 'RAS'}

Exercices à expliquer (JSON) :
{json.dumps(exercices, ensure_ascii=False)}

Explique chaque exercice et renvoie le JSON demandé.
"""

    raw = await generate_llm_prediction(system_prompt=system_prompt, user_prompt=user_prompt)
    resp = _validate_llm(raw, ExplainExercisesResponse, "explain-exercises")

    await _trace_mongo(
        "explain-exercises",
        user_id,
        round((time.perf_counter() - start) * 1000, 1),
        {"nb_exercices": len(exercices)},
    )
    return resp.model_dump()
