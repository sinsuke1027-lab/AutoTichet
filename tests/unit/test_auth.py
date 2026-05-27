from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from src.api.auth import TokenPayload, get_current_user, require_role


def test_token_payload_defaults() -> None:
    payload = TokenPayload(
        sub="user-123",
        name="山田太郎",
        email="yamada@example.com",
        roles=["member"],
        tid="tenant-id",
    )
    assert payload.sub == "user-123"
    assert payload.roles == ["member"]
    assert payload.name == "山田太郎"


def test_token_payload_empty_roles_default() -> None:
    payload = TokenPayload(sub="u1", tid="t1")
    assert payload.roles == []
    assert payload.name == ""
    assert payload.email == ""


@pytest.mark.asyncio
async def test_get_current_user_missing_token() -> None:
    mock_request = MagicMock()
    mock_request.headers.get.return_value = None
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(request=mock_request, credentials=None)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_require_role_insufficient_permission() -> None:
    payload = TokenPayload(sub="u1", name="Test", email="t@t.com", roles=["member"], tid="tid")
    checker = require_role("admin")
    with pytest.raises(HTTPException) as exc_info:
        await checker(current_user=payload)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_require_role_exact_match() -> None:
    payload = TokenPayload(sub="u1", name="Test", email="t@t.com", roles=["admin"], tid="tid")
    checker = require_role("admin")
    result = await checker(current_user=payload)
    assert result == payload


@pytest.mark.asyncio
async def test_require_role_higher_role_passes() -> None:
    payload = TokenPayload(sub="u1", name="Test", email="t@t.com", roles=["manager"], tid="tid")
    checker = require_role("leader")
    result = await checker(current_user=payload)
    assert result == payload


@pytest.mark.asyncio
async def test_require_role_member_cannot_access_leader() -> None:
    payload = TokenPayload(sub="u1", name="Test", email="t@t.com", roles=["member"], tid="tid")
    checker = require_role("leader")
    with pytest.raises(HTTPException) as exc_info:
        await checker(current_user=payload)
    assert exc_info.value.status_code == 403
