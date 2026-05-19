from typing import Any

import httpx

from src.connectors.graph_api import GraphAPIClient
from src.models.config import get_settings


class FormsConnector:
    """Microsoft Forms 回答取得コネクター（SharePoint リスト経由）"""

    BASE_URL = "https://graph.microsoft.com/v1.0"

    def __init__(self, graph_client: GraphAPIClient) -> None:
        self._graph = graph_client

    async def get_form_responses(self, since_id: str | None = None) -> list[dict[str, Any]]:
        """SharePoint リストから Forms の回答を取得する。"""
        settings = get_settings()
        if not settings.sharepoint_site_id or not settings.forms_list_id:
            return []

        url = (
            f"{self.BASE_URL}/sites/{settings.sharepoint_site_id}"
            f"/lists/{settings.forms_list_id}/items"
        )
        params: dict[str, str] = {
            "$expand": "fields",
            "$orderby": "createdDateTime asc",
        }
        if since_id:
            params["$filter"] = f"id gt {since_id}"

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url,
                headers=self._graph._headers(),
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            return list(data.get("value", []))
