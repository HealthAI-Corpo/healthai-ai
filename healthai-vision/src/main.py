from contextlib import asynccontextmanager
from datetime import datetime
from os import getenv  # Pour récupérer dynamiquement les variables d'environnement

import httpx  # Ajout de l'import pour le ping rapide
from fastapi import FastAPI, File, HTTPException, UploadFile

from src.database import AsyncSessionLocal
from src.database_mongo import mongo_db
from src.services.ai_service import ai_service
from src.services.nutrition_service import enrich_with_nutrition
from src.services.recommandation_service import generate_nutritional_advice

# Configuration d'Ollama (Récupère les variables du .env local ou prend les valeurs de dev)
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


@app.post("/analyze")
async def analyze_meal(file: UploadFile = File(...), user_id: str = "1"):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Format de fichier non supporté.")

    try:
        image_bytes = await file.read()

        # 1. IA (YOLO)
        raw_results = ai_service.analyze_image(image_bytes)

        # 2. Traitement SQL & Recommandation
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

            # 3. Logique de Recommandation Intelligente
            has_food = total_repas["calories"] > 0
            has_water = any(item.get("display_name") == "Water" for item in enriched_results)

            if len(enriched_results) > 0 and (has_food or has_water):
                conseil = await generate_nutritional_advice(int(user_id), db)

            elif len(enriched_results) > 0 and not (has_food or has_water):
                # Cas où on détecte un objet (ex: bowl) mais qui ne contient rien de connu
                conseil = (
                    "Objet reconnu (contenant), mais le contenu alimentaire "
                    "n'a pas pu être identifié pour calculer vos apports."
                )

            else:
                # Cas où YOLO ne voit rien du tout
                conseil = (
                    "Aucun aliment reconnu. Essayez de prendre une "
                    "photo plus claire ou de plus près."
                )
        # 4. Sauvegarde dans MongoDB (Historique)
        consumption_doc = {
            "user_id": user_id,
            "timestamp": datetime.utcnow(),
            "summary": total_repas,
            "details": enriched_results,
        }

        if mongo_db.db is not None:
            await mongo_db.db.consumptions.insert_one(consumption_doc)

        # 5. Réponse finale
        return {
            "filename": file.filename,
            "user_id": user_id,
            "count": len(enriched_results),
            "total_repas": total_repas,
            "recommandation": conseil,
            "detections": enriched_results,
        }

    except Exception as e:
        print(f"Erreur CRITIQUE : {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'analyse : {str(e)}")
