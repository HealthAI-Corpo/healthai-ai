"""Authentification du gateway IA.

Deux modes :
- `AUTH_MODE=jwks` : valide le JWT Bearer contre les clés publiques Zitadel,
  vérifie issuer / audience / expiration / rôle optionnel, puis résout
  `id_utilisateur` via Postgres à partir de l'email du token.
- `AUTH_MODE=dev_stub` : court-circuite tout (mode dev local sans Zitadel).
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
# Cache: email -> (id_utilisateur, expires_at_epoch)
_user_id_cache: dict[str, tuple[int, float]] = {}


def _build_jwks_url() -> str:
    issuer = settings.ZITADEL_ISSUER.rstrip("/")
    if not issuer:
        raise RuntimeError("ZITADEL_ISSUER manquant pour AUTH_MODE=jwks.")
    return f"{issuer}/oauth/v2/keys"


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


async def _resolve_user_id(claims: dict[str, Any]) -> int:
    email = claims.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le token ne contient pas de claim 'email' — impossible de "
            "résoudre l'utilisateur côté IA.",
        )

    now = time.time()
    cached = _user_id_cache.get(email)
    if cached and cached[1] > now:
        return cached[0]

    user_id = await find_user_id_by_email(email)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Utilisateur '{email}' inconnu de la base applicative.",
        )
    _user_id_cache[email] = (user_id, now + settings.USER_ID_CACHE_TTL_SECONDS)
    return user_id


async def _validate_jwt(token: str) -> dict[str, Any]:
    try:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token).key
    except (jwt.PyJWKClientError, httpx.HTTPError) as exc:
        logger.warning("JWKS Zitadel indisponible : {}", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Impossible de récupérer les clés Zitadel (JWKS).",
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
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, f"Token invalide : {exc}"
        ) from exc

    _check_role(claims)
    return claims


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

    claims = await _validate_jwt(creds.credentials)
    user_id = await _resolve_user_id(claims)
    return {
        "id": user_id,
        "email": claims.get("email"),
        "sub": claims.get("sub"),
        "role": "user",
    }
