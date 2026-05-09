from src.models.utilisateur import Utilisateur
from src.models.profilsante import ProfilSante
from sqlalchemy.future import select
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from src.database_mongo import mongo_db

async def generate_nutritional_advice(user_id: int, db_sql: AsyncSession):
    # 1. Récupérer le profil santé complet
    result = await db_sql.execute(
        select(ProfilSante)
        .join(Utilisateur, Utilisateur.id_profil_sante == ProfilSante.id_profil_sante)
        .where(Utilisateur.id_utilisateur == user_id)
    )
    profil = result.scalar_one_or_none()

    if not profil:
        return "Profil santé introuvable. Veuillez compléter vos informations."

    # 2. Calcul des besoins théoriques (TDEE)
    facteur_activite = 1.2
    if profil.niveau_activite == "Modéré": facteur_activite = 1.4
    elif profil.niveau_activite == "Intense": facteur_activite = 1.6

    besoin_calorique_base = float(profil.poids_kg) * 30 * facteur_activite
    cible_proteines = float(profil.poids_kg) * 1.5 

    # 3. Récupération de la consommation réelle du jour (MongoDB)
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    cursor = mongo_db.db.consumptions.find({
        "user_id": str(user_id), 
        "timestamp": {"$gte": today}
    })
    
    conso_jour = {"cal": 0.0, "prot": 0.0, "glu": 0.0, "eau": 0.0}
    async for doc in cursor:
        summary = doc.get('summary', {})
        conso_jour["cal"] += float(summary.get('calories', 0))
        conso_jour["prot"] += float(summary.get('proteines', 0))
        conso_jour["glu"] += float(summary.get('glucides', 0))
        conso_jour["eau"] += float(summary.get('eau_ml', 0))

    # 4. Ajustement de l'objectif selon le profil
    besoin_final = besoin_calorique_base
    if profil.objectif_principal == "Perte de poids":
        besoin_final = besoin_calorique_base - 500

    reste_cal = besoin_final - conso_jour["cal"]
    manque_prot = cible_proteines - conso_jour["prot"]
    
    # 5. Génération du message de base (Nutrition)
    advice = ""

    # --- Cas 1 : Perte de poids ---
    if profil.objectif_principal == "Perte de poids":
        limite_glucides = (besoin_final * 0.40) / 4
        
        if reste_cal < 0:
            advice = f"Quota perte de poids atteint ({int(conso_jour['cal'])} kcal). "
        elif conso_jour["glu"] > limite_glucides:
            advice = f"Reste {int(reste_cal)} kcal. Attention aux glucides ({int(conso_jour['glu'])}g), privilégiez les protéines. "
        elif reste_cal < 300:
            advice = f"Presque fini ! Reste {int(reste_cal)} kcal. Misez sur des légumes. "
        elif manque_prot > 30:
            advice = f"Reste {int(reste_cal)} kcal. Boostez les protéines (poulet, poisson) pour vos muscles. "
        else:
            advice = f"Belle progression ! Marge : {int(reste_cal)} kcal en déficit. "

    # --- Cas 2 : Prise de masse ou Sport ---
    elif "masse" in profil.objectif_principal.lower() or "sport" in str(profil.objectif_principal).lower():
        if reste_cal > 800:
            advice = f"N'oubliez pas de manger ! Il manque {int(reste_cal)} kcal. "
        elif manque_prot > 20:
            advice = f"Calories OK, mais manque {int(manque_prot)}g de protéines. "
        else:
            advice = f"Bonne gestion de votre masse. Reste {int(reste_cal)} kcal. "

    # --- Cas par défaut (Maintien) ---
    else:
        if reste_cal < 0:
            advice = f"Maintenance dépassée ({int(conso_jour['cal'])} kcal). "
        else:
            advice = f"Journée équilibrée. Reste : {int(reste_cal)} kcal. "

    # 6. Ajout de la logique d'hydratation (Suffixe)
    objectif_eau = 2000 
    if conso_jour["eau"] < objectif_eau:
        manque_eau = (objectif_eau - conso_jour["eau"]) / 1000
        advice += f" Il vous manque environ {manque_eau:.1f}L d'eau."
    else:
        advice += " Hydratation parfaite !"

    return advice