import json

from google import genai
from google.genai import types

from src.models.task import ExtractedTask
from src.providers.ollama import _EXTRACT_SYSTEM


class GeminiProvider:
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash") -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model

    async def extract_tasks(self, text: str, source_type: str) -> list[ExtractedTask]:
        resp = await self._client.aio.models.generate_content(
            model=self._model,
            contents=f"以下のテキストからタスクを抽出:\n\n{text}",
            config=types.GenerateContentConfig(
                system_instruction=_EXTRACT_SYSTEM,
                response_mime_type="application/json",
            ),
        )
        raw: list[dict[str, object]] = json.loads(resp.text or "[]")
        return [
            ExtractedTask.model_validate({**t, "source_type": source_type, "source_id": ""})
            for t in raw
            if t.get("is_task")
        ]

    async def analyze_image(self, image: bytes, comment: str) -> str:
        resp = await self._client.aio.models.generate_content(
            model=self._model,
            contents=[
                types.Part.from_bytes(data=image, mime_type="image/jpeg"),
                f"画像の内容を説明してください。補足コメント: {comment}",
            ],
        )
        return resp.text or ""
