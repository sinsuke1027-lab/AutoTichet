from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import ollama

_SYSTEM_PROMPT = """\
あなたはタスク管理システムへの入力を構造化するアシスタントです。
ユーザーの入力テキストから以下の JSON のみを出力してください（説明・コードブロック不要）。

今日の日付: {today}

出力形式:
{{
  "title": "タスクタイトル（必須、日本語で簡潔に）",
  "due_date": "YYYY-MM-DD または null",
  "assignee_name": "担当者の表示名または null",
  "priority": "low|medium|high|urgent または null"
}}\
"""

_EMPTY: dict = {"title": None, "due_date": None, "assignee_name": None, "priority": None}

_VISION_EMPTY: dict = {
    "title": None,
    "due_date": None,
    "assignee_name": None,
    "priority": None,
    "description_hint": None,
}

_VISION_PROMPT = """\
画像からタスク管理に関連する情報を抽出してください。
今日の日付: {today}

以下の JSON のみを出力してください（説明・コードブロック不要）:
{{
  "title": "タスクタイトル（日本語で簡潔に、必須）",
  "due_date": "YYYY-MM-DD または null",
  "assignee_name": "担当者の表示名または null",
  "priority": "low|medium|high|urgent または null",
  "description_hint": "画像から読み取れる補足情報（1〜2文）または null"
}}\
"""


class OllamaClient:
    def __init__(self, model: str = "gemma4:e4b") -> None:
        self.model = model

    def parse(self, text: str) -> dict:
        today = date.today().isoformat()
        try:
            response = ollama.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT.format(today=today)},
                    {"role": "user", "content": text},
                ],
                options={"temperature": 0},
            )
            raw = response["message"]["content"].strip()
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start == -1 or end == 0:
                return dict(_EMPTY)
            return json.loads(raw[start:end])
        except Exception:
            return dict(_EMPTY)

    def parse_image(self, image_path: Path) -> dict:
        today = date.today().isoformat()
        try:
            response = ollama.chat(
                model=self.model,
                messages=[{
                    "role": "user",
                    "content": _VISION_PROMPT.format(today=today),
                    "images": [str(image_path)],
                }],
                options={"temperature": 0},
            )
            raw = response["message"]["content"].strip()
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start == -1 or end == 0:
                return dict(_VISION_EMPTY)
            return json.loads(raw[start:end])
        except Exception:
            return dict(_VISION_EMPTY)
