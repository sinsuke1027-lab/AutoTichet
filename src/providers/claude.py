import json

import anthropic

from src.models.task import ExtractedTask
from src.providers.ollama import _EXTRACT_SYSTEM


class ClaudeProvider:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6") -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model

    async def extract_tasks(self, text: str, source_type: str) -> list[ExtractedTask]:
        msg = await self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            system=_EXTRACT_SYSTEM,
            messages=[{"role": "user", "content": f"以下のテキストからタスクを抽出:\n\n{text}"}],
        )
        raw: list[dict[str, object]] = json.loads(msg.content[0].text)  # type: ignore[union-attr]
        return [
            ExtractedTask.model_validate({**t, "source_type": source_type, "source_id": ""})
            for t in raw
            if t.get("is_task")
        ]

    async def analyze_image(self, image: bytes, comment: str) -> str:
        import base64

        b64 = base64.b64encode(image).decode()
        msg = await self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {"type": "base64", "media_type": "image/png", "data": b64},
                        },
                        {
                            "type": "text",
                            "text": f"画像の内容を説明してください。補足コメント: {comment}",
                        },
                    ],
                }
            ],
        )
        return str(msg.content[0].text)  # type: ignore[union-attr]
