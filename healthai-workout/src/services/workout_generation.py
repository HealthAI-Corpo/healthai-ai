from typing import Any

from src.services.llm_service import generate_llm_prediction


async def generate_ai_workout_session(
    user_profile: dict[str, Any],
    past_sessions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Génère une séance personnalisée via Ollama à partir du profil et de l'historique."""
    history_text = "Aucune séance enregistrée pour le moment (Nouvel utilisateur)."
    if past_sessions:
        history_text = "\n".join(
            f"- {s.get('date')} : {s.get('nom_seance')} (Focus: {s.get('focus')})"
            for s in past_sessions
        )

    system_prompt = """
Tu es le coach sportif expert de l'application HealthAI.
Tu dois concevoir une séance d'entraînement sur-mesure unique et structurée.
Tu dois répondre OBLIGATOIREMENT sous forme d'un objet JSON strict en français, sans aucun blabla avant ou après.

Format JSON attendu :
{
  "titre_seance": "Nom de la séance",
  "focus_musculaire": "Muscles ciblés",
  "duree_estimee_minutes": 45,
  "difficulte": "Débutant/Intermédiaire/Avancé",
  "corps_seance": [
    {"exercice": "Nom de l'exercice", "series": 4, "repetitions": "10-12", "conseil": "Astuce"}
  ]
}
"""

    user_prompt = f"""
Voici le profil de l'utilisateur :
- Objectif : {user_profile.get("objectif")}
- Niveau : {user_profile.get("niveau")}
- Restrictions : {user_profile.get("restrictions")}

Historique de ses dernières séances (propose une suite logique COMPLÉMENTAIRE, évite de cibler le même focus) :
{history_text}

Génère la séance idéale en respectant strictement le format JSON demandé.
"""
    return await generate_llm_prediction(system_prompt=system_prompt, user_prompt=user_prompt)
