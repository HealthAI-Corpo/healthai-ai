import httpx
from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.responses import StreamingResponse

from src.core.config import settings
from src.core.security import get_current_user
from src.schemas.health import InternalHealthResponse

app = FastAPI(title="HealthAI Gateway")


# ==============================================================
# FONCTION MUTUALISÉE DE TRANSFERT (REVERSE PROXY)
# ==============================================================


async def forward_request(
    base_service_url: str, path: str, request: Request, current_user: dict
):
    """
    Prend une requête de la Gateway, injecte l'user_id extrait du JWT,
    et la transfère proprement au microservice interne.
    """
    # 1. On construit l'URL cible (Ex: http://healthai-vision:8001/analyze)
    target_url = f"{base_service_url}/{path}"
    if request.url.query:
        target_url += f"?{request.url.query}"

    # 2. On prépare les headers en injectant l'identité de l'utilisateur
    headers = dict(request.headers)
    headers["X-User-Id"] = str(current_user["id"])

    # Sécurité : On retire le gros JWT pour ne pas surcharger le réseau interne
    if "authorization" in headers:
        del headers["authorization"]

    # 3. Envoi asynchrone du flux (gère le JSON, le multipart form-data des images, etc.)
    async with httpx.AsyncClient() as client:
        try:
            req_body = await request.body()
            rp_resp = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=req_body,
                timeout=60.0,  # Crucial pour laisser l'IA d'Ollama répondre
            )

            return StreamingResponse(
                rp_resp.aiter_bytes(),
                status_code=rp_resp.status_code,
                headers=dict(rp_resp.headers),
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=502,
                detail=f"Erreur de liaison avec le service interne : {str(e)}",
            )


# ==============================================================
# ROUTEURS PAR SERVICES
# ==============================================================


# MICROSERVICE VISION & NUTRITION (Port 8001)
@app.api_route("/vision/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def route_to_vision(
    path: str, request: Request, current_user: dict = Depends(get_current_user)
):
    """
    Exemple Front: POST /vision/analyze  -> Appel interne: POST /analyze
    Exemple Front: POST /vision/nutrition/ai/suggest-meal -> Appel interne: POST /nutrition/ai/suggest-meal
    """
    return await forward_request(
        settings.VISION_SERVICE_URL, path, request, current_user
    )


# MICROSERVICE WORKOUT / SPORT (Port 8002)
@app.api_route("/workout/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def route_to_workout(
    path: str, request: Request, current_user: dict = Depends(get_current_user)
):
    """
    Exemple Front: GET /workout/seance/1 -> Appel interne: GET /seance/1
    """
    return await forward_request(
        settings.WORKOUT_SERVICE_URL, path, request, current_user
    )


# ==============================================================
# ROUTE DE DIAGNOSTIC
# ==============================================================


@app.get("/test-internal", response_model=InternalHealthResponse)
async def test_internal():
    # ... (Garde ton code de check /health existant inchangé) ...
    pass
