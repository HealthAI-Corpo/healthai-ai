import os
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.database_mongo import mongo_db
from src.models.profilsante import ProfilSante
from src.models.utilisateur import Utilisateur

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://healthai-ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")


async def suggest_meal_from_db(user_id: int, db_sql: AsyncSession) -> dict:
    """Calcule le besoin restant et génère une recette sur-mesure via Ollama."""
    # 1. Profil de l'utilisateur
    result = await db_sql.execute(
        select(ProfilSante)
        .join(Utilisateur, Utilisateur.id_utilisateur == ProfilSante.id_utilisateur)
        .where(Utilisateur.id_utilisateur == user_id)
    )
    profil = result.scalar_one_or_none()
    if not profil:
        return {"error": "Profil santé introuvable."}

    # 2. Besoins de base théoriques
    poids = float(profil.poids_kg or 70.0)
    facteur = 1.4 if profil.niveau_activite == "Modéré" else 1.2
    besoin_calorique = poids * 30 * facteur
    if profil.objectif_principal == "Perte de poids":
        besoin_calorique -= 500
    cible_prot = poids * 1.5

    # 3. Ce qu'il a déjà mangé aujourd'hui dans Mongo
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    cursor = mongo_db.db.consumptions.find({"user_id": str(user_id), "timestamp": {"$gte": today}})

    cal_mangees = 0.0
    prot_mangees = 0.0
    async for doc in cursor:
        summary = doc.get("summary", {})
        cal_mangees += float(summary.get("calories", 0))
        prot_mangees += float(summary.get("proteines", 0))

    reste_cal = max(0, besoin_calorique - cal_mangees)
    reste_prot = max(0, cible_prot - prot_mangees)

    # 4. Prompts pour l'IA
    system_prompt = """
Tu es le chef cuisinier et nutritionniste de HealthAI.
Suggère UN SEUL repas (recette) adapté aux besoins restants de l'utilisateur.
Réponds EXCLUSIVEMENT sous la forme d'un objet JSON en français, sans aucun code.
"""

    user_prompt = (
        f"Propose un repas adapté à ce profil :\n"
        f"- Objectif : {profil.objectif_principal or 'Équilibre'}\n"
        f"- Restrictions alimentaires : {profil.restrictions_alimentaires or 'Aucune'}\n"
        f"- Apports restants : {int(reste_cal)} kcal et {int(reste_prot)}g de protéines.\n"
        f"Génère une recette simple."
    )

    try:
        from healthai_common.llm import generate_meal_suggestion

        return await generate_meal_suggestion(
            OLLAMA_BASE_URL, OLLAMA_MODEL, system_prompt, user_prompt
        )
    except Exception as e:
        return {
            "titre_repas": "Salade de poulet grillé et quinoa",
            "estimation_calories": f"Environ {int(reste_cal) if reste_cal > 200 else 400} kcal",
            "ingredients": "Blanc de poulet, Quinoa, Tomates, Huile d'olive",
            "instructions": "Cuire le quinoa. Griller le poulet et mélanger.",
            "debug_error": str(e),
        }
