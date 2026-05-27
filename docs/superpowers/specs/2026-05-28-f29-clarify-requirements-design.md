# F-29 タスク要件の明確化プロンプト 設計書

**最終更新:** 2026-05-28
**ステータス:** 承認済み
**対応要件:** F-29「完了条件等の不足を AI が検知し追記を促す」（Should / Phase 2）

---

## 1. 概要

タスク詳細の「詳細」タブに「AI チェック」ボタンを配置する。
押下時にルールベース + Gemini AI でタスクの不足項目を検知し、`Alert` コンポーネントで改善提案を表示する。

**検知対象:**

| 検知方式 | 対象フィールド | 判定条件 |
|---------|--------------|---------|
| ルールベース | `due_date` | `null` |
| ルールベース | `assignees` | 空配列 |
| Gemini AI | `description` | 完了条件が不明確・説明が曖昧または未記載 |

---

## 2. 変更ファイル

| ファイル | 変更内容 |
|---------|---------|
| `src/models/task_web.py` | `ClarifyIssue` / `ClarifyRequirementsResponse` モデル追加 |
| `src/providers/gemini.py` | `clarify_requirements()` メソッド追加 |
| `src/api/routers/tasks_crud.py` | `POST /{task_id}/clarify-requirements` エンドポイント追加 |
| `frontend/src/hooks/useTaskDetails.ts` | `useClarifyRequirements()` フック追加 |
| `frontend/src/pages/Tasks/TaskDetail.tsx` | AI チェックボタン + Alert 表示追加 |

新規ファイル: `tests/unit/test_clarify_requirements.py`

---

## 3. バックエンド

### 3-1. Pydantic モデル（`src/models/task_web.py` に追加）

```python
class ClarifyIssue(BaseModel):
    field: str          # "due_date" | "assignees" | "description"
    message: str        # ユーザー向けメッセージ
    suggestion: str | None  # AI 提案文（description のみ）、ルールベースは None

class ClarifyRequirementsResponse(BaseModel):
    issues: list[ClarifyIssue]  # 空リスト = 問題なし
```

### 3-2. Gemini メソッド（`src/providers/gemini.py` に追加）

```python
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
            return str(data.get("suggestion", ""))
        return None
    except json.JSONDecodeError:
        return None
```

### 3-3. エンドポイント（`src/api/routers/tasks_crud.py` に追加）

```
POST /api/v1/tasks/{task_id}/clarify-requirements
```

| 項目 | 内容 |
|------|------|
| 認証 | 全認証済みユーザー |
| タスク不存在時 | 404 |
| Gemini APIキー未設定 | ルールチェック結果のみ返す（503 にしない） |

**処理フロー:**

1. タスク + assignees を取得（なければ 404）
2. ルールチェック:
   - `task.due_date is None` → `ClarifyIssue(field="due_date", message="期限が設定されていません", suggestion=None)`
   - `assignees == []` → `ClarifyIssue(field="assignees", message="担当者が設定されていません", suggestion=None)`
3. `settings.google_api_key` が設定されている場合のみ Gemini 呼び出し:
   - `suggestion = await provider.clarify_requirements(task.title, task.description)`
   - `suggestion is not None` → `ClarifyIssue(field="description", message="完了条件が不明確です", suggestion=suggestion)`
4. `ClarifyRequirementsResponse(issues=issues)` を返す

---

## 4. フロントエンド

### 4-1. フック（`frontend/src/hooks/useTaskDetails.ts` に追加）

```typescript
interface ClarifyIssue {
  field: string
  message: string
  suggestion: string | null
}

interface ClarifyRequirementsData {
  issues: ClarifyIssue[]
}

export function useClarifyRequirements(taskId: string) {
  return useMutation<ClarifyRequirementsData>({
    mutationFn: async () => {
      const { data } = await api.post<ClarifyRequirementsData>(
        `/tasks/${taskId}/clarify-requirements`,
      )
      return data
    },
  })
}
```

### 4-2. UI（`frontend/src/pages/Tasks/TaskDetail.tsx` の詳細タブに追加）

詳細タブの `<Descriptions>` の下に以下を追加:

```
[🤖 AI チェック]  ← Button（ローディングスピナー付き）

（ボタン押下後）

┌─ 警告 ─────────────────────────────────────────────────┐
│ 以下の項目を確認してください:                              │
│  • 期限が設定されていません                                │
│  • 担当者が設定されていません                              │
│  • 完了条件: 「〇〇が完了したら終了」のような               │
│    受け入れ基準を追加することをお勧めします                  │
└────────────────────────────────────────────────────────┘
```

- 問題あり → `<Alert type="warning">` + `description` に issues をリスト表示
- 問題なし（`issues: []`）→ `<Alert type="success" message="問題は検出されませんでした" />`
- ロード中 → ボタンの `loading` prop で表現（Alert は表示しない）

---

## 5. テスト

**ファイル:** `tests/unit/test_clarify_requirements.py`

| # | テストケース | 検証内容 |
|---|------------|---------|
| 1 | `due_date` が null | issues に `field="due_date"` が含まれる |
| 2 | `assignees` が空 | issues に `field="assignees"` が含まれる |
| 3 | due_date あり・assignees あり・Gemini が問題なし | `issues: []` |
| 4 | タスク不存在 | 404 |
| 5 | Gemini APIキー未設定 | ルールチェック結果のみ返す（503 にならない） |
| 6 | Gemini が有問題と判定 | issues に `field="description"` + `suggestion` が含まれる |

---

## 6. スコープ外

- 問題フィールドへのナビゲーションリンク
- 提案文のワンクリック自動入力
- 定期的な自動チェック・バッジ表示
