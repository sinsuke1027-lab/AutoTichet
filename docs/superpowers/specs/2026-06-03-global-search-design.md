# 横断全文検索（Cmd+K コマンドパレット）設計書

> **For agentic workers:** この設計書を実装する際は `superpowers:writing-plans` スキルで実装計画を作成してから着手すること。

**Goal:** タスク名・説明・コメントを横断検索できる Cmd+K コマンドパレットをアプリ全体に追加する。

**Architecture:** バックエンドは新規ルーター `search.py` に統合エンドポイント `GET /api/v1/search?q=` を追加し、タスクとコメントを 1 クエリで検索して task_id 単位に重複排除する。フロントエンドは `CommandPalette.tsx` コンポーネントを `App.tsx` ヘッダーに追加し、Ctrl+K / Cmd+K でトグル開閉する。

**Tech Stack:** React 18 + TypeScript + Ant Design 5.x + TanStack Query 5.x / FastAPI + SQLAlchemy 2.x + Pydantic v2

---

## 1. 方針

| 項目 | 決定 |
|------|------|
| 検索対象 | Task（title・description）＋ TaskComment（content）|
| 重複排除 | task_id 単位（同一タスクが複数列でヒットしても 1 件表示）|
| snippet 優先順位 | title マッチ → description マッチ → コメントマッチ |
| 結果件数 | 最大 20 件（重複排除後）|
| 最小クエリ長 | 2 文字未満は 422 を返す |
| 結果クリック | `/projects/:project_id` に遷移してモーダルを閉じる |
| キーボード操作 | Escape で閉じる・Enter で先頭結果を選択 |
| トリガー | Ctrl+K（Windows）/ Cmd+K（Mac）、ヘッダーの検索アイコンボタンでも開閉 |
| デバウンス | 入力から 300ms（`useDeferredValue` 使用）|
| 権限 | 全認証済みユーザー（既存の `_scope_condition()` を適用してロール別スコープでフィルタ。private タスクはオーナーのみ検索可能）|

---

## 2. バックエンド

### 2-1. Pydantic モデル

`src/models/task_web.py` の末尾に追加:

```python
# --- Search ---

class SearchResultItem(BaseModel):
    task_id: uuid.UUID
    project_id: uuid.UUID
    project_name: str
    title: str
    snippet: str       # マッチ前後 50 文字
    match_type: Literal["title", "description", "comment"]

    model_config = {"from_attributes": True}


class SearchResponse(BaseModel):
    items: list[SearchResultItem]
    total: int
```

### 2-2. 新規ルーター

`src/api/routers/search.py` を新規作成。`src/api/main.py` に `include_router` 追加。

**エンドポイント:**

```
GET /api/v1/search?q=<keyword>&limit=20
```

**処理フロー:**

1. `q` が 2 文字未満 → 422
2. タスク検索: `Task.title ILIKE` または `Task.description ILIKE`、`Project` を JOIN して `project_name` 取得
3. コメント検索: `TaskComment.content ILIKE`、`Task` → `Project` を JOIN
4. task_id 単位で重複排除（優先度: title > description > comment）
5. snippet 生成: マッチ箇所の前後 50 文字を抽出
6. limit 件に絞って `SearchResponse` として返却

**スニペット生成ロジック:**

```python
def _make_snippet(text: str, keyword: str, context: int = 50) -> str:
    lower = text.lower()
    idx = lower.find(keyword.lower())
    if idx == -1:
        return text[:context * 2]
    start = max(0, idx - context)
    end = min(len(text), idx + len(keyword) + context)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return prefix + text[start:end] + suffix
```

### 2-3. テスト

`tests/unit/test_search_router.py` に 5 件:

| テスト名 | 内容 |
|---------|------|
| `test_search_task_title` | タイトルマッチ → 200・items 1 件 |
| `test_search_comment` | コメントマッチ → 200・match_type="comment" |
| `test_search_deduplication` | タイトル＋コメント両方マッチ → 1 件のみ返却・match_type="title" |
| `test_search_short_query` | q="a"（1 文字）→ 422 |
| `test_search_unauthenticated` | 認証なし → 401 |

---

## 3. フロントエンド

### 3-1. ファイル構成

```
# 新規作成
frontend/src/hooks/useSearch.ts
frontend/src/components/CommandPalette.tsx

# 変更
frontend/src/lib/api.ts              ← SearchResultItem 型・searchAll 関数追加
frontend/src/App.tsx                 ← CommandPalette 追加・ヘッダーに検索アイコン
```

### 3-2. `api.ts` 追加

```typescript
export interface SearchResultItem {
  task_id: string
  project_id: string
  project_name: string
  title: string
  snippet: string
  match_type: 'title' | 'description' | 'comment'
}

export interface SearchResponse {
  items: SearchResultItem[]
  total: number
}

export async function searchAll(q: string, limit = 20): Promise<SearchResponse> {
  const { data } = await api.get<SearchResponse>('/search', { params: { q, limit } })
  return data
}
```

### 3-3. `useSearch.ts`

```typescript
import { useQuery } from '@tanstack/react-query'
import { type SearchResponse, searchAll } from '../lib/api'

export function useSearch(q: string) {
  return useQuery<SearchResponse>({
    queryKey: ['search', q],
    queryFn: () => searchAll(q),
    enabled: q.length >= 2,
    staleTime: 0,
  })
}
```

### 3-4. `CommandPalette.tsx`

**Props:** なし（グローバルコンポーネント）

**主要な状態:**
- `open: boolean` — モーダル表示状態
- `input: string` — 入力値（リアルタイム）
- `deferredQ: string` — `useDeferredValue(input)`（300ms 遅延後に API 発火）

**表示:**
- Ant Design `Modal`（`footer=null`、`width=600`、`style={{ top: 100 }}`）
- `Input.Search`（`autoFocus`、プレースホルダー「タスク・コメントを検索…」）
- `List`（各行: タイトル + `project_name` タグバッジ + `match_type` バッジ）
- 検索中: `Spin` アイコン
- 0 件: 「一致するタスクが見つかりません」
- `q` が 1 文字以下: リスト非表示

**キーボードイベント:**
- `useEffect` で `keydown` を `document` にリスナー登録
- `(e.ctrlKey || e.metaKey) && e.key === 'k'` → `setOpen(true)`、`e.preventDefault()`
- `e.key === 'Escape'` → `setOpen(false)`

### 3-5. `App.tsx` 変更点

```tsx
import CommandPalette from './components/CommandPalette'

// ヘッダー内 WorkloadAlertBadge の左に追加
<Button
  icon={<SearchOutlined />}
  type="text"
  style={{ color: 'white' }}
  onClick={() => openCommandPalette()}
/>
<CommandPalette />
```

`openCommandPalette` は `CommandPalette` 内で `useImperativeHandle` または Zustand の小さなストアで開閉状態を共有する。シンプルさを優先し **Zustand ストア** 方式を採用:

```typescript
// frontend/src/store/useSearchStore.ts
import { create } from 'zustand'

interface SearchStore {
  open: boolean
  setOpen: (open: boolean) => void
}

export const useSearchStore = create<SearchStore>((set) => ({
  open: false,
  setOpen: (open) => set({ open }),
}))
```

---

## 4. 変更しないもの

| 対象 | 理由 |
|------|------|
| 既存の `GET /tasks?q=` | タスク一覧ページのフィルタ検索はそのまま維持 |
| `useSimilarTasks` | タスク作成時の重複チェック用途が異なる |
| DB スキーマ | ILIKE で十分なデータ規模、インデックス追加なし |
