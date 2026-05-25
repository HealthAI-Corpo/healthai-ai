import json
import os
from datetime import datetime

from bson import ObjectId
from healthai_common.llm import generate_llm_prediction
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.database import AsyncSessionLocal
from src.database_mongo import mongo_db
from src.models.profilsante import ProfilSante
from src.models.utilisateur import Utilisateur

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://healthai-ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")


async def generate_nutritional_advice_from_db(
    user_id: int, db_sql: AsyncSession, consumption_id: str = None
) -> dict:
    # 1. Récupérer le profil santé
    result = await db_sql.execute(
        select(ProfilSante)
        .join(Utilisateur, Utilisateur.id_utilisateur == ProfilSante.id_utilisateur)
        .where(Utilisateur.id_utilisateur == user_id)
    )
    profil = result.scalar_one_or_none()

    if not profil:
        return {"error": "Profil santé introuvable."}

    poids_actuel = float(profil.poids_kg or 70.0)
    facteur_activite = 1.2
    if profil.niveau_activite == "Modéré":
        facteur_activite = 1.4
    elif profil.niveau_activite == "Intense":
        facteur_activite = 1.6

    besoin_calorique_base = poids_actuel * 30 * facteur_activite
    cible_proteines = poids_actuel * 1.5

    # 2. Récupérer les détails du repas actuel depuis Mongo si l'ID est fourni
    current_meal_text = "Un repas vient d'être enregistré."
    if consumption_id:
        try:
            current_doc = await mongo_db.db.consumptions.find_one({"_id": ObjectId(consumption_id)})
            if current_doc:
                details = current_doc.get("details", [])
                aliments = ", ".join([item.get("display_name", "Inconnu") for item in details])
                summary = current_doc.get("summary", {})
                current_meal_text = (
                    f"L'utilisateur vient de manger : {aliments} "
                    f"({int(summary.get('calories', 0))} kcal)."
                )
        except Exception:
            pass  # Sécurité si l'ObjectId est mal formé

    # 3. Récupération des consommations globales de la journée
    # (repas actuel inclus car déjà loggé !)
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    cursor = mongo_db.db.consumptions.find({"user_id": str(user_id), "timestamp": {"$gte": today}})

    conso_jour = {"cal": 0.0, "prot": 0.0, "glu": 0.0, "eau": 0.0}
    async_docs = []
    async for doc in cursor:
        async_docs.append(doc)
        summary = doc.get("summary", {})
        conso_jour["cal"] += float(summary.get("calories", 0))
        conso_jour["prot"] += float(summary.get("proteines", 0))
        conso_jour["glu"] += float(summary.get("glucides", 0))
        conso_jour["eau"] += float(summary.get("eau_ml", 0))

    besoin_final = besoin_calorique_base
    if profil.objectif_principal == "Perte de poids":
        besoin_final = besoin_calorique_base - 500

    reste_cal = besoin_final - conso_jour["cal"]
    manque_prot = cible_proteines - conso_jour["prot"]

    # 4. Construction du Prompt Utilisateur
    user_prompt = (
        f"{current_meal_text}\n\n"
        f"Données de sa journée :\n"
        f"- Objectif : {profil.objectif_principal or 'Équilibre'}\n"
        f"- Calories consommées aujourd'hui : {int(conso_jour['cal'])} kcal sur "
        f"un objectif de {int(besoin_final)} kcal (Reste : {int(reste_cal)} kcal).\n"
        f"- Protéines consommées aujourd'hui : {int(conso_jour['prot'])}g sur "
        f"une cible de {int(cible_proteines)}g (Manque : {int(manque_prot)}g).\n"
        f"- Eau bue : {int(conso_jour['eau'])} ml sur un objectif de 2000 ml."
    )

    try:
        system_prompt = """
Tu es l'expert en nutrition HealthAI. Réponds UNIQUEMENT par un objet JSON en français.
Chaque valeur doit être une phrase de conseil textuelle simple, sans aucun code ni sous-objet.

Format obligatoire :
{
  "bilan_macros": "Met ici une phrase analysant les calories et protéines de sa journée.",
  "conseils_sante": "Met ici un conseil concret pour son hydratation et son prochain repas."
}
"""
        nutrition_schema = {
            "type": "object",
            "properties": {
                "bilan_macros": {"type": "string"},
                "conseils_sante": {"type": "string"},
            },
            "required": ["bilan_macros", "conseils_sante"],
        }
        llm_raw_result = await generate_llm_prediction(
            base_url=OLLAMA_BASE_URL,
            model_name=OLLAMA_MODEL,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_format=nutrition_schema,
            options={"temperature": 0.1, "num_predict": 120, "num_threads": 4},
        )

        if isinstance(llm_raw_result, dict):
            return llm_raw_result

        cleaned_response = str(llm_raw_result).strip()
        if cleaned_response.startswith("```"):
            lines = cleaned_response.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines[-1].startswith("```"):
                lines = lines[:-1]
            cleaned_response = "\n".join(lines).strip()

        return json.loads(cleaned_response)

    except Exception as e:
        # E501 Fix: Chaîne textuelle coupée pour ne pas saturer la ligne
        msg_repas = (
            "Ajustez vos apports sur le prochain repas en fonction de votre cible de protéines."
        )
        return {
            "statut_motivation": "Super repas enregistré ! Continuez vos efforts.",
            "analyse_macros": f"Il vous reste {int(reste_cal)} kcal à consommer.",
            "recommandation_repas": msg_repas,
            "alerte_eau": "N'oubliez pas de boire régulièrement.",
            "debug_error": str(e),
        }


async def run_ollama_in_background(user_id: int, consumption_id: str):
    """
    Exécuté en tâche de fond. Génère le conseil nutritionnel
    via Ollama et l'enregistre dans le document de consommation Mongo.
    """
    if mongo_db.db is None:
        print("[Tâche de fond] Erreur : MongoDB non connecté.")
        return

    # On ouvre une session de base de données SQL propre à ce thread de fond
    async with AsyncSessionLocal() as db_sql:
        try:
            # Appel de ta fonction existante
            conseil_ia = await generate_nutritional_advice_from_db(
                user_id=user_id, db_sql=db_sql, consumption_id=consumption_id
            )

            # Une fois qu'Ollama a fini, on injecte dans MongoDB
            await mongo_db.db.consumptions.update_one(
                {"_id": ObjectId(consumption_id)}, {"$set": {"recommandation_ia": conseil_ia}}
            )
            print(f"[Tâche de fond] Conseils IA enregistrés pour le repas {consumption_id}")

        except Exception as e:
            print(f"[Tâche de fond] Erreur lors du calcul Ollama Recommandation : {str(e)}")
            await mongo_db.db.consumptions.update_one(
                {"_id": ObjectId(consumption_id)},
                {
                    "$set": {
                        "recommandation_ia": {
                            "error": "L'IA n'a pas pu générer de conseils.",
                            "debug": str(e),
                        }
                    }
                },
            )
