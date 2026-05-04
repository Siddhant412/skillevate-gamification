from functools import lru_cache
from typing import Dict

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from .config import Settings, get_settings

security = HTTPBearer(auto_error=True)


@lru_cache(maxsize=4)
def _jwks_client(domain: str) -> PyJWKClient:
    return PyJWKClient(f"https://{domain}/.well-known/jwks.json")


def verify_token(token: str, settings: Settings) -> Dict[str, object]:
    if not settings.auth0_domain or not settings.auth0_audience:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AUTH0_DOMAIN and AUTH0_AUDIENCE must be configured",
        )

    try:
        signing_key = _jwks_client(settings.auth0_domain).get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.auth0_audience,
            issuer=f"https://{settings.auth0_domain}/",
        )
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
