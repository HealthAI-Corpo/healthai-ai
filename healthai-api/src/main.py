"""Gateway HealthAI IA.

Sert d'unique entrée publique pour le front : reverse proxy authentifié
vers `healthai-vision` et `healthai-workout`. En production (compose
`healthai-infra`), seules les routes /vision/* et /workout/* exposées ici
sont accessibles — les micro-services restent sur le réseau interne.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from loguru import logger

from src.core.config import settings
from src.core.database import dispose_engine
from src.core.security import get_current_user
from src.schemas.health import InternalHealthResponse, StatusResponse

# Headers que la requête entrante ne doit JAMAIS pouvoir injecter / passer tels quels.
# - host : sinon le service interne refuse le routing
# - authorization : on retire le JWT externe, les services internes font confiance à X-User-Id
# - content-length : recalculé par httpx
# - x-user-id : sécurité critique — seul le gateway peut le poser après auth
_HOP_BY_HOP = {
    "host",
    "authorization",
    "content-length",
    "connection",
    "keep-alive",
    "proxy-authorization",
    "proxy-authenticate",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
    "x-user-id",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Gateway HealthAI IA — AUTH_MODE={}, VISION={}, WORKOUT={}",
        settings.AUTH_MODE,
        settings.VISION_SERVICE_URL,
        settings.WORKOUT_SERVICE_URL,
    )
    if settings.AUTH_MODE == "dev_stub":
        logger.warning(
            "AUTH_MODE=dev_stub : toutes les requêtes sont attribuées à "
            "id_utilisateur={} ({}). Ne JAMAIS utiliser en production.",
            settings.DEV_STUB_USER_ID,
            settings.DEV_STUB_USER_EMAIL,
        )
    yield
    await dispose_engine()


app = FastAPI(
    title="HealthAI Gateway",
    version="1.0.0",
    description=(
        "Point d'entrée public unique des services IA. Reverse proxy authentifié vers "
        "`healthai-vision` (`/vision/*`) et `healthai-workout` (`/workout/*`). En "
        "production l'authentification se fait via JWT Zitadel (Bearer) ; en dev local "
        "le mode `AUTH_MODE=dev_stub` court-circuite cette validation."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _sanitize_headers(headers: dict[str, str], user_id: int) -> dict[str, str]:
    cleaned = {k: v for k, v in headers.items() if k.lower() not in _HOP_BY_HOP}
    cleaned["X-User-Id"] = str(user_id)
    return cleaned


async def forward_request(
    base_service_url: str, path: str, request: Request, current_user: dict
) -> StreamingResponse:
    target_url = f"{base_service_url.rstrip('/')}/{path}"
    if request.url.query:
        target_url += f"?{request.url.query}"

    headers = _sanitize_headers(dict(request.headers), current_user["id"])

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            body = await request.body()
            upstream = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
            )
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Erreur de liaison avec le service interne : {exc}",
            ) from exc

    response_headers = {
        k: v for k, v in upstream.headers.items() if k.lower() not in {"content-encoding", "transfer-encoding", "content-length", "connection"}
    }
    return StreamingResponse(
        iter([upstream.content]),
        status_code=upstream.status_code,
        headers=response_headers,
    )


# /vision/* -> healthai-vision (port 8001 en interne)
@app.api_route(
    "/vision/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    tags=["Vision proxy"],
    summary="Reverse proxy vers healthai-vision",
    description=(
        "Préfixe ajouté par la gateway : `POST /vision/analyze` → `POST /analyze` côté "
        "vision. La gateway strip tout `X-User-Id` envoyé par le client et injecte celui "
        "résolu depuis le JWT. Cf. Swagger du service vision pour la liste détaillée."
    ),
)
async def route_to_vision(
    path: str, request: Request, current_user: dict = Depends(get_current_user)
) -> StreamingResponse:
    return await forward_request(settings.VISION_SERVICE_URL, path, request, current_user)


# /workout/* -> healthai-workout (port 8002 en interne, inclut /ai/* et /calorie-estimation/*)
@app.api_route(
    "/workout/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    tags=["Workout proxy"],
    summary="Reverse proxy vers healthai-workout",
    description=(
        "Préfixe ajouté par la gateway : `POST /workout/ai/generate-session` → "
        "`POST /ai/generate-session` côté workout. Couvre `/calorie-estimation/*`, "
        "`/ai/*`, `/recommendations/*`. Cf. Swagger du service workout."
    ),
)
async def route_to_workout(
    path: str, request: Request, current_user: dict = Depends(get_current_user)
) -> StreamingResponse:
    return await forward_request(settings.WORKOUT_SERVICE_URL, path, request, current_user)


@app.get(
    "/health",
    response_model=StatusResponse,
    tags=["Diagnostics"],
    summary="Liveness de la gateway",
)
async def health() -> StatusResponse:
    return StatusResponse(status="ok", message="HealthAI Gateway up")


@app.get(
    "/test-internal",
    response_model=InternalHealthResponse,
    tags=["Diagnostics"],
    summary="Diagnostic agrégé vision + workout",
)
async def test_internal() -> InternalHealthResponse:
    """Ping `/health` de chaque micro-service interne."""

    async def _ping(url: str) -> dict | str:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{url.rstrip('/')}/health")
                return resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text
        except Exception as exc:  # noqa: BLE001
            return f"unreachable: {exc}"

    vision, workout = await asyncio.gather(
        _ping(settings.VISION_SERVICE_URL),
        _ping(settings.WORKOUT_SERVICE_URL),
    )
    return InternalHealthResponse(gateway="ok", vision_service=vision, workout_service=workout)
