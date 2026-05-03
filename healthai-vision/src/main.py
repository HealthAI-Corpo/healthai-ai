from fastapi import FastAPI, UploadFile, File, HTTPException
from src.services.ai_service import ai_service
from src.services.nutrition_service import enrich_with_nutrition
from src.database import AsyncSessionLocal  # On ne garde que l'async
from src.core.config import settings

app = FastAPI(title="HealthAI Vision Service")

@app.get("/health")
async def health():
    return {
        "status": "online",
        "service": "healthai-vision",
        "model_loaded": ai_service.model is not None
    }

@app.post("/analyze")
async def analyze_meal(file: UploadFile = File(...)):
    # 1. Vérification du format
    if not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400, 
            detail="Format de fichier non supporté."
        )

    try:
        # 2. Lecture des octets
        image_bytes = await file.read()

        # 3. IA (YOLO)
        raw_results = ai_service.analyze_image(image_bytes)

        # 4. Session Async avec gestionnaire de contexte
        # C'est ici que la magie opère
        async with AsyncSessionLocal() as db:
            enriched_results = await enrich_with_nutrition(raw_results, db)

        # 5. Retour des résultats
        return {
            "filename": file.filename,
            "count": len(enriched_results),
            "detections": enriched_results
        }

    except Exception as e:
        # On affiche l'erreur réelle dans les logs pour débugger
        print(f"Erreur CRITIQUE : {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Erreur lors de l'analyse : {str(e)}"
        )