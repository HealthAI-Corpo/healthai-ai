import httpx
from loguru import logger

from src.core.config import settings


async def verify_user_exists(user_id: int) -> bool:
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.INTERNAL_API_URL}/api/v1/users/{user_id}",
                headers={"x-api-key": settings.INTERNAL_API_KEY},
                timeout=5.0,
            )
            return response.status_code == 200
    except Exception as e:
        logger.warning("Impossible de vérifier l'utilisateur {} : {}", user_id, e)
        return True  # réseau KO → on laisse passer (résilience)
