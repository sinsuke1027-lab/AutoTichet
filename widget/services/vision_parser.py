from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from widget.clients.ollama_client import OllamaClient
    from widget.config import Config

_EMPTY: dict = {
    "title": None,
    "due_date": None,
    "assignee_name": None,
    "priority": None,
    "description_hint": None,
}


class VisionParser:
    """vision_provider 設定に応じてローカル / Google を切り替えるルーター。

    現在 "local" のみ実装済み。"google" は config.google_api_key を設定した上で
    google-generativeai ライブラリを導入することで有効化できる。
    """

    def __init__(self, config: Config, ollama: OllamaClient) -> None:
        self._config = config
        self._ollama = ollama

    def parse_image(self, image_path: Path) -> dict:
        if self._config.vision_provider == "google":
            return self._parse_with_google(image_path)
        return self._ollama.parse_image(image_path)

    def _parse_with_google(self, image_path: Path) -> dict:
        # TODO: google-generativeai で実装
        # 1. pip install google-generativeai
        # 2. import google.generativeai as genai
        # 3. genai.configure(api_key=self._config.google_api_key)
        # 4. model = genai.GenerativeModel("gemini-2.0-flash")
        # 5. response = model.generate_content([prompt, image])
        raise NotImplementedError(
            "Google Vision API は未実装です。"
            "vision_provider を 'local' に設定するか、実装を追加してください。"
        )
