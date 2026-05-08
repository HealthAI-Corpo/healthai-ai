from fastapi import FastAPI, File, HTTPException, UploadFile
from contextlib import asynccontextmanager
from datetime import datetime

from src.database import AsyncSessionLocal
from src.services.ai_service import ai_service
from src.services.nutrition_service import enrich_with_nutrition
from src.database_mongo import mongo_db 

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialisation de la connexion MongoDB au démarrage
    mongo_db.connect()
    yield
    # Fermeture de la connexion à l'arrêt
    mongo_db.close()

app = FastAPI(title="HealthAI Vision Service", lifespan=lifespan)

@app.get("/health")
async def health():
    return {
        "status": "online",
        "service": "healthai-vision",
        "model_loaded": ai_service.model is not None,
        "mongodb_connected": mongo_db.db is not None
    }

@app.post("/analyze")
async def analyze_meal(file: UploadFile = File(...), user_id: str = "user_test_default"):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Format de fichier non supporté.")

    try:
        image_bytes = await file.read()

        # 3. IA (YOLO)
        raw_results = ai_service.analyze_image(image_bytes)

        # 4. Enrichissement SQL (Postgres)
        async with AsyncSessionLocal() as db:
            enriched_results = await enrich_with_nutrition(raw_results, db)

        # 5. Calcul des totaux pour le suivi nutritionnel
        total_repas = {
            "calories": sum(item.get('nutrition', {}).get('calories', 0) for item in enriched_results),
            "proteines": sum(item.get('nutrition', {}).get('proteines', 0) for item in enriched_results),
            "glucides": sum(item.get('nutrition', {}).get('glucides', 0) for item in enriched_results),
            "lipides": sum(item.get('nutrition', {}).get('lipides', 0) for item in enriched_results),
        }

        # 6. Sauvegarde dans MongoDB (Historique utilisateur)
        consumption_doc = {
            "user_id": user_id,
            "timestamp": datetime.utcnow(),
            "summary": total_repas,
            "details": enriched_results
        }
        
        if mongo_db.db is not None:
            await mongo_db.db.consumptions.insert_one(consumption_doc)

        return {
            "filename": file.filename,
            "user_id": user_id,
            "count": len(enriched_results),
            "total_repas": total_repas,
            "detections": enriched_results,
        }

    except Exception as e:
        print(f"Erreur CRITIQUE : {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'analyse : {str(e)}")