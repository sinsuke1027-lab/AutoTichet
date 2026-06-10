from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

import ollama

_SYSTEM_PROMPT = """\
タスク管理アシスタント。今日: {today}
入力からタスク情報を抽出し、JSON のみ出力（他のテキスト・コードブロック不要）。

{{"title":"タスク名(必須)","due_date":"YYYY-MM-DD or null","assignee_name":"担当者名 or null","priority":"low|medium|high|urgent or null","clarifying_question":"説明文作成のためのヒアリング質問1問 or null"}}\
"""

_EMPTY: dict = {
    "title": None,
    "due_date": None,
    "assignee_name": None,
    "priority": None,
    "clarifying_question": None,
}

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

_DESCRIBE_PROMPT = """\
以下の情報をもとにタスクの説明文を1〜3文で生成してください（JSON不要・自然文で）。

元のテキスト: {original_text}
ヒアリング回答: {answer}\
"""


class OllamaClient:
    def __init__(self, model: str = "qwen2.5:1.5b", vision_model: str = "gemma4:e4b") -> None:
        self.model = model
        self.vision_model = vision_model

    def parse(self, text: str) -> dict:
        today = date.today().isoformat()
        logging.debug("OllamaClient.parse model=%s text=%r", self.model, text[:100])
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
            logging.debug("OllamaClient.parse raw=%r", raw[:300])
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start == -1 or end == 0:
                logging.warning("OllamaClient.parse: no JSON found in response")
                return dict(_EMPTY)
            result = json.loads(raw[start:end])
            logging.debug("OllamaClient.parse result=%s", result)
            return result
        except Exception as exc:
            logging.error("OllamaClient.parse error: %s", exc)
            return dict(_EMPTY)

    def parse_image(self, image_path: Path) -> dict:
        today = date.today().isoformat()
        logging.debug("OllamaClient.parse_image model=%s path=%s", self.vision_model, image_path)
        try:
            response = ollama.chat(
                model=self.vision_model,
                messages=[{
                    "role": "user",
                    "content": _VISION_PROMPT.format(today=today),
                    "images": [str(image_path)],
                }],
                options={"temperature": 0},
            )
            raw = response["message"]["content"].strip()
            logging.debug("OllamaClient.parse_image raw=%r", raw[:300])
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start == -1 or end == 0:
                logging.warning("OllamaClient.parse_image: no JSON found in response")
                return dict(_VISION_EMPTY)
            result = json.loads(raw[start:end])
            logging.debug("OllamaClient.parse_image result=%s", result)
            return result
        except Exception as exc:
            logging.error("OllamaClient.parse_image error: %s", exc)
            return dict(_VISION_EMPTY)

    def generate_description(self, original_text: str, answer: str) -> str:
        prompt = _DESCRIBE_PROMPT.format(
            original_text=original_text[:500],
            answer=answer[:200],
        )
        logging.debug("OllamaClient.generate_description model=%s", self.model)
        try:
            response = ollama.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.3},
            )
            return response["message"]["content"].strip()
        except Exception as exc:
            logging.error("OllamaClient.generate_description error: %s", exc)
            return ""
