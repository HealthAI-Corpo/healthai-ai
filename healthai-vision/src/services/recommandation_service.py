import json
import os
from datetime import datetime

# Import de ta bibliothèque partagée commune
from healthai_common.llm import generate_llm_prediction
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.database_mongo import mongo_db
from src.models.profilsante import ProfilSante
from src.models.utilisateur import Utilisateur

# Configuration des variables d'environnement pour Ollama
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://healthai-ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:1b")


async def generate_nutritional_advice(user_id: int, db_sql: AsyncSession) -> dict:
    # 1. Récupérer le profil santé (Inchangé)
    result = await db_sql.execute(
        select(ProfilSante)
        .join(Utilisateur, Utilisateur.id_utilisateur == ProfilSante.id_utilisateur)
        .where(Utilisateur.id_utilisateur == user_id)
    )
    profil = result.scalar_one_or_none()

    if not profil:
        return {"error": "Profil santé introuvable. Veuillez compléter vos informations."}

    # 2. Calcul des besoins théoriques (Inchangé)
    poids_actuel = float(profil.poids_kg or 70.0)
    facteur_activite = 1.2
    if profil.niveau_activite == "Modéré":
        facteur_activite = 1.4
    elif profil.niveau_activite == "Intense":
        facteur_activite = 1.6

    besoin_calorique_base = poids_actuel * 30 * facteur_activite
    cible_proteines = poids_actuel * 1.5

    # 3. Récupération des consommations réelles MongoDB (Inchangé)
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    cursor = mongo_db.db.consumptions.find({"user_id": str(user_id), "timestamp": {"$gte": today}})

    conso_jour = {"cal": 0.0, "prot": 0.0, "glu": 0.0, "eau": 0.0}
    async for doc in cursor:
        summary = doc.get("summary", {})
        conso_jour["cal"] += float(summary.get("calories", 0))
        conso_jour["prot"] += float(summary.get("proteines", 0))
        conso_jour["glu"] += float(summary.get("glucides", 0))
        conso_jour["eau"] += float(summary.get("eau_ml", 0))

    # 4. Ajustement selon l'objectif principal (Inchangé)
    besoin_final = besoin_calorique_base
    if profil.objectif_principal == "Perte de poids":
        besoin_final = besoin_calorique_base - 500

    reste_cal = besoin_final - conso_jour["cal"]
    manque_prot = cible_proteines - conso_jour["prot"]

    # 5. Construction du Prompt Utilisateur
    user_prompt = (
        f"Voici les données de l'utilisateur à analyser :\n"
        f"- Objectif principal : {profil.objectif_principal or 'Équilibre'}\n"
        f"- Niveau d'activité : {profil.niveau_activite or 'Sédentaire'}\n"
        f"- Restrictions alimentaires / Allergies : {profil.restrictions_alimentaires or 'Aucune'}"
        f"Bilan nutritionnel du jour :\n"
        f"- Calories consommées : {int(conso_jour['cal'])} kcal / "
        f"Objectif : {int(besoin_final)} kcal (Reste : {int(reste_cal)} kcal)\n"
        f"- Protéines consommées : {int(conso_jour['prot'])}g / "
        f"Cible : {int(cible_proteines)}g (Manque : {int(manque_prot)}g)\n"
        f"- Glucides consommés : {int(conso_jour['glu'])}g\n"
        f"- Eau bue : {int(conso_jour['eau'])} ml / Objectif : 2000 ml\n\n"
        f"Génère les conseils adaptés en respectant scrupuleusement ces métriques."
    )

    # 6. Appel de Ollama avec formatage JSON strict
    try:
        # On redemande du JSON mais de manière très guidée
        system_prompt = """
Tu es l'expert en nutrition de l'application HealthAI.
Tu dois obligatoirement répondre sous la forme d'un objet JSON strict 
en français sans aucun texte avant ni après.

Format attendu :
{
  "statut_motivation": "Une phrase d'encouragement personnalisée",
  "analyse_macros": "Une analyse rapide de ses calories et protéines restantes",
  "recommandation_repas": "Un conseil de repas concret basé sur son objectif et son manque",
  "alerte_eau": "Un conseil sur son hydratation du jour"
}
"""

        llm_raw_result = await generate_llm_prediction(
            base_url=OLLAMA_BASE_URL,
            model_name=OLLAMA_MODEL,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        # SÉCURITÉ : Si la bibliothèque te renvoie déjà un dict, on le garde
        if isinstance(llm_raw_result, dict):
            return llm_raw_result

        # NETTOYAGE : Si c'est une chaîne de caractères, on vire les balises ```json indésirables
        cleaned_response = str(llm_raw_result).strip()
        if cleaned_response.startswith("```"):
            lines = cleaned_response.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines[-1].startswith("```"):
                lines = lines[:-1]
            cleaned_response = "\n".join(lines).strip()

        # Extraction finale du dictionnaire
        return json.loads(cleaned_response)

    except Exception as e:
        # Fallback de secours si le parsing échoue quand même
        return {
            "statut_motivation": "Continuez vos efforts !",
            "analyse_macros": f"Il vous reste {int(reste_cal)} kcal à consommer aujourd'hui.",
            "recommandation_repas": (
                "Privilégiez une source de protéines maigres et des légumes de saison."
            ),
            "alerte_eau": "N'oubliez pas de boire régulièrement tout au long de la journée.",
            "debug_error": str(e),
        }
