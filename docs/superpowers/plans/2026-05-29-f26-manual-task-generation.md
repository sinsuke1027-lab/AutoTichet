# F-26 マニュアルから自動生成 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 手順書・マニュアルのテキストを ExtractModal の「マニュアル」タブに貼り付けるか .txt ファイルで読み込むと、AI がタスク群を自動生成して一括起票できるようにする。

**Architecture:** 既存の `POST /api/v1/tasks/extract` エンドポイントに `source_type="manual"` を追加し、`GeminiProvider.extract_tasks` 内でマニュアル専用プロンプト（`_MANUAL_SYSTEM`）へ分岐する。フロントエンドは既存の `ExtractModal` に「マニュアル」タブを追加し、.txt ファイルは `FileReader` でクライアントサイドのみで処理する（追加 API なし）。

**Tech Stack:** Python / FastAPI / Pydantic v2 / google-genai / React / TypeScript / Ant Design Upload コンポーネント

---

## ファイル構成

| ファイル | 変更内容 |
|---------|---------|
| `tests/unit/test_providers.py` | `extract_tasks` の manual/email プロンプト分岐テスト 2 件追加 |
| `src/models/task.py` | `ExtractedTask.source_type` Literal に `"manual"` 追加 |
| `src/providers/gemini.py` | `_MANUAL_SYSTEM` プロンプト追加・`extract_tasks` に source_type 分岐 |
| `frontend/src/pages/Tasks/ExtractModal.tsx` | SOURCE_OPTIONS に「マニュアル」追加・.txt ファイル読み込み UI |

---

### Task 1: テスト作成（TDD Red フェーズ）

**Files:**
- Modify: `tests/unit/test_providers.py`

**背景:** `GeminiProvider.extract_tasks` が `source_type="manual"` を受け取ったとき `_MANUAL_SYSTEM` プロンプトを使うことを確認するテストを先に書く。`_MANUAL_SYSTEM` は Task 2 まで存在しないので、インポートエラーで失敗することを確認する（TDD Red）。

- [ ] **Step 1: テストを追加する**

`tests/unit/test_providers.py` の末尾に以下を追記する（既存コードには触れない）:

```python
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.providers.gemini import GeminiProvider, _EXTRACT_SYSTEM, _MANUAL_SYSTEM  # noqa: F401


@pytest.mark.asyncio
async def test_extract_tasks_manual_uses_manual_prompt() -> None:
    """source_type='manual' のとき _MANUAL_SYSTEM プロンプトが使われる"""
    provider = GeminiProvider(api_key="dummy")
    mock_resp = MagicMock()
    mock_resp.text = json.dumps([
        {
            "is_task": True,
            "title": "手順1を実行する",
            "assignee_name": None,
            "deadline": None,
            "priority": "medium",
            "category": "その他",
            "visibility": "team",
            "confidence_score": 0.9,
        }
    ])
    with patch.object(
        provider._client.aio.models,
        "generate_content",
        new_callable=AsyncMock,
        return_value=mock_resp,
    ) as mock_gen:
        result = await provider.extract_tasks("手順書テキスト", "manual")

    call_config = mock_gen.call_args.kwargs["config"]
    assert call_config.system_instruction == _MANUAL_SYSTEM
    assert len(result) == 1
    assert result[0].title == "手順1を実行する"
    assert result[0].source_type == "manual"


@pytest.mark.asyncio
async def test_extract_tasks_email_uses_extract_prompt() -> None:
    """source_type='email' のとき _EXTRACT_SYSTEM が使われる（既存動作の保護）"""
    provider = GeminiProvider(api_key="dummy")
    mock_resp = MagicMock()
    mock_resp.text = "[]"
    with patch.object(
        provider._client.aio.models,
        "generate_content",
        new_callable=AsyncMock,
        return_value=mock_resp,
    ) as mock_gen:
        await provider.extract_tasks("メールテキスト", "email")

    call_config = mock_gen.call_args.kwargs["config"]
    assert call_config.system_instruction == _EXTRACT_SYSTEM
```

- [ ] **Step 2: テストが失敗することを確認する（Red）**

```
pytest tests/unit/test_providers.py::test_extract_tasks_manual_uses_manual_prompt tests/unit/test_providers.py::test_extract_tasks_email_uses_extract_prompt -v
```

期待: `ImportError: cannot import name '_MANUAL_SYSTEM' from 'src.providers.gemini'`

---

### Task 2: バックエンド実装

**Files:**
- Modify: `src/models/task.py`
- Modify: `src/providers/gemini.py`

**背景:** `ExtractedTask.source_type` に `"manual"` を追加し、`GeminiProvider.extract_tasks` にマニュアル専用プロンプトの分岐を追加する。

- [ ] **Step 1: `src/models/task.py` の source_type Literal を更新する**

現在の行:
```python
    source_type: Literal["email", "meeting", "chat", "onenote", "teams_bot"]
```

変更後:
```python
    source_type: Literal["email", "meeting", "chat", "onenote", "teams_bot", "manual"]
```

- [ ] **Step 2: `src/providers/gemini.py` に `_MANUAL_SYSTEM` を追加する**

ファイル先頭の `_CLARIFY_SYSTEM = ...` 定義の直後（`class GeminiProvider:` の前）に以下を追加する:

