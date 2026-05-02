import json

import google.generativeai as genai  # type: ignore[import-untyped]

from src.models.task import ExtractedTask
from src.providers.ollama import _EXTRACT_SYSTEM


class GeminiProvider:
    def __init__(self, api_key: str, model: str = "gemini-1.5-pro") -> None:
        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(
            model_name=model,
            system_instruction=_EXTRACT_SYSTEM,
        )

    async def extract_tasks(self, text: str, source_type: str) -> list[ExtractedTask]:
        resp = await self._model.generate_content_async(
            f"以下のテキストからタスクを抽出:\n\n{text}",
            generation_config={"response_mime_type": "application/json"},
        )
        raw: list[dict[str, object]] = json.loads(resp.text)
        return [
            ExtractedTask.model_validate({**t, "source_type": source_type, "source_id": ""})
            for t in raw
            if t.get("is_task")
        ]

    async def analyze_image(self, image: bytes, comment: str) -> str:
        import io

        import PIL.Image  # type: ignore[import-untyped]

        img = PIL.Image.open(io.BytesIO(image))
        resp = await self._model.generate_content_async(
            [img, f"画像の内容を説明してください。補足コメント: {comment}"]
        )
        return str(resp.text)
