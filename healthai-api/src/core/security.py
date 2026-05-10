from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2AuthorizationCodeBearer
from src.core.config import settings

# On définit l'URL de l'autorité (Zitadel)
zitadel_auth_url = f"{settings.ZITADEL_DOMAIN}/oauth/v2/authorize"
zitadel_token_url = f"{settings.ZITADEL_DOMAIN}/oauth/v2/token"

oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=zitadel_auth_url, tokenUrl=zitadel_token_url
)


async def get_current_user(token: str = Depends(oauth2_scheme)):
    """
    Logique pour valider le token JWT auprès de Zitadel.
    À implémenter lors de la phase d'intégration Zitadel.
    """
    try:
        # Ici on ajoutera la vérification de la signature du JWT
        return {"id": "user_id_from_token", "role": "user"}
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré",
        )
