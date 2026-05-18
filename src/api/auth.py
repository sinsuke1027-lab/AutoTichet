import time
from collections.abc import Callable, Coroutine
from typing import Annotated, Any

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from src.models.config import get_settings

_bearer = HTTPBearer(auto_error=False)

_ROLE_HIERARCHY: dict[str, int] = {
    "member": 0,
    "leader": 1,
    "manager": 2,
    "admin": 3,
}

_JWKS_TTL = 3600.0
_jwks_cache: dict[str, tuple[dict[str, Any], float]] = {}


class TokenPayload(BaseModel):
    sub: str
    name: str = ""
    email: str = ""
    roles: list[str] = []
    tid: str = ""


async def _fetch_jwks(tenant_id: str) -> dict[str, Any]:
    now = time.monotonic()
    cached = _jwks_cache.get(tenant_id)
    if cached is not None and now < cached[1]:
        return cached[0]
    url = f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
    _jwks_cache[tenant_id] = (data, now + _JWKS_TTL)
    return data


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
) -> TokenPayload:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="認証が必要です",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    settings = get_settings()
    try:
        jwks = await _fetch_jwks(settings.azure_tenant_id)
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        public_key = next((k for k in jwks["keys"] if k.get("kid") == kid), None)
        if public_key is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="署名キーが見つかりません",
            )
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=settings.azure_client_id,
        )
        return TokenPayload(
            sub=payload.get("oid", payload.get("sub", "")),
            name=payload.get("name", ""),
            email=payload.get("preferred_username", ""),
            roles=payload.get("roles", []),
            tid=payload.get("tid", ""),
        )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"トークン検証失敗: {e}",
        ) from e


def require_role(
    required_role: str,
) -> Callable[[TokenPayload], Coroutine[Any, Any, TokenPayload]]:
    async def _checker(
        current_user: Annotated[TokenPayload, Depends(get_current_user)],
    ) -> TokenPayload:
        user_level = max(
            (_ROLE_HIERARCHY.get(r, 0) for r in current_user.roles),
            default=0,
        )
        required_level = _ROLE_HIERARCHY.get(required_role, 99)
        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="権限が不足しています",
            )
        return current_user

    return _checker


CurrentUser = Annotated[TokenPayload, Depends(get_current_user)]
