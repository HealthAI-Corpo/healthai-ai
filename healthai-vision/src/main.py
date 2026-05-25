from contextlib import asynccontextmanager
from datetime import datetime
from os import getenv

import httpx
from bson import ObjectId
from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

from src.database import AsyncSessionLocal
from src.database_mongo import mongo_db
from src.services.ai_service import ai_service
from src.services.nutrition_service import enrich_with_nutrition
from src.services.recommandation_service import (
    run_ollama_in_background,
)
from src.services.suggestion_service import suggest_meal_from_db, validate_and_log_meal_to_postgres

OLLAMA_BASE_URL = getenv("OLLAMA_BASE_URL", "http://healthai-ollama:11434")


@asynccontextmanager
async def lifespan(app: FastAPI):
    mongo_db.connect()
    yield
    mongo_db.close()


app = FastAPI(title="HealthAI Vision Service", lifespan=lifespan)


# Helper d'injection pour obtenir une session de DB Postgres facilement
async def get_db_sql():
    async with AsyncSessionLocal() as session:
        yield session


# Schémas de validation Pydantic pour les requêtes entrantes
class AdviceRequest(BaseModel):
    user_id: int
    consumption_id: str


class SuggestMealRequest(BaseModel):
    user_id: int


class ValidateSuggestionRequest(BaseModel):
    suggestion_id: str


@app.get("/health")
async def health():
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


# ==============================================================
# 1. STRATÉGIE VISION : ANALYSE PHOTO (YOLO -> MONGO)
# ==============================================================


@app.post("/analyze")
async def analyze_meal(
    file: UploadFile = File(...), user_id: str = "1", db_sql=Depends(get_db_sql)
):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Format de fichier non supporté.")

    try:
        image_bytes = await file.read()
        raw_results = ai_service.analyze_image(image_bytes)
        enriched_results = await enrich_with_nutrition(raw_results, db_sql)

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

        consumption_doc = {
            "user_id": user_id,
            "timestamp": datetime.utcnow(),
            "summary": total_repas,
            "details": enriched_results,
        }

        inserted_id = None
        if mongo_db.db is not None:
            result_mongo = await mongo_db.db.consumptions.insert_one(consumption_doc)
            inserted_id = str(result_mongo.inserted_id)

        return {
            "filename": file.filename,
            "user_id": user_id,
            "consumption_id": inserted_id,
            "count": len(enriched_results),
            "total_repas": total_repas,
            "detections": enriched_results,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'analyse : {str(e)}")


# ==============================================================
# 2. STRATÉGIE CONSEIL : BACKGROUND TASKS RECOMMANDATION
# ==============================================================




@app.post("/nutrition/ai/advice")
async def get_nutritional_advice_endpoint(
    payload: AdviceRequest, background_tasks: BackgroundTasks
):
    """
    Route immédiate : elle délègue le calcul de recommandation au service
    en tâche de fond et répond directement au Front-end.
    """
    background_tasks.add_task(
        run_ollama_in_background, user_id=payload.user_id, consumption_id=payload.consumption_id
    )
    return {
        "status": "processing",
        "message": "L'IA génère vos conseils personnalisés en tâche de fond.",
        "consumption_id": payload.consumption_id,
    }


@app.get("/nutrition/consumption/{consumption_id}")
async def get_consumption_status(consumption_id: str):
    """Le Front-end appelle cette route en polling pour afficher les conseils."""
    try:
        doc = await mongo_db.db.consumptions.find_one({"_id": ObjectId(consumption_id)})
        if not doc:
            raise HTTPException(status_code=404, detail="Repas introuvable.")

        advice = doc.get("recommandation_ia")
        return {
            "consumption_id": consumption_id,
            "status": "completed" if advice else "processing",
            "total_repas": doc.get("summary"),
            "detections": doc.get("details"),
            "recommandation_ia": advice,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==============================================================
# 3. STRATÉGIE RECETTE : SUGGESTION ET VALIDATION (MONGO -> POSTGRES)
# ==============================================================


async def run_meal_suggestion_in_background(user_id: int, suggestion_id: str):
    async with AsyncSessionLocal() as db_sql:
        try:
            suggestion_json = await suggest_meal_from_db(user_id=user_id, db_sql=db_sql)
            await mongo_db.db.suggestions.update_one(
                {"_id": ObjectId(suggestion_id)},
                {
                    "$set": {
                        "status": "completed",
                        "validation_status": "pending",
                        "suggestion": suggestion_json,
                    }
                },
            )
        except Exception as e:
            await mongo_db.db.suggestions.update_one(
                {"_id": ObjectId(suggestion_id)}, {"$set": {"status": "failed", "error": str(e)}}
            )


@app.post("/nutrition/ai/suggest-meal")
async def suggest_meal_endpoint(payload: SuggestMealRequest, background_tasks: BackgroundTasks):
    new_suggestion = {
        "user_id": str(payload.user_id),
        "timestamp": datetime.utcnow(),
        "status": "processing",
        "validation_status": "pending",
        "suggestion": None,
    }
    result = await mongo_db.db.suggestions.insert_one(new_suggestion)
    suggestion_id = str(result.inserted_id)

    background_tasks.add_task(
        run_meal_suggestion_in_background, user_id=payload.user_id, suggestion_id=suggestion_id
    )

    return {
        "status": "processing",
        "message": "L'IA concocte votre recette personnalisée...",
        "suggestion_id": suggestion_id,
    }


@app.get("/nutrition/suggestion/{suggestion_id}")
async def get_suggestion_endpoint_status(suggestion_id: str):
    try:
        doc = await mongo_db.db.suggestions.find_one({"_id": ObjectId(suggestion_id)})
        if not doc:
            raise HTTPException(status_code=404, detail="Suggestion introuvable.")
        return {
            "suggestion_id": suggestion_id,
            "status": doc.get("status"),
            "validation_status": doc.get("validation_status"),
            "resultat": doc.get("suggestion"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/nutrition/ai/validate-suggestion")
async def validate_suggestion_endpoint(
    payload: ValidateSuggestionRequest, db_sql=Depends(get_db_sql)
):
    """Nouvel Endpoint permettant de valider le repas choisi et de le pousser dans Postgres."""
    res = await validate_and_log_meal_to_postgres(payload.suggestion_id, db_sql)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res
