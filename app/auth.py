from functools import lru_cache
from typing import Dict

import httpx
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from .config import Settings, get_settings

security = HTTPBearer(auto_error=True)


@lru_cache(maxsize=4)
def _jwks_client(domain: str) -> PyJWKClient:
    return PyJWKClient(f"https://{domain}/.well-known/jwks.json")


def _is_jwt(token: str) -> bool:
    """JWTs have exactly two dots (header.payload.signature)."""
    return token.count(".") == 2


def _verify_via_userinfo(token: str, domain: str) -> Dict[str, object]:
    """
    Validate an opaque access token by calling Auth0's /userinfo endpoint.
    Auth0 returns the user profile if the token is valid, 401 if not.
    """
    try:
        resp = httpx.get(
            f"https://{domain}/userinfo",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0,
        )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not reach Auth0 to validate token",
        ) from exc

    if resp.status_code == 401:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
        )
    if not resp.is_success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token validation failed",
        )

    payload = resp.json()
    if not payload.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token is missing subject")
    return payload


def verify_token(token: str, settings: Settings) -> Dict[str, object]:
    if not settings.auth0_domain:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AUTH0_DOMAIN must be configured",
        )

    # Opaque access token (no audience configured) — validate via /userinfo
    if not _is_jwt(token):
        return _verify_via_userinfo(token, settings.auth0_domain)

    # JWT access token — verify locally using JWKS
    try:
        signing_key = _jwks_client(settings.auth0_domain).get_signing_key_from_jwt(token)
        decode_kwargs: Dict[str, object] = {
            "algorithms": ["RS256"],
            "issuer": f"https://{settings.auth0_domain}/",
        }
        if settings.auth0_audience:
            decode_kwargs["audience"] = settings.auth0_audience
        else:
            decode_kwargs["options"] = {"verify_aud": False}
        payload = jwt.decode(token, signing_key.key, **decode_kwargs)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
        ) from exc

    if not payload.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token is missing subject")

    return payload


def current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    payload = verify_token(credentials.credentials, get_settings())
    return str(payload["sub"])
