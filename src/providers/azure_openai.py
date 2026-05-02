import json

from openai import AsyncAzureOpenAI

from src.models.task import ExtractedTask
from src.providers.ollama import _EXTRACT_SYSTEM


class AzureOpenAIProvider:
    def __init__(self, api_key: str, endpoint: str, deployment: str) -> None:
        self._client = AsyncAzureOpenAI(
            api_key=api_key,
            azure_endpoint=endpoint,
            api_version="2024-08-01-preview",
        )
        self._deployment = deployment

    async def extract_tasks(self, text: str, source_type: str) -> list[ExtractedTask]:
        resp = await self._client.chat.completions.create(
            model=self._deployment,
            messages=[
                {"role": "system", "content": _EXTRACT_SYSTEM},
                {"role": "user", "content": f"以下のテキストからタスクを抽出:\n\n{text}"},
            ],
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content or "[]"
        parsed: list[dict[str, object]] | dict[str, object] = json.loads(content)
        if isinstance(parsed, dict):
            tasks_data = parsed.get("tasks", [])
            raw: list[dict[str, object]] = tasks_data if isinstance(tasks_data, list) else []
        else:
            raw = parsed
        return [
            ExtractedTask.model_validate({**t, "source_type": source_type, "source_id": ""})
            for t in raw
            if t.get("is_task")
        ]

    async def analyze_image(self, image: bytes, comment: str) -> str:
        import base64

        b64 = base64.b64encode(image).decode()
        resp = await self._client.chat.completions.create(
            model=self._deployment,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        },
                        {
                            "type": "text",
                            "text": f"画像の内容を説明してください。補足コメント: {comment}",
                        },
                    ],
                }
            ],
        )
        return str(resp.choices[0].message.content)
