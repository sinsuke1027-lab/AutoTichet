# F-26 マニュアルから自動生成 — 設計書

最終更新: 2026-05-29

---

## 概要

| F-ID | 機能名 | 説明 |
|------|--------|------|
| F-26 | マニュアルから自動生成 🤖 | 手順書・マニュアルのテキストを貼り付けるか .txt ファイルを読み込み、AI がタスク群を自動生成する |

---

## 選定アプローチ

**Option A: 既存 `/tasks/extract` エンドポイントに "manual" source_type を追加**

`ExtractRequest.source_type` に `"manual"` を受け付け、`GeminiProvider.extract_tasks` 内でマニュアル専用の `_MANUAL_SYSTEM` プロンプトへ分岐する。フロントエンドは既存の `ExtractModal` に「マニュアル」タブ（source_type ラジオボタン）を追加するだけ。追加 API・追加 DB・追加フックなし。

---

## アーキテクチャ

```
[ExtractModal — マニュアルタブ]
  ├─ テキスト貼り付け        ─┐
  └─ .txt ファイル読み込み    ─┤ FileReader（クライアントサイド）
       （UTF-8 テキスト化）   ─┘
                ↓
  POST /api/v1/tasks/extract
    { text: "...", source_type: "manual" }
                ↓
  classify_sensitivity（Pattern B チェック）
                ↓
  GeminiProvider.extract_tasks(text, "manual")
    → _MANUAL_SYSTEM プロンプトを使用
                ↓
  list[ExtractedTask]  ← 既存モデルを流用
                ↓
  [候補カード一覧] → チェック → 一括起票
```

---

## バックエンド設計

### 変更ファイル

#### `src/models/task.py` — source_type に "manual" を追加

```python
source_type: Literal["email", "meeting", "chat", "onenote", "teams_bot", "manual"]
```

#### `src/providers/gemini.py` — _MANUAL_SYSTEM 追加・extract_tasks に分岐

```python
_MANUAL_SYSTEM = """あなたはプロジェクト管理の専門家です。
入力された手順書・マニュアルを読み、各手順・作業項目を実行可能なタスクとして抽出してください。

出力フォーマット（JSONのみ）:
[
  {
    "is_task": true,
    "title": "タスクタイトル（1〜200文字）",
    "assignee_name": null,
    "deadline": null,
    "priority": "high|medium|low",
    "category": "その他",
    "visibility": "team",
    "confidence_score": 0.0〜1.0の数値
  }
]

タスクがない場合は空リスト [] を返してください。"""
```

`extract_tasks` の変更:

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

`tasks.py` エンドポイント・`OllamaProvider` は変更なし（Ollama は Phase 3 スコープ外）。

### テスト

`tests/unit/test_providers.py` に 2 件追加:

```python
@pytest.mark.asyncio
async def test_extract_tasks_manual_uses_manual_system_prompt():
    """source_type='manual' のとき _MANUAL_SYSTEM が使われる"""
    provider = GeminiProvider(api_key="test")
    mock_response = MagicMock()
    mock_response.text = json.dumps([
        {"is_task": True, "title": "手順1を実行する", "assignee_name": None,
         "deadline": None, "priority": "medium", "category": "その他",
         "visibility": "team", "confidence_score": 0.9}
    ])
    with patch.object(provider._client.aio.models, "generate_content",
                      return_value=mock_response) as mock_gen:
        result = await provider.extract_tasks("手順書テキスト", "manual")
        call_config = mock_gen.call_args.kwargs["config"]
        assert call_config.system_instruction == _MANUAL_SYSTEM
        assert len(result) == 1
        assert result[0].title == "手順1を実行する"
        assert result[0].source_type == "manual"


@pytest.mark.asyncio
async def test_extract_tasks_non_manual_uses_extract_system_prompt():
    """source_type='email' のとき _EXTRACT_SYSTEM が使われる（既存動作の保護）"""
    provider = GeminiProvider(api_key="test")
    mock_response = MagicMock()
    mock_response.text = "[]"
    with patch.object(provider._client.aio.models, "generate_content",
                      return_value=mock_response) as mock_gen:
        await provider.extract_tasks("メールテキスト", "email")
        call_config = mock_gen.call_args.kwargs["config"]
        assert call_config.system_instruction == _EXTRACT_SYSTEM
```

---

## フロントエンド設計

### 変更ファイル

#### `frontend/src/pages/Tasks/ExtractModal.tsx`

**1. SOURCE_OPTIONS に「マニュアル」を追加**

```typescript
const SOURCE_OPTIONS = [
  { label: 'メール', value: 'email' },
  { label: '会議文字起こし', value: 'meeting' },
  { label: 'チャット', value: 'chat' },
  { label: 'マニュアル', value: 'manual' },
]
```

**2. .txt ファイル読み込みハンドラ**

`FileReader` でクライアントサイド処理。API への追加送信なし。

```typescript
const handleFileUpload = (file: File): false => {
  const reader = new FileReader()
  reader.onload = (e) => setText(e.target?.result as string)
  reader.readAsText(file, 'UTF-8')
  return false  // antd Upload の自動アップロードを防ぐ
}
```

**3. マニュアル選択時のみファイルアップロード UI を表示**

TextArea の上部に配置:

```tsx
{sourceType === 'manual' && (
  <Upload
    accept=".txt"
    showUploadList={false}
    beforeUpload={handleFileUpload}
  >
    <Button icon={<UploadOutlined />} size="small" style={{ marginBottom: 8 }}>
      .txt ファイルを読み込む
    </Button>
  </Upload>
)}
```

**4. TextArea の placeholder をソース別に変更**

```tsx
<TextArea
  placeholder={
    sourceType === 'manual'
      ? '手順書・マニュアルのテキストを貼り付けるか、.txt ファイルを読み込んでください'
      : '会議文字起こし・メール文面・チャットコメントを貼り付けてください'
  }
/>
```

---

## 変更ファイル一覧

| ファイル | 変更種別 | 内容 |
|---------|---------|------|
| `src/models/task.py` | 修正 | `source_type` Literal に `"manual"` 追加 |
| `src/providers/gemini.py` | 修正 | `_MANUAL_SYSTEM` 追加・`extract_tasks` に manual 分岐 |
| `tests/unit/test_providers.py` | 修正 | manual source_type テスト 2 件追加 |
| `frontend/src/pages/Tasks/ExtractModal.tsx` | 修正 | SOURCE_OPTIONS に「マニュアル」追加・.txt ファイル読み込み UI |

---

## 非機能要件

- 追加 API エンドポイントなし（既存 `/tasks/extract` を流用）
- 追加 DB テーブルなし
- 追加フックなし
- ファイル読み込みはクライアントサイド完結（バックエンドへのファイル転送なし）
- Pattern B チェックは既存の `classify_sensitivity` をそのまま通過
- Langfuse ロギングは既存の extract_from_text トレースに自動記録

---

## 対象外（YAGNI）

- PDF・Word（.docx）対応: テキストのみで十分
- サーバーサイドファイルアップロード: クライアントサイド FileReader で代替
- マニュアルの階層構造（章 → サブタスク）: F-32 のサブタスク自動生成で代替
- OllamaProvider への同等実装: Phase 3 スコープ外
