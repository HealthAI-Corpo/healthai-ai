"""Authentification du gateway IA.

Trois modes (cf. `settings.AUTH_MODE`) :

- `jwks` (cible / prod) : valide l'**access token** Bearer contre les clés
  publiques Zitadel (issuer / audience / expiration / rôle optionnel), puis
  résout l'email via l'endpoint **userinfo** OIDC (l'access token Zitadel ne
  contient pas l'email — c'est volontaire). L'email résout `id_utilisateur`
  via Postgres.
- `id_token` : valide un **ID token** Zitadel et lit l'email directement dans
  le claim `email` (l'ID token le porte). Mode de transition/dépannage, qui
  pourra être retiré une fois le front câblé sur l'access token.
- `dev_stub` : court-circuite tout (dev local sans Zitadel).
"""

from __future__ import annotations

import time
from typing import Any

import httpx
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from loguru import logger

from src.core.config import settings
from src.repositories.user_repository import find_user_id_by_email

_bearer = HTTPBearer(auto_error=False)

_jwks_client: PyJWKClient | None = None
# Cache: sub -> (id_utilisateur, email, expires_at_epoch). On indexe par `sub`
# (stable, toujours présent) pour éviter de rappeler userinfo + Postgres à chaque
# requête, quel que soit le mode (jwks/id_token).
_user_cache: dict[str, tuple[int, str, float]] = {}

# Timeout des appels HTTP sortants vers Zitadel (userinfo).
_USERINFO_TIMEOUT_SECONDS = 10.0


def _build_jwks_url() -> str:
    issuer = settings.ZITADEL_ISSUER.rstrip("/")
    if not issuer:
        raise RuntimeError("ZITADEL_ISSUER manquant pour AUTH_MODE=jwks.")
    return f"{issuer}/oauth/v2/keys"


def _build_userinfo_url() -> str:
    issuer = settings.ZITADEL_ISSUER.rstrip("/")
    if not issuer:
        raise RuntimeError("ZITADEL_ISSUER manquant pour récupérer userinfo.")
    return f"{issuer}/oidc/v1/userinfo"


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(_build_jwks_url(), cache_keys=True, lifespan=3600)
    return _jwks_client


def _check_role(claims: dict[str, Any]) -> None:
    """Vérifie qu'un rôle requis est présent dans les claims Zitadel.

    Zitadel met les rôles dans `urn:zitadel:iam:org:project:roles` (dict
    {role_name: {org_id: org_domain}}). Si la conf ne demande pas de rôle, no-op.
    """
    required = settings.ZITADEL_REQUIRED_ROLE
    if not required:
        return
    roles = claims.get("urn:zitadel:iam:org:project:roles") or {}
    if required not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Rôle requis '{required}' absent du token.",
        )


async def _validate_jwt(token: str) -> dict[str, Any]:
    """Valide la signature + issuer/audience/expiration et renvoie les claims.

    Vaut pour l'access token (mode `jwks`) comme pour l'ID token (mode
    `id_token`) : les deux sont des JWT RS256 signés par la même clé Zitadel.
    """
    try:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token).key
    except (jwt.PyJWKClientError, httpx.HTTPError) as exc:
        logger.warning("JWKS Zitadel indisponible : {}", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Impossible de récupérer les clés Zitadel (JWKS).",
        ) from exc
    except jwt.InvalidTokenError as exc:
        # Token illisible (segments manquants, header KO…) avant même le décodage.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token illisible : {exc}",
        ) from exc

    try:
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=settings.JWT_AUDIENCE or None,
            issuer=settings.ZITADEL_ISSUER or None,
            options={
                "require": ["exp", "iat"],
                "verify_aud": bool(settings.JWT_AUDIENCE),
                "verify_iss": bool(settings.ZITADEL_ISSUER),
            },
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expiré.") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Token invalide : {exc}") from exc

    _check_role(claims)
    return claims


async def _fetch_email_from_userinfo(token: str) -> str:
    """Appelle l'endpoint userinfo OIDC de Zitadel pour récupérer l'email.

    L'access token Zitadel ne porte pas l'email : c'est userinfo (ou l'ID token)
    qui le fournit. On présente l'access token en Bearer ; Zitadel revalide le
    token côté serveur et renvoie les claims d'identité.
    """
    url = _build_userinfo_url()
    try:
        async with httpx.AsyncClient(timeout=_USERINFO_TIMEOUT_SECONDS) as client:
            resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})
    except httpx.HTTPError as exc:
        logger.warning("Userinfo Zitadel injoignable : {}", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Userinfo Zitadel indisponible.",
        ) from exc

    if resp.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token refusé par userinfo Zitadel.",
        )
    if resp.status_code != status.HTTP_200_OK:
        logger.warning("Userinfo a renvoyé {} : {}", resp.status_code, resp.text)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Réponse userinfo Zitadel inattendue.",
        )

    try:
        data = resp.json()
    except ValueError as exc:
        logger.warning("Userinfo Zitadel : JSON invalide ({})", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Userinfo Zitadel : réponse JSON invalide.",
        ) from exc

    email = data.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Userinfo Zitadel ne contient pas de claim 'email'.",
        )
    return email


async def _resolve_email(token: str, claims: dict[str, Any]) -> str:
    """Détermine l'email selon le mode.

    - `id_token` : l'email est dans le token (claim `email`).
    - `jwks`     : on tente d'abord le claim (au cas où le token serait enrichi),
                   sinon on interroge userinfo avec l'access token.
    """
    email = claims.get("email")
    if email:
        return email

    if settings.AUTH_MODE == "id_token":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="L'ID token ne contient pas de claim 'email'.",
        )

    return await _fetch_email_from_userinfo(token)


async def _resolve_user_id(email: str) -> int:
    """Mappe un email vers `id_utilisateur` via la base applicative."""
    user_id = await find_user_id_by_email(email)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Utilisateur '{email}' inconnu de la base applicative.",
        )
    return user_id


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict[str, Any]:
    """Dépendance FastAPI : renvoie `{id, email, sub, role}` pour l'utilisateur authentifié."""
    if settings.AUTH_MODE == "dev_stub":
        return {
            "id": settings.DEV_STUB_USER_ID,
            "email": settings.DEV_STUB_USER_EMAIL,
            "sub": f"dev-{settings.DEV_STUB_USER_ID}",
            "role": "user",
        }

    if creds is None or creds.scheme.lower() != "bearer" or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token manquant.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = creds.credentials
    claims = await _validate_jwt(token)
    sub = claims.get("sub")

    now = time.time()
    if sub:
        cached = _user_cache.get(sub)
        if cached and cached[2] > now:
            user_id, email, _ = cached
            return {"id": user_id, "email": email, "sub": sub, "role": "user"}

    email = await _resolve_email(token, claims)
    user_id = await _resolve_user_id(email)

    if sub:
        _user_cache[sub] = (user_id, email, now + settings.USER_ID_CACHE_TTL_SECONDS)

    return {"id": user_id, "email": email, "sub": sub, "role": "user"}
