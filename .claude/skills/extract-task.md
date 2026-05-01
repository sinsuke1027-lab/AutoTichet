---
description: タスク抽出スキル - LangGraphエージェントのタスク抽出ノード実装・修正時の指示
---

# タスク抽出スキル

`src/agents/task_extractor.py` および `src/agents/graph.py` を実装・修正する際に使用する。

## ExtractedTask データモデル（src/models/task.py）

```python
from datetime import date
from typing import Literal
from pydantic import BaseModel

class ExtractedTask(BaseModel):
    is_task: bool
    title: str                    # 20〜60文字
    assignee: str | None
    deadline: date | None
    priority: Literal["high", "medium", "low"]
    category: Literal["HR", "IT", "総務", "その他"]
    confidence_score: float       # 0.0〜1.0
    source_type: Literal["email", "meeting"]
    source_id: str                # Graph API メッセージID
```

## LangGraph ノード一覧

| ノード名 | 責務 |
|---------|------|
| classify_sensitivity | 機密度判定（Pattern A/B振り分け） |
| extract_tasks | LLMでタスク候補を抽出 |
| match_assignee | 担当者名をユーザーリストと照合 |
| score_confidence | 信頼スコアを算出 |
| route_approval | スコアで承認フローを分岐 |
| auto_create | Plannerへ自動起票 |
| request_approval | Teamsへ承認通知送信 |
| log_only | Langfuseへログ記録のみ |

## プロンプト設計原則
1. 日本語テキストを前提とする
2. 「〜してください」「〜お願いします」「〜までに」等のフレーズをタスク候補として検出
3. 期限は相対表現（「来週」「月末」等）を絶対日付に変換する
4. 信頼スコアは根拠の明確さで算出（担当者・期限が明示的 → 高スコア）
5. 1テキストから複数タスクを抽出する場合はリストで返す

## 信頼スコア判定基準
| スコア範囲 | 条件 |
|-----------|------|
| 0.8〜1.0 | タスク・担当者・期限が全て明示的 |
| 0.5〜0.8 | タスクは明確だが担当者または期限が不明 |
| 0.0〜0.5 | タスクかどうか自体が曖昧 |
