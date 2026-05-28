# F-33 引き継ぎドキュメント自動生成 — 設計書

最終更新: 2026-05-29

---

## 概要

| F-ID | 機能名 | 説明 |
|------|--------|------|
| F-33 | 引き継ぎドキュメント自動生成 🤖 | 自分または指定メンバーの未完了タスク（コメント付き）を AI に渡し、引き継ぎ者が即座に状況把握できる Markdown 形式の引き継ぎ書を生成する |

---

## 選定アプローチ

**Option A: 専用エンドポイント `POST /api/v1/tasks/generate-handover`**

`generate_subtasks` / `clarify_requirements` と同じパターンで専用エンドポイントを追加する。`assignee_id` パラメータを省略すると自分自身が対象になり、leader 以上のロールを持つユーザーは任意のメンバーを対象に指定できる。コメントは最新 3 件を含める。

---

## アーキテクチャ

```
[タスク一覧ページ]
  ├─ 全ユーザー: 「引き継ぎ書を生成」ボタン（自分対象）
  └─ leader/manager/admin: ユーザー Select + ボタン（他者対象）
                ↓
  POST /api/v1/tasks/generate-handover
    { assignee_id: string | null }
                ↓
  ロール検証（他者対象 → leader 以上必要）
                ↓
  DB: 未完了タスク取得（selectinload コメント最新3件）
                ↓
  テキスト整形（タスク + コメント）
                ↓
  GeminiProvider.generate_handover_doc(tasks_text)
    → _HANDOVER_SYSTEM プロンプト
                ↓
  GenerateHandoverResponse { document: str }
                ↓
  [結果モーダル] — TextArea（読み取り専用）+ コピーボタン
```

---

## バックエンド設計

### 変更ファイル

#### `src/models/task_web.py` — モデル 2 種を追加

```python
class HandoverRequest(BaseModel):
    assignee_id: str | None = None  # None = 自分自身

class GenerateHandoverResponse(BaseModel):
    document: str  # Markdown 形式の引き継ぎ書
```

#### `src/providers/gemini.py` — `_HANDOVER_SYSTEM` + `generate_handover_doc` 追加

```python
_HANDOVER_SYSTEM = (
    "あなたはプロジェクト管理の専門家です。"
    "以下の未完了タスク一覧（コメント付き）を読み、"
    "引き継ぎ者が状況を即座に把握できる引き継ぎ書をMarkdown形式で作成してください。"
    "以下を含めてください:\n"
    "1. 概要（未完了タスク数・緊急度の高いもの）\n"
    "2. タスク別の現状・残作業・注意事項\n"
    "3. 引き継ぎ先へのメッセージ\n"
    "簡潔かつ具体的に書いてください。"
)

async def generate_handover_doc(self, tasks_text: str) -> str:
    resp = await self._client.aio.models.generate_content(
        model=self._model,
        contents=f"以下の未完了タスク情報から引き継ぎ書を生成してください:\n\n{tasks_text}",
        config=types.GenerateContentConfig(
            system_instruction=_HANDOVER_SYSTEM,
        ),
    )
    return resp.text or ""
```

#### `src/api/routers/tasks_crud.py` — `POST /tasks/generate-handover` 追加

```python
class HandoverRequest(BaseModel):
    assignee_id: str | None = None

@router.post("/generate-handover", response_model=GenerateHandoverResponse)
async def generate_handover(
    body: HandoverRequest,
    db: DbDep,
    current_user: CurrentUser,
    settings: Settings = Depends(get_settings),
) -> GenerateHandoverResponse:
    target_user_id = body.assignee_id or current_user.sub

    # 他者対象の場合は leader 以上のロールが必要
    if body.assignee_id and body.assignee_id != current_user.sub:
        user_level = max((ROLE_HIERARCHY.get(r, 0) for r in current_user.roles), default=0)
        if user_level < ROLE_HIERARCHY.get("leader", 1):
            raise HTTPException(status_code=403, detail="リーダー以上の権限が必要です")

    if not settings.gemini_api_key:
        raise HTTPException(status_code=503, detail="Gemini API キーが設定されていません")

    # 未完了タスクを取得（コメントを selectinload）
    result = await db.execute(
        select(Task)
        .join(TaskAssignee, TaskAssignee.task_id == Task.id)
        .where(
            TaskAssignee.user_id == target_user_id,
            Task.status.notin_(["completed", "cancelled"]),
        )
        .options(selectinload(Task.comments))
        .order_by(Task.due_date.asc().nullslast())
    )
    tasks = result.scalars().all()

    # テキスト整形
    lines: list[str] = []
    for task in tasks:
        lines.append(f"## {task.title}")
        lines.append(f"- ステータス: {task.status}")
        lines.append(f"- 優先度: {task.priority}")
        lines.append(f"- 期限: {task.due_date or '未設定'}")
        if task.description:
            lines.append(f"- 説明: {task.description}")
        recent = sorted(task.comments, key=lambda c: c.created_at, reverse=True)[:3]
        if recent:
            lines.append("- 最近のコメント:")
            for c in recent:
                lines.append(f"  - {c.content}")
        lines.append("")
    tasks_text = "\n".join(lines)

    provider = GeminiProvider(api_key=settings.gemini_api_key, model=settings.gemini_model)
    try:
        document = await provider.generate_handover_doc(tasks_text)
    except Exception:
        logger.exception("Gemini generate_handover_doc failed")
        raise HTTPException(
            status_code=503, detail="引き継ぎ書の生成に失敗しました。しばらく後に再試行してください"
        )

    return GenerateHandoverResponse(document=document)
```

