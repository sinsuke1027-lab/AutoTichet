import json

from google import genai
from google.genai import types

from src.models.task import ExtractedTask
from src.providers.ollama import _EXTRACT_SYSTEM

_SUBTASK_SYSTEM = (
    "あなたはプロジェクト管理の専門家です。"
    "タスクのタイトルと説明から、そのタスクを完了するために必要なサブタスクを3〜6個提案してください。"
    "各サブタスクは具体的で実行可能な短いアクション（30文字以内）にしてください。"
    "以下のJSON形式のみで返してください。説明文は不要です:\n"
    '{"subtasks": ["サブタスク名1", "サブタスク名2", "サブタスク名3"]}'
)

_MANUAL_SYSTEM = (
    "あなたはプロジェクト管理の専門家です。"
    "入力された手順書・マニュアルを読み、各手順・作業項目を実行可能なタスクとして抽出してください。"
    "出力フォーマット（JSONのみ）:\n"
    "[\n"
    '  {"is_task": true, "title": "タスクタイトル（1〜200文字）", "assignee_name": null,\n'
    '   "deadline": null, "priority": "high|medium|low", "category": "その他",\n'
    '   "visibility": "team", "confidence_score": 0.0〜1.0の数値}\n'
    "]\n"
    "タスクがない場合は空リスト [] を返してください。"
)

_CLARIFY_SYSTEM = (
    "あなたはプロジェクト管理の専門家です。"
    "タスクのタイトルと説明を読み、完了条件が明確かどうかを判断してください。"
    "以下のJSON形式のみで返してください:\n"
    '{"has_issue": true/false, "suggestion": "改善提案（has_issueがtrueの場合のみ、1〜2文）"}\n'
    "has_issueをtrueにする条件:\n"
    "- 説明が存在しないか極めて短い（意味のある内容が10文字未満）\n"
    "- 何をもって完了とするかが不明確\n"
    "- 抽象的すぎて具体的なアクションが見えない\n"
    "上記に当てはまらない場合はhas_issue: falseを返してください。"
)


class GeminiProvider:
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash") -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model

    async def extract_tasks(self, text: str, source_type: str) -> list[ExtractedTask]:
        system = _MANUAL_SYSTEM if source_type == "manual" else _EXTRACT_SYSTEM
        prompt = (
            f"以下のマニュアル・手順書からタスクを生成:\n\n{text}"
            if source_type == "manual"
            else f"以下のテキストからタスクを抽出:\n\n{text}"
        )
        resp = await self._client.aio.models.generate_content(
            model=self._model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system,
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

    async def generate_subtasks(self, title: str, description: str | None) -> list[str]:
        prompt = f"タスクタイトル: {title}"
        if description:
            prompt += f"\n説明: {description}"
        resp = await self._client.aio.models.generate_content(
            model=self._model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=_SUBTASK_SYSTEM,
                response_mime_type="application/json",
            ),
        )
        try:
            data: dict[str, list[str]] = json.loads(resp.text or '{"subtasks": []}')
            return data.get("subtasks", [])
        except json.JSONDecodeError:
            return []

    async def clarify_requirements(self, title: str, description: str | None) -> str | None:
        prompt = f"タスクタイトル: {title}\n説明: {description or '（未記載）'}"
        resp = await self._client.aio.models.generate_content(
            model=self._model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=_CLARIFY_SYSTEM,
                response_mime_type="application/json",
            ),
        )
        try:
            data: dict[str, object] = json.loads(resp.text or '{"has_issue": false}')
            if data.get("has_issue"):
                raw_suggestion = data.get("suggestion")
                if isinstance(raw_suggestion, str) and raw_suggestion:
                    return raw_suggestion
            return None
        except (json.JSONDecodeError, ValueError):
            return None
