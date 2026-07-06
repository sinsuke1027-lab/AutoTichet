# Board/Gantt バグ修正 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Board・Gantt の2バグを修正する — (1) プロジェクトフィルターが非admin ユーザーで空になる、(2) Board の同カラム内ドラッグ並び替えが動作しない

**Architecture:**
- Bug 1: `useProjects()` のデフォルト `scope='mine'` はプロジェクトメンバーとして登録されているもののみ返す。Board・Gantt はフィルター選択肢として全プロジェクトを表示する必要があるため `scope='all'` に変更する。
- Bug 2: `handleDragEnd` で `over.id` がカードの上でなくカラムコンテナ上になると、`colTasks.findIndex((t) => t.id === overId)` が -1 を返し並び替えがスキップされる。`overId` がカラムキーと一致する場合はカラム末尾へのドロップとして扱う。

**Tech Stack:** React, @dnd-kit/core, @dnd-kit/sortable, TanStack Query, TypeScript

---

## 変更ファイル一覧

| ファイル | 変更内容 |
|--------|---------|
| `frontend/src/pages/Board/index.tsx:139` | `useProjects()` → `useProjects({ scope: 'all' })` |
| `frontend/src/pages/Board/index.tsx:193` | `overIndex` 計算を修正（`overId` がカラムキーの場合は末尾扱い） |
| `frontend/src/pages/Gantt/index.tsx:70` | `useProjects()` → `useProjects({ scope: 'all' })` |

---

### Task 1: Board プロジェクトフィルター修正（scope: 'all'）

**Files:**
- Modify: `frontend/src/pages/Board/index.tsx:139`

- [ ] **Step 1: 現状を確認する**

```bash
grep -n "useProjects" frontend/src/pages/Board/index.tsx
```

Expected: `139: const { data: projects = [] } = useProjects()`

- [ ] **Step 2: `scope: 'all'` に変更する**

`frontend/src/pages/Board/index.tsx` の 139行目を変更:

```tsx
// Before:
const { data: projects = [] } = useProjects()

// After:
const { data: projects = [] } = useProjects({ scope: 'all' })
```

- [ ] **Step 3: 変更を確認する**

```bash
grep -n "useProjects" frontend/src/pages/Board/index.tsx
```

Expected: `139: const { data: projects = [] } = useProjects({ scope: 'all' })`

- [ ] **Step 4: TypeScript 型エラーがないことを確認する**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep -i board
```

Expected: エラーなし

- [ ] **Step 5: コミットする**

```bash
git add frontend/src/pages/Board/index.tsx
git commit -m "fix: Board プロジェクトフィルターを scope=all に変更"
```

---

### Task 2: Board 同カラム内ドラッグ並び替え修正

**Files:**
- Modify: `frontend/src/pages/Board/index.tsx:189-203`

**根本原因:**
`@dnd-kit` では、カード同士の間に隙間があるとき、`over` がカラムコンテナ（`useDroppable({ id: colKey })`）になる。このとき `over.id` はカラムキー（例: `'in_progress'`）であり、タスク ID ではない。現在のコードはタスク ID として検索するため `overIndex` が -1 となり、並び替えがスキップされる。

**修正方針:** `overId` がカラムキーと一致するとき（カラム空白部分へのドロップ）は、末尾への移動として扱う。

- [ ] **Step 1: 現状の同一カラム並び替えロジックを確認する**

```bash
sed -n '188,205p' frontend/src/pages/Board/index.tsx
```

Expected: 以下のコードが表示される:
```tsx
    if (activeColKey === overColKey) {
      // 同一カラム内の並び替え
      const colTasks = columnTasks[activeColKey] ?? []
      const activeIndex = colTasks.findIndex((t) => t.id === activeId)
      const overIndex = colTasks.findIndex((t) => t.id === overId)
      if (activeIndex !== -1 && overIndex !== -1 && activeIndex !== overIndex) {
        const newOrder = arrayMove(colTasks, activeIndex, overIndex)
        const beforeTask = overIndex > 0 ? newOrder[overIndex - 1] : null
        const afterTask = overIndex < newOrder.length - 1 ? newOrder[overIndex + 1] : null
        reorderTask.mutate({
          taskId: activeId,
          beforeId: beforeTask?.id ?? null,
          afterId: afterTask?.id ?? null,
        })
      }
    }
```

- [ ] **Step 2: `overIndex` の計算を修正する**

`frontend/src/pages/Board/index.tsx` の 189〜203行目を以下に置き換える:

```tsx
    if (activeColKey === overColKey) {
      // 同一カラム内の並び替え
      const colTasks = columnTasks[activeColKey] ?? []
      const activeIndex = colTasks.findIndex((t) => t.id === activeId)
      // over.id がカラムキーのとき（空白部分へのドロップ）は末尾扱い
      const overIndex =
        overId === activeColKey
          ? colTasks.length - 1
          : colTasks.findIndex((t) => t.id === overId)
      if (activeIndex !== -1 && overIndex !== -1 && activeIndex !== overIndex) {
        const newOrder = arrayMove(colTasks, activeIndex, overIndex)
        const beforeTask = overIndex > 0 ? newOrder[overIndex - 1] : null
        const afterTask = overIndex < newOrder.length - 1 ? newOrder[overIndex + 1] : null
        reorderTask.mutate({
          taskId: activeId,
          beforeId: beforeTask?.id ?? null,
          afterId: afterTask?.id ?? null,
        })
      }
    }
```

- [ ] **Step 3: TypeScript 型エラーがないことを確認する**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep -i board
```

Expected: エラーなし

- [ ] **Step 4: コミットする**

```bash
git add frontend/src/pages/Board/index.tsx
git commit -m "fix: Board 同カラム内ドラッグ — over がカラムコンテナのとき末尾に移動"
```

---

### Task 3: Gantt プロジェクトフィルター修正（scope: 'all'）

**Files:**
- Modify: `frontend/src/pages/Gantt/index.tsx:70`

- [ ] **Step 1: 現状を確認する**

```bash
grep -n "useProjects" frontend/src/pages/Gantt/index.tsx
```

Expected: `70: const { data: projects = [] } = useProjects()`

- [ ] **Step 2: `scope: 'all'` に変更する**

`frontend/src/pages/Gantt/index.tsx` の 70行目を変更:

```tsx
// Before:
const { data: projects = [] } = useProjects()

// After:
const { data: projects = [] } = useProjects({ scope: 'all' })
```

- [ ] **Step 3: TypeScript 型エラーがないことを確認する**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep -i gantt
```

Expected: エラーなし

- [ ] **Step 4: コミットする**

```bash
git add frontend/src/pages/Gantt/index.tsx
git commit -m "fix: Gantt プロジェクトフィルターを scope=all に変更"
```

---

## 検証方法

修正後にブラウザで以下を確認:

### Bug 1 検証（Board / Gantt プロジェクトフィルター）

1. `石川 智代`（非admin）でログイン
2. `/board` → プロジェクトドロップダウンを開く
3. 「総務業務管理」「人事業務管理」の2件が表示されること ✅
4. `/gantt` → プロジェクトドロップダウンを開く
5. 同様に2件が表示されること ✅

### Bug 2 検証（Board 同カラム並び替え）

1. `/board` → 任意のカラムに複数タスクがある状態にする
2. 先頭カードをカラム内の空白部分（末尾付近）へドラッグ
3. カードが末尾に移動すること ✅
4. 先頭カードを別のカードの上にドラッグ
5. カードが入れ替わること ✅