### テスト

`tests/unit/test_handover.py` — 6 件:

| テスト名 | 内容 |
|---------|------|
| `test_generate_handover_own_tasks` | assignee_id=None → 自分の未完了タスクで生成・200 |
| `test_generate_handover_for_member_by_manager` | leader ロールで assignee_id 指定 → 200 |
| `test_generate_handover_member_cannot_target_others` | member ロールで他人指定 → 403 |
| `test_generate_handover_no_tasks` | 未完了タスクなし → 200・document が空でない |
| `test_generate_handover_gemini_error` | GeminiProvider が例外 → 503 |
| `test_generate_handover_no_api_key` | gemini_api_key="" → 503 |

---

## フロントエンド設計

### 変更ファイル

#### `frontend/src/lib/api.ts` — 型と関数を追加

```typescript
export interface HandoverResponse {
  document: string
}

export async function generateHandover(assigneeId?: string): Promise<HandoverResponse> {
  const res = await apiClient.post<HandoverResponse>('/api/v1/tasks/generate-handover', {
    assignee_id: assigneeId ?? null,
  })
  return res.data
}
```

#### `frontend/src/pages/Tasks/index.tsx` — ボタン + モーダルを追加

**ステート追加:**
```typescript
const [handoverOpen, setHandoverOpen] = useState(false)
const [handoverDoc, setHandoverDoc] = useState('')
const [handoverTarget, setHandoverTarget] = useState<string | undefined>()
const generateHandoverMutation = useMutation({
  mutationFn: (assigneeId?: string) => generateHandover(assigneeId),
})
```

**ボタン配置（ヘッダー右端、「新規タスク」ボタンの隣）:**
```tsx
{canFilterByAssignee && (
  <Select
    placeholder="引き継ぎ対象者（未選択 = 自分）"
    allowClear
    options={users.map((u) => ({ label: u.display_name, value: u.user_id }))}
    value={handoverTarget}
    onChange={setHandoverTarget}
    style={{ width: 180 }}
  />
)}
<Button
  icon={<FileTextOutlined />}
  loading={generateHandoverMutation.isPending}
  onClick={async () => {
    try {
      const res = await generateHandoverMutation.mutateAsync(handoverTarget)
      setHandoverDoc(res.document)
      setHandoverOpen(true)
    } catch {
      void message.error('引き継ぎ書の生成に失敗しました')
    }
  }}
>
  引き継ぎ書を生成
</Button>
```

**結果モーダル:**
```tsx
<Modal
  title="引き継ぎ書"
  open={handoverOpen}
  onCancel={() => setHandoverOpen(false)}
  width={720}
  footer={
    <Button
      icon={<CopyOutlined />}
      onClick={() => {
        void navigator.clipboard.writeText(handoverDoc)
        void message.success('コピーしました')
      }}
    >
      クリップボードにコピー
    </Button>
  }
>
  <Input.TextArea value={handoverDoc} rows={20} readOnly style={{ fontFamily: 'monospace' }} />
</Modal>
```

**追加インポート:**
- `FileTextOutlined`, `CopyOutlined` を `@ant-design/icons` から追加
- `useMutation` を `@tanstack/react-query` から追加
- `generateHandover` を `../../lib/api` から追加

---

## 変更ファイル一覧

| ファイル | 変更種別 | 内容 |
|---------|---------|------|
| `src/models/task_web.py` | 修正 | `HandoverRequest` / `GenerateHandoverResponse` 追加 |
| `src/providers/gemini.py` | 修正 | `_HANDOVER_SYSTEM` + `generate_handover_doc` 追加 |
| `src/api/routers/tasks_crud.py` | 修正 | `POST /tasks/generate-handover` エンドポイント追加 |
| `tests/unit/test_handover.py` | 新規 | 6 件のテスト |
| `frontend/src/lib/api.ts` | 修正 | `HandoverResponse` 型 + `generateHandover` 関数 |
| `frontend/src/pages/Tasks/index.tsx` | 修正 | ボタン + ユーザー Select + 結果モーダル |

---

## 非機能要件

- `selectinload(Task.comments)` で N+1 なし
- Gemini レスポンスは `response_mime_type` を指定しない（自由形式テキスト）
- Pattern B チェックは対象外（引き継ぎ書生成はタスクデータ → AI で、外部テキスト入力でない）
- Langfuse ロギングは対象外（`generate_handover_doc` は Langfuse コンテキスト外で呼ぶ）

---

## 対象外（YAGNI）

- 引き継ぎ書のDB保存・履歴管理（生成のたびに新規生成で十分）
- PDF ダウンロード（クリップボードコピーで代替）
- プロジェクト単位の引き継ぎ書（担当者単位で十分）
- 引き継ぎ先（受取人）の指定（文書内容は受取人に依存しない）
