from typing import Any

import httpx

from src.connectors.graph_api import GraphAPIClient


class TeamsChatConnector:
    """Teams チャンネルメッセージ取得コネクター（Graph API 経由）"""

    BASE_URL = "https://graph.microsoft.com/v1.0"

    def __init__(self, graph_client: GraphAPIClient) -> None:
        self._graph = graph_client

    async def get_teams(self) -> list[dict[str, Any]]:
        """参加している Teams チーム一覧を取得する"""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/teams",
                headers=self._graph._headers(),
                params={"$select": "id,displayName"},
            )
            resp.raise_for_status()
            return list(resp.json().get("value", []))

    async def get_channels(self, team_id: str) -> list[dict[str, Any]]:
        """チームのチャンネル一覧を取得する"""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/teams/{team_id}/channels",
                headers=self._graph._headers(),
                params={"$select": "id,displayName"},
            )
            resp.raise_for_status()
            return list(resp.json().get("value", []))

    async def get_channel_messages(
        self, team_id: str, channel_id: str, top: int = 50
    ) -> list[dict[str, Any]]:
        """チャンネルの最新メッセージを取得する"""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/teams/{team_id}/channels/{channel_id}/messages",
                headers=self._graph._headers(),
                params={"$top": str(top)},
            )
            resp.raise_for_status()
            return list(resp.json().get("value", []))
