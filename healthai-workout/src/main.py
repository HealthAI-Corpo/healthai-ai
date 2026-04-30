from fastapi import FastAPI

app = FastAPI(title="HealthAI Workout Service")

@app.get("/")
async def root():
    return {"message": "Workout Service is up and running"}

@app.get("/health")
async def health():
    # Verification 
    return {"status": "online", "service": "healthai-workout"}

