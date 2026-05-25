import os
from datetime import datetime

from bson import ObjectId
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.database_mongo import mongo_db

# Importe ton modèle de log de consommation Postgres (adapte le nom exact de ta classe si besoin)
from src.models.log_aliment import LogRepas
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

    # 4. Prompts pour l'IA (Version optimisée et blindée anti-bavardage)
    system_prompt = (
        "Tu es le chef cuisinier et nutritionniste expert de HealthAI.\n"
        "Suggère UN SEUL repas (recette) adapté aux besoins de l'utilisateur.\n\n"
        "Tu DOIS répondre EXCLUSIVEMENT sous la forme d'un objet JSON en français, "
        "sans aucun texte d'introduction ni de conclusion, et sans balises markdown "
        "(pas de ```json).\n\n"
        "Consignes strictes de formatage pour éviter les bugs :\n"
        "1. 'estimation_calories' : Donne UNIQUEMENT une valeur textuelle simple "
        "(Exemple : '650 kcal'). INTERDICTION absolue d'inclure des calculs, "
        "des divisions ou des symboles comme [ ou /.\n"
        "2. 'ingredients' : Une chaîne de caractères simple énumérant les ingrédients "
        "et leurs quantités (Exemple: '150g de poulet, 60g de riz, 1 c.à.s d'huile').\n"
        "3. Ne mets pas de crochets [] dans tes réponses."
    )

    user_prompt = (
        f"Génère une recette simple respectant STRICTEMENT ces contraintes :\n"
        f"- Objectif : {profil.objectif_principal or 'Équilibre'}\n"
        f"- Restrictions : {profil.restrictions_alimentaires or 'Aucune'}\n"
        f"- Cible calorique : Environ {int(reste_cal)} kcal "
        f"(ne montre pas de calcul, donne juste la recette pour cette cible)\n"
        f"- Protéines souhaitées : Environ {int(reste_prot)}g\n"
    )

    try:
        from healthai_common.llm import generate_meal_suggestion

        return await generate_meal_suggestion(
            OLLAMA_BASE_URL, OLLAMA_MODEL, system_prompt, user_prompt
        )
    except Exception as e:
        return {
            "titre_repas": "Salade de poulet grillé et quinoa",
            "estimation_calories": f"{int(reste_cal) if reste_cal > 200 else 400} kcal",
            "ingredients": (
                "150g de blanc de poulet, 60g de quinoa, "
                "1 tomate, 1 c.à.s d'huile d'olive"
            ),
            "instructions": (
                "Cuire le quinoa. Griller le poulet "
                "et mélanger le tout dans un bol."
            ),
            "debug_error": str(e),
        }


async def validate_and_log_meal_to_postgres(suggestion_id: str, db_sql: AsyncSession) -> dict:
    """Valide la recette stockée dans Mongo et l'écrit définitivement dans Postgres"""
    if mongo_db.db is None:
        return {"error": "Base MongoDB non connectée."}

    # 1. Récupération de la suggestion depuis MongoDB
    suggestion = await mongo_db.db.suggestions.find_one({"_id": ObjectId(suggestion_id)})
    if not suggestion:
        return {"error": "Suggestion introuvable."}
    
    if suggestion.get("status") != "completed":
        return {"error": "Cette suggestion n'a pas encore fini d'être générée ou a échoué."}

    # 2. Changement d'état de validation dans Mongo
    await mongo_db.db.suggestions.update_one(
        {"_id": ObjectId(suggestion_id)},
        {"$set": {"validation_status": "approved"}}
    )

    # 3. Récupération des infos de la recette
    recette = suggestion.get("suggestion", {})
    
    # 4. Enregistrement final dans PostgreSQL via le modèle LogRepas
    # Plus besoin de 'calories_int', Ruff est content !
    nouveau_log = LogRepas(
        id_utilisateur=int(suggestion["user_id"]),
        repas=recette.get("titre_repas", "Repas Recommandé")[:50],
        quantite=1.00,                 
        unite="portion",               
        id_aliment=1,                  # ID de ton "Repas Personnalisé IA" dans la table 'aliment'
        log_date=datetime.utcnow()     
    )
    
    db_sql.add(nouveau_log)
    await db_sql.commit()

    return {
        "message": "Repas validé et inscrit avec succès dans PostgreSQL", 
        "suggestion_id": suggestion_id
    }
