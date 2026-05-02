from fastapi import FastAPI, UploadFile, File, HTTPException
from src.services.ai_service import ai_service  # On importe l'instance déjà créée
from src.core.config import settings

app = FastAPI(title="HealthAI Vision Service")

@app.get("/health")
async def health():
    # On peut même vérifier si le modèle est bien chargé
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
            detail="Format de fichier non supporté. Veuillez envoyer une image."
        )

    try:
        # 2. Lecture des octets de l'image
        image_bytes = await file.read()

        # 3. Appel au service IA
        results = ai_service.analyze_image(image_bytes)

        # 4. Retour des résultats
        return {
            "filename": file.filename,
            "count": len(results),
            "detections": results
        }

    except Exception as e:
        # Log l'erreur ici si tu as un logger
        raise HTTPException(
            status_code=500, 
            detail=f"Erreur interne lors de l'analyse : {str(e)}"
        )