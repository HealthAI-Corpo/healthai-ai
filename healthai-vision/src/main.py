from contextlib import asynccontextmanager
from datetime import datetime
from os import getenv

import httpx  # Ajout de l'import pour le ping rapide
from bson import ObjectId
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

from src.database import AsyncSessionLocal
from src.database_mongo import mongo_db
from src.services.ai_service import ai_service
from src.services.nutrition_service import enrich_with_nutrition
from src.services.recommandation_service import generate_nutritional_advice_from_db
from src.services.suggestion_service import suggest_meal_from_db

OLLAMA_BASE_URL = getenv("OLLAMA_BASE_URL", "http://healthai-ollama:11434")


@asynccontextmanager
async def lifespan(app: FastAPI):
    mongo_db.connect()
    yield
    mongo_db.close()


app = FastAPI(title="HealthAI Vision Service", lifespan=lifespan)


@app.get("/health")
async def health():
    # Ping asynchrone ultra rapide en local pour vérifier si le conteneur Ollama répond
    ollama_online = False
    async with httpx.AsyncClient(timeout=2.0) as client:
        try:
            response = await client.get(f"{OLLAMA_BASE_URL}/")
            ollama_online = response.status_code == 200 and "Ollama is running" in response.text
        except Exception:
            ollama_online = False

    return {
        "status": "online",
        "service": "healthai-vision",
        "model_loaded": ai_service.model is not None,
        "mongodb_connected": mongo_db.db is not None,
        "ollama_connected": ollama_online,
    }


# 1. ROUTE D'ANALYSE INSTANTANÉE (YOLO + POSTGRES)


@app.post("/analyze")
async def analyze_meal(file: UploadFile = File(...), user_id: str = "1"):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Format de fichier non supporté.")

    try:
        image_bytes = await file.read()

        # 1. IA (YOLO) - Ultra rapide
        raw_results = ai_service.analyze_image(image_bytes)

        async with AsyncSessionLocal() as db:
            # Enrichissement calories/protéines via Postgres
            enriched_results = await enrich_with_nutrition(raw_results, db)

            # Calcul des totaux
            total_repas = {
                "calories": sum(
                    item.get("nutrition", {}).get("calories", 0) for item in enriched_results
                ),
                "proteines": sum(
                    item.get("nutrition", {}).get("proteines", 0) for item in enriched_results
                ),
                "glucides": sum(
                    item.get("nutrition", {}).get("glucides", 0) for item in enriched_results
                ),
                "lipides": sum(
                    item.get("nutrition", {}).get("lipides", 0) for item in enriched_results
                ),
                "eau_ml": sum(item.get("nutrition", {}).get("eau", 0) for item in enriched_results),
            }

        # 2. Sauvegarde immédiate dans MongoDB (Historique)
        consumption_doc = {
            "user_id": user_id,
            "timestamp": datetime.utcnow(),
            "summary": total_repas,
            "details": enriched_results,
        }

        inserted_id = None
        if mongo_db.db is not None:
            result_mongo = await mongo_db.db.consumptions.insert_one(consumption_doc)
            inserted_id = str(result_mongo.inserted_id)  # On récupère l'ID du repas stocké

        # 3. Réponse finale instantanée pour le Front
        return {
            "filename": file.filename,
            "user_id": user_id,
            # Utile pour que le front puisse demander le conseil sur CE repas précis
            "consumption_id": inserted_id,
            "count": len(enriched_results),
            "total_repas": total_repas,
            "detections": enriched_results,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'analyse : {str(e)}")


# ==============================================
# Partie Recommandation Nutritionnelle
# ==============================================


class AdviceRequest(BaseModel):
    user_id: int
    consumption_id: str | None = None  # Optionnel : ID du repas qui vient d'être scanné


async def run_ollama_in_background(user_id: int, consumption_id: str):
    """
    Cette fonction s'exécute de manière invisible en tâche de fond.
    Elle prend son temps (1 minute s'il le faut), puis enregistre le JSON final dans Mongo.
    """
    # 1. On ouvre une session de base de données SQL propre à ce thread de fond
    async with AsyncSessionLocal() as db_sql:
        try:
            # 2. On appelle ton service de recommandation (avec ton nouveau schéma simplifié)
            conseil_ia = await generate_nutritional_advice_from_db(
                user_id=user_id, db_sql=db_sql, consumption_id=consumption_id
            )

            # 3. Une fois qu'Ollama a fini, on injecte dans MongoDB
            await mongo_db.db.consumptions.update_one(
                {"_id": ObjectId(consumption_id)}, {"$set": {"recommandation_ia": conseil_ia}}
            )
            print(f"[Tâche de fond] Conseils IA enregistrés pour {consumption_id}")

        except Exception as e:
            # En tâche de fond, on ne peut pas faire de "raise HTTPException".
            # On logge l'erreur ou on l'écrit dans Mongo pour le debug.
            print(f" [Tâche de fond] Erreur lors du calcul Ollama : {str(e)}")
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


# ROUTE DE RECOMMANDATION NUTRITIONNELLE


@app.post("/nutrition/ai/advice")
async def get_nutritional_advice_endpoint(
    payload: AdviceRequest, background_tasks: BackgroundTasks
):
    """
    Route immédiate : elle lance le calcul en tâche de fond et répond
    directement au Front-end sans bloquer l'utilisateur.
    """
    if not payload.consumption_id:
        raise HTTPException(
            status_code=400,
            detail="L'ID du repas (consumption_id) est obligatoire pour cette stratégie.",
        )

    # On ajoute la lourde tâche Ollama en tâche de fond
    background_tasks.add_task(
        run_ollama_in_background, user_id=payload.user_id, consumption_id=payload.consumption_id
    )

    # Réponse INSTANTANÉE pour le front
    return {
        "status": "processing",
        "message": "L'IA génère vos conseils personnalisés en tâche de fond.",
        "consumption_id": payload.consumption_id,
    }


#  ROUTE DE VERIFICATION RECO (POLLING POUR LE FRONT)


@app.get("/nutrition/consumption/{consumption_id}")
async def get_consumption_status(consumption_id: str):
    """
    Le Front-end appelle cette route toutes les 5 ou 10 secondes.
    Dès que la clé 'recommandation_ia' apparaît, le Front affiche les conseils.
    """
    try:
        doc = await mongo_db.db.consumptions.find_one({"_id": ObjectId(consumption_id)})
        if not doc:
            raise HTTPException(status_code=404, detail="Repas introuvable.")

        # On vérifie si l'IA a fini d'écrire son résultat
        advice = doc.get("recommandation_ia")

        return {
            "consumption_id": consumption_id,
            "status": "completed" if advice else "processing",
            "total_repas": doc.get("summary"),
            "detections": doc.get("details"),
            "recommandation_ia": advice,  # Sera null tant qu'Ollama n'a pas fini
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==============================================
# Partie Suggestion repas
# ==============================================
class SuggestMealRequest(BaseModel):
    user_id: int


# Fonction exécutée en tâche de fond pour la suggestion de repas
async def run_meal_suggestion_in_background(user_id: int, suggestion_id: str):
    async with AsyncSessionLocal() as db_sql:
        try:
            # On appelle la logique métier (qu'on va ajouter au service juste après)
            suggestion_json = await suggest_meal_from_db(user_id=user_id, db_sql=db_sql)

            await mongo_db.db.suggestions.update_one(
                {"_id": ObjectId(suggestion_id)},
                {"$set": {"status": "completed", "suggestion": suggestion_json}},
            )
            print(f"[Tâche de fond] Suggestion de repas enregistrée pour {suggestion_id}")
        except Exception as e:
            print(f"[Tâche de fond] Erreur lors de la suggestion : {str(e)}")
            await mongo_db.db.suggestions.update_one(
                {"_id": ObjectId(suggestion_id)}, {"$set": {"status": "failed", "error": str(e)}}
            )


# ROUTE : SUGGÉRER UN REPAS (ASYNCHRONE)


@app.post("/nutrition/ai/suggest-meal")
async def suggest_meal_endpoint(payload: SuggestMealRequest, background_tasks: BackgroundTasks):
    """Lance la génération d'une recette sur-mesure en tâche de fond."""
    # 1. Préparation du document temporaire dans MongoDB
    new_suggestion = {
        "user_id": str(payload.user_id),
        "timestamp": datetime.utcnow(),
        "status": "processing",
        "suggestion": None,
    }
    result = await mongo_db.db.suggestions.insert_one(new_suggestion)
    suggestion_id = str(result.inserted_id)

    # 2. On délègue le travail lourd à la tâche de fond
    background_tasks.add_task(
        run_meal_suggestion_in_background, user_id=payload.user_id, suggestion_id=suggestion_id
    )

    return {
        "status": "processing",
        "message": "L'IA concocte votre recette personnalisée...",
        "suggestion_id": suggestion_id,
    }


# ROUTE : RÉCUPÉRER LA SUGGESTION (POLLING)


@app.get("/nutrition/suggestion/{suggestion_id}")
async def get_suggestion_status(suggestion_id: str):
    """Le Front appelle cette route pour afficher la recette dès qu'elle est prête."""
    try:
        doc = await mongo_db.db.suggestions.find_one({"_id": ObjectId(suggestion_id)})
        if not doc:
            raise HTTPException(status_code=404, detail="Suggestion introuvable.")
        return {
            "suggestion_id": suggestion_id,
            "status": doc.get("status"),
            "resultat": doc.get("suggestion"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
