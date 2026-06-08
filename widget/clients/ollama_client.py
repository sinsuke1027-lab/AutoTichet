from __future__ import annotations

import json
from datetime import date

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