```python
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
```

- [ ] **Step 3: `src/providers/gemini.py` の `extract_tasks` メソッドを更新する**

現在の `extract_tasks` メソッド全体:
```python
    async def extract_tasks(self, text: str, source_type: str) -> list[ExtractedTask]:
        resp = await self._client.aio.models.generate_content(
            model=self._model,
            contents=f"以下のテキストからタスクを抽出:\n\n{text}",
            config=types.GenerateContentConfig(
                system_instruction=_EXTRACT_SYSTEM,
                response_mime_type="application/json",
            ),
        )
        raw: list[dict[str, object]] = json.loads(resp.text or "[]")
        return [
            ExtractedTask.model_validate({**t, "source_type": source_type, "source_id": ""})
            for t in raw
            if t.get("is_task")
        ]
```

変更後:
```python
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
```

- [ ] **Step 4: テストが通ることを確認する（Green）**

```
pytest tests/unit/test_providers.py::test_extract_tasks_manual_uses_manual_prompt tests/unit/test_providers.py::test_extract_tasks_email_uses_extract_prompt -v
```

期待: `2 passed`

- [ ] **Step 5: 全テストが壊れていないことを確認する**

```
pytest tests/ -v
```

期待: 既存テストがすべて PASS（新規 2 件含む全件グリーン）

- [ ] **Step 6: コミット**

```
git add src/models/task.py src/providers/gemini.py tests/unit/test_providers.py
git commit -m "feat: F-26 extract_tasks に manual source_type 追加・_MANUAL_SYSTEM プロンプト"
```

---

### Task 3: フロントエンド実装

**Files:**
- Modify: `frontend/src/pages/Tasks/ExtractModal.tsx`

**背景:** ExtractModal の SOURCE_OPTIONS に「マニュアル」タブを追加し、.txt ファイル読み込みボタンを実装する。ファイルの内容は FileReader でクライアントサイドのみで処理し、textarea に流し込む。追加 API コールなし。

- [ ] **Step 1: antd の `Upload` と `UploadOutlined` アイコンをインポートに追加する**

現在の antd インポート（`message,` の後）に `Upload,` を追加:
```tsx
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Col,
  DatePicker,
  Form,
  Input,
  Modal,
  Popconfirm,
  Progress,
  Radio,
  Row,
  Select,
  Space,
  Tag,
  Typography,
  Upload,
  message,
} from 'antd'
```

アイコンインポートに `UploadOutlined` を追加:
```tsx
import { EditOutlined, RiseOutlined, UploadOutlined } from '@ant-design/icons'
```

- [ ] **Step 2: SOURCE_OPTIONS に「マニュアル」を追加する**

現在の `SOURCE_OPTIONS`:
```typescript
const SOURCE_OPTIONS = [
  { label: 'メール', value: 'email' },
  { label: '会議文字起こし', value: 'meeting' },
  { label: 'チャット', value: 'chat' },
]
```

変更後:
```typescript
const SOURCE_OPTIONS = [
  { label: 'メール', value: 'email' },
  { label: '会議文字起こし', value: 'meeting' },
  { label: 'チャット', value: 'chat' },
  { label: 'マニュアル', value: 'manual' },
]
```

- [ ] **Step 3: `handleFileUpload` 関数を追加する**

`handleExtract` 関数の直前に以下を追加:
```typescript
const handleFileUpload = (file: File): false => {
  const reader = new FileReader()
  reader.onload = (e) => setText(e.target?.result as string)
  reader.readAsText(file, 'UTF-8')
  return false
}
```

- [ ] **Step 4: マニュアル選択時のファイルアップロード UI を追加する**

JSX の「入力元」ラジオグループの直後（`</div>` の後、TextArea の `<div>` の前）に以下を追加:
```tsx
{sourceType === 'manual' && (
  <Upload
    accept=".txt"
    showUploadList={false}
    beforeUpload={handleFileUpload}
  >
    <Button icon={<UploadOutlined />} size="small">
      .txt ファイルを読み込む
    </Button>
  </Upload>
)}
```

- [ ] **Step 5: TextArea の placeholder をソース別に変更する**

現在の `TextArea`:
```tsx
<TextArea
  value={text}
  onChange={(e) => setText(e.target.value)}
  rows={14}
  placeholder="会議文字起こし・メール文面・チャットコメントを貼り付けてください"
  style={{ marginTop: 8, resize: 'vertical' }}
/>
```

変更後:
```tsx
<TextArea
  value={text}
  onChange={(e) => setText(e.target.value)}
  rows={14}
  placeholder={
    sourceType === 'manual'
      ? '手順書・マニュアルのテキストを貼り付けるか、.txt ファイルを読み込んでください'
      : '会議文字起こし・メール文面・チャットコメントを貼り付けてください'
  }
  style={{ marginTop: 8, resize: 'vertical' }}
/>
```

- [ ] **Step 6: TypeScript チェックを通す**

```
cd frontend && npx tsc --noEmit
```

期待: エラーなし（出力なし）

- [ ] **Step 7: コミット**

```
git add frontend/src/pages/Tasks/ExtractModal.tsx
git commit -m "feat: F-26 ExtractModal にマニュアルタブ・.txt ファイル読み込み追加"
```
