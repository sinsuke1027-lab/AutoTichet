"""LLM 抽出レスポンスの堅牢な JSON パース（issue #17）

LLM が不正な JSON・コードフェンス付き・dict ラップ等を返しても例外を伝播させず、
パース可能なタスクのみを返す。`node_extract`（ポーリング自動起票）でのクラッシュ・
無限リトライを防ぐため、各プロバイダーの ``extract_tasks`` はこのヘルパーを共用する。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import ValidationError

from src.models.task import ExtractedTask

logger = logging.getLogger(__name__)


def _strip_code_fence(text: str) -> str:
    """``` ... ``` のコードフェンスを除去する"""
    t = text.strip()
    if not t.startswith("```"):
        return t
    # 先頭の ```（言語指定を含む）行を落とす
    t = t.split("\n", 1)[1] if "\n" in t else t[3:]
    if t.rstrip().endswith("```"):
        t = t.rstrip()[:-3]
    return t.strip()


def parse_extracted_tasks(raw_text: str | None, source_type: str) -> list[ExtractedTask]:
    """LLM 応答テキストから ``ExtractedTask`` のリストを安全に構築する

    Args:
        raw_text: LLM が返した生テキスト（JSON 想定だが不正でも可）
        source_type: ソース種別（email / teams / manual など）

    Returns:
        パース・バリデーションに成功したタスクのみのリスト。
        不正な JSON・空応答の場合は空リストを返す（例外は送出しない）。
    """
    if not raw_text:
        return []

    try:
        data: Any = json.loads(_strip_code_fence(raw_text))
    except (json.JSONDecodeError, ValueError):
        logger.warning("extract_tasks: JSON パースに失敗したため空リストを返します")
        return []

    # 配列でなく {"tasks": [...]} のような dict でラップされている場合は
    # 内部の最初のリスト値を採用する
    if isinstance(data, dict):
        list_value = next((v for v in data.values() if isinstance(v, list)), None)
        data = list_value if list_value is not None else []

    if not isinstance(data, list):
        return []

    results: list[ExtractedTask] = []
    for item in data:
        if not isinstance(item, dict) or not item.get("is_task"):
            continue
        try:
            results.append(
                ExtractedTask.model_validate({**item, "source_type": source_type, "source_id": ""})
            )
        except ValidationError:
            logger.warning("extract_tasks: 不正なタスク要素をスキップしました")
            continue
    return results
