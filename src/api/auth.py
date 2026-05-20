import json
import time
from collections.abc import Callable, Coroutine
from typing import Annotated, Any

import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.engine import get_db
from src.models.config import get_settings

_bearer = HTTPBearer(auto_error=False)

ROLE_HIERARCHY: dict[str, int] = {
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
    department_tags: list[str] = []


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
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
    db: AsyncSession = Depends(get_db),
) -> TokenPayload:
    settings = get_settings()
    if settings.dev_mode:
        dev_header = request.headers.get("X-Dev-User")
        if dev_header:
            try:
                dev_data = json.loads(dev_header)
                return TokenPayload(
                    sub=dev_data.get("userId", "dev-user"),
                    name=dev_data.get("displayName", "Dev User"),
                    email=dev_data.get("email", "dev@example.com"),
                    roles=[dev_data.get("role", "member")],
                    tid="dev",
                    department_tags=dev_data.get("departmentTags", []),
                )
            except (json.JSONDecodeError, KeyError):
                pass

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="認証が必要です",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
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
        sub = payload.get("oid", payload.get("sub", ""))

        # DB から UserProfile を取得（循環インポート回避のため関数内でインポート）
        from src.db.models import UserProfile  # noqa: PLC0415

        profile_result = await db.execute(select(UserProfile).where(UserProfile.user_id == sub))
        profile = profile_result.scalar_one_or_none()

        raw_roles: list[str] = payload.get("roles", [])
        if raw_roles:
            # JWT に roles あり → 本番（Entra ID App Roles）
            roles = raw_roles
        else:
            # JWT に roles なし → 開発環境（DB fallback）
            roles = [profile.role] if profile else ["member"]

        department_tags: list[str] = list(profile.department_tags) if profile else []

        return TokenPayload(
            sub=sub,
            name=payload.get("name", ""),
            email=payload.get("preferred_username", ""),
            roles=roles,
            tid=payload.get("tid", ""),
            department_tags=department_tags,
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
            (ROLE_HIERARCHY.get(r, 0) for r in current_user.roles),
            default=0,
        )
        required_level = ROLE_HIERARCHY.get(required_role, 99)
        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="権限が不足しています",
            )
        return current_user

    return _checker


CurrentUser = Annotated[TokenPayload, Depends(get_current_user)]
