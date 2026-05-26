from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2AuthorizationCodeBearer
from src.core.config import settings

zitadel_auth_url = f"{settings.ZITADEL_DOMAIN}/oauth/v2/authorize"
zitadel_token_url = f"{settings.ZITADEL_DOMAIN}/oauth/v2/token"

oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=zitadel_auth_url, tokenUrl=zitadel_token_url
)


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """
    Décode le token Zitadel et extrait les informations de l'utilisateur.
    """
    try:
        # ⚠️ Phase d'intégration future Zitadel :
        # Ici, tu liras les clés publiques (JWKS) de Zitadel pour valider la signature.

        # Pour l'instant, on simule l'extraction du sujet (sub) qui fait office d'user_id
        user_id_from_token = "1"  # Permet de matcher avec tes données de tests

        return {"id": user_id_from_token, "role": "user"}

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide, expiré ou corrompu",
        )
