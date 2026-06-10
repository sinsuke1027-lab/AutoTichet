from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import ollama

_SYSTEM_PROMPT = """\
タスク管理アシスタント。今日: {today}
入力からタスク情報を抽出し、JSON のみ出力（他のテキスト・コードブロック不要）。

{{"title":"タスク名(必須)","due_date":"YYYY-MM-DD or null","assignee_name":"担当者名 or null","priority":"low|medium|high|urgent or null"}}\
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
タスク管理アシスタント。今日: {today}
この画像に含まれるタスク・作業・TODO情報を読み取り、JSON のみ出力（他のテキスト不要）。

{{"title":"タスク名(必須)","due_date":"YYYY-MM-DD or null","assignee_name":"担当者名 or null","priority":"low|medium|high|urgent or null","description_hint":"補足1〜2文 or null"}}\
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
