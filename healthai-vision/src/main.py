from fastapi import FastAPI

app = FastAPI(title="HealthAI Vision Service")

@app.get("/")
async def root():
    return {"message": "Vision Service is up and running"}

@app.get("/health")
async def health():
    # Verification 
    return {"status": "online", "service": "healthai-vision"}

'''@app.post("/analyze/meal")
async def analyze_meal():
    # Route future pour YOLO
    return {"message": "Analyse d'image bientôt disponible"}'''