from typing import Any

import httpx
import msal


class GraphAPIClient:
    """MSAL client_credentials フローで Graph API を呼び出すクライアント"""

    BASE_URL = "https://graph.microsoft.com/v1.0"
    SCOPES = ["https://graph.microsoft.com/.default"]

    def __init__(self, tenant_id: str, client_id: str, client_secret: str) -> None:
        self._app: msal.ConfidentialClientApplication = msal.ConfidentialClientApplication(
            client_id,
            authority=f"https://login.microsoftonline.com/{tenant_id}",
            client_credential=client_secret,
        )

    def _get_token(self) -> str:
        result: dict[str, Any] = self._app.acquire_token_for_client(scopes=self.SCOPES)
        if "access_token" not in result:
            raise RuntimeError(f"トークン取得失敗: {result.get('error_description', '不明')}")
        return str(result["access_token"])

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type": "application/json",
        }

    async def get_unread_emails(self, user_id: str) -> list[dict[str, Any]]:
        """未読メール一覧を取得する（最大50件）"""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/users/{user_id}/messages",
                headers=self._headers(),
                params={
                    "$filter": "isRead eq false",
                    "$select": "id,subject,body,from,receivedDateTime",
                    "$top": "50",
                },
            )
            resp.raise_for_status()
            return list(resp.json().get("value", []))

    async def mark_email_read(self, user_id: str, message_id: str) -> None:
        """メールを既読にする"""
        async with httpx.AsyncClient() as client:
            resp = await client.patch(
                f"{self.BASE_URL}/users/{user_id}/messages/{message_id}",
                headers=self._headers(),
                json={"isRead": True},
            )
            resp.raise_for_status()

    async def get_meeting_transcripts(self, meeting_id: str) -> list[dict[str, Any]]:
        """Teams会議の文字起こし一覧を取得する"""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/me/onlineMeetings/{meeting_id}/transcripts",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return list(resp.json().get("value", []))

    async def get_users(self) -> list[dict[str, Any]]:
        """組織のユーザー一覧を取得する"""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/users",
                headers=self._headers(),
                params={"$select": "id,displayName,mail,department", "$top": "999"},
            )
            resp.raise_for_status()
            return list(resp.json().get("value", []))

    async def get_groups(self) -> list[dict[str, Any]]:
        """M365 グループ（部署）一覧を取得する"""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/groups",
                headers=self._headers(),
                params={
                    "$select": "id,displayName",
                    "$filter": "groupTypes/any(c:c eq 'Unified')",
                },
            )
            resp.raise_for_status()
            return list(resp.json().get("value", []))
