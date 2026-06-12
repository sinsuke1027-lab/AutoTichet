import base64

import httpx

from src.models.task import ExtractedTask
from src.providers.parsing import parse_extracted_tasks

_EXTRACT_SYSTEM = """あなたはタスク抽出の専門家です。与えられた日本語テキストからタスクを抽出し、JSONのみ返してください。

出力フォーマット:
[
  {
    "is_task": true,
    "title": "タスクタイトル（1〜200文字）",
    "assignee_name": "担当者名またはnull",
    "deadline": "YYYY-MM-DD形式またはnull",
    "priority": "high|medium|low",
    "category": "HR|IT|総務|その他",
    "visibility": "private|team|all",
    "confidence_score": 0.0〜1.0の数値
  }
]

タスクがない場合は空リスト [] を返してください。"""


class OllamaProvider:
    """Ollama LLMプロバイダー実装"""

    def __init__(self, host: str, model: str) -> None:
        """初期化

        Args:
            host: Ollama APIのベースURL（例: http://localhost:11434）
            model: 使用するモデル名（例: qwen2.5:14b）
        """
        self._host = host
        self._model = model

    async def extract_tasks(self, text: str, source_type: str) -> list[ExtractedTask]:
        """テキストからタスクを抽出する

        Args:
            text: 抽出対象のテキスト
            source_type: ソースの種類

        Returns:
            抽出されたタスクのリスト
        """
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self._host}/api/chat",
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": _EXTRACT_SYSTEM},
                        {
                            "role": "user",
                            "content": f"以下のテキストからタスクを抽出:\n\n{text}",
                        },
                    ],
                    "format": "json",
                    "stream": False,
                },
            )
            resp.raise_for_status()
            return parse_extracted_tasks(resp.json()["message"]["content"], source_type)


class OllamaVisionProvider:
    """Ollama ビジョン対応LLMプロバイダー実装"""

    def __init__(self, host: str, vision_model: str) -> None:
        """初期化

        Args:
            host: Ollama APIのベースURL
            vision_model: 使用するビジョンモデル名（例: llama3.2-vision）
        """
        self._host = host
        self._vision_model = vision_model

    async def analyze_image(self, image: bytes, comment: str) -> str:
        """画像を分析してテキスト説明を生成する

        Args:
            image: 画像バイナリデータ
            comment: 画像に付与されたコメント

        Returns:
            画像の説明文
        """
        b64 = base64.b64encode(image).decode()
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(
                f"{self._host}/api/chat",
                json={
                    "model": self._vision_model,
                    "messages": [
                        {
                            "role": "user",
                            "content": (f"画像の内容を説明してください。補足コメント: {comment}"),
                            "images": [b64],
                        }
                    ],
                    "stream": False,
                },
            )
            resp.raise_for_status()
            return str(resp.json()["message"]["content"])
