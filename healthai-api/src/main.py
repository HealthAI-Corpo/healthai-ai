import httpx
from fastapi import FastAPI
from src.core.config import settings

app = FastAPI(title="HealthAI Gateway")

@app.get("/")
async def root():
    return {"status": "online", "message": "Welcome to HealthAI API"}

@app.get("/test-internal")
async def test_internal():
    async with httpx.AsyncClient() as client:
        try:
            res_vision = await client.get(f"{settings.VISION_SERVICE_URL}/health")
            vision_status = res_vision.json()
            res_workout = await client.get(f"{settings.WORKOUT_SERVICE_URL}/health")
            workout_status = res_workout.json()
        except Exception as e:
            vision_status = f"Erreur de connexion: {str(e)}"
            workout_status = f"Erreur de connexion: {str(e)}"

    return {
        "gateway": "OK",
        "vision_service": vision_status,
        "workout_service": workout_status
    }