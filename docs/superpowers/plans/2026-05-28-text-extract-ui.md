# テキスト抽出 UI 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 会議文字起こし・メール・チャットテキストを貼り付けてタスク候補を AI 抽出し、確認・編集してから起票できるスプリットパネルモーダルをタスク一覧ページに追加する。

**Architecture:** バックエンドの既存 `POST /api/v1/tasks/extract` を JSON ボディ対応に修正し、フロントエンドに `ExtractModal.tsx`（スプリットパネルモーダル）を新規作成する。左パネルにテキスト入力、右パネルに抽出候補カード一覧を配置し、各カードを編集サブモーダルで修正後に一括起票する。

**Tech Stack:** FastAPI + Pydantic v2、React 18 + TypeScript strict、TanStack Query、Ant Design 5.x

---

## ファイル構成

| ファイル | 変更種別 | 内容 |
|---------|---------|------|
| `src/api/routers/tasks.py` | 修正 | `ExtractRequest` モデル追加・JSON ボディ対応 |
| `frontend/src/lib/api.ts` | 修正 | `ExtractedTask`・`ExtractResult` 型追加・`extractTasksFromText` 関数追加 |
| `frontend/src/hooks/useTasks.ts` | 修正 | `useExtractTasks` フック追加 |
| `frontend/src/pages/Tasks/ExtractModal.tsx` | 新規 | スプリットパネルモーダル本体 |
| `frontend/src/pages/Tasks/index.tsx` | 修正 | 「テキストから作成」ボタン追加・`ExtractModal` 組み込み |

---

### Task 1: バックエンド — JSON ボディ対応 + 型定義

**Files:**
- Modify: `src/api/routers/tasks.py`
- Modify: `frontend/src/lib/api.ts`

現在の `POST /tasks/extract` はクエリパラメータで `text` を受け取っているが、会議文字起こしは数千文字になるため URL 長制限に引っかかる。Pydantic モデルで JSON ボディ受け取りに変更する。

- [ ] **Step 1: `src/api/routers/tasks.py` を読んで現在の実装を確認**

現在の実装（確認済み）:
```python
@router.post("/extract")
async def extract_from_text(
    text: str,
    source_type: str = "email",
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
```

- [ ] **Step 2: `ExtractRequest` モデルと JSON ボディ対応に書き換える**

`src/api/routers/tasks.py` を以下に書き換える:

```python
from contextlib import nullcontext

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.models.config import Settings, get_settings
from src.services.classifier import classify_sensitivity
from src.services.langfuse_client import get_langfuse_client

router = APIRouter(prefix="/tasks")


class ExtractRequest(BaseModel):
    text: str
    source_type: str = "email"


@router.post("/extract")
async def extract_from_text(
    body: ExtractRequest,
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> dict[str, object]:
    langfuse = get_langfuse_client(settings)
    ctx = (
        langfuse.start_as_current_observation(
            name="extract_from_text",
            as_type="chain",
            input={"text": body.text, "source_type": body.source_type},
        )
        if langfuse
        else nullcontext()
    )

    async with ctx:  # type: ignore[union-attr]
        sensitivity = classify_sensitivity(body.text)

        if langfuse:
            langfuse.start_observation(
                name="classify_sensitivity",
                as_type="span",
                input={"text": body.text},
                output=sensitivity.model_dump(),
            )

        if sensitivity.label == "pattern_b":
            result: dict[str, object] = {
                "tasks": [],
                "skipped_reason": "機密データ（Pattern B）",
            }
            if langfuse:
                langfuse.set_current_trace_io(
                    input={"text": body.text, "source_type": body.source_type},
                    output=result,
                )
            return result

        from src.providers.factory import create_llm_provider

        provider = create_llm_provider(settings)
        tasks = await provider.extract_tasks(body.text, body.source_type)
        result = {"tasks": [t.model_dump() for t in tasks]}

        if langfuse:
            langfuse.set_current_trace_io(
                input={"text": body.text, "source_type": body.source_type},
                output=result,
            )

        return result
```

- [ ] **Step 3: ruff チェック**

```
ruff check src/api/routers/tasks.py
```
期待: エラーなし

- [ ] **Step 4: `frontend/src/lib/api.ts` に型を追加**

`getEstimateHours` 関数の後に追記:

```typescript
export interface ExtractedTask {
  is_task: boolean
  title: string
  assignee_name: string | null
  deadline: string | null
  priority: 'high' | 'medium' | 'low'
  category: string
  visibility: 'private' | 'team' | 'all'
  confidence_score: number
  source_type: string
}

export interface ExtractResult {
  tasks: ExtractedTask[]
  skipped_reason?: string
}

export const extractTasksFromText = async (
  text: string,
  sourceType: string,
): Promise<ExtractResult> => {
  const { data } = await api.post<ExtractResult>('/tasks/extract', {
    text,
    source_type: sourceType,
  })
  return data
}
```

- [ ] **Step 5: TypeScript 型チェック**

```
cd frontend && npx tsc --noEmit 2>&1 | head -20
```
期待: エラーなし

- [ ] **Step 6: コミット**

```bash
git add src/api/routers/tasks.py frontend/src/lib/api.ts
git commit -m "feat: extract endpoint を JSON ボディ対応に変更・ExtractedTask 型追加"
```

---

### Task 2: `useExtractTasks` フック追加

**Files:**
- Modify: `frontend/src/hooks/useTasks.ts`

- [ ] **Step 1: `useTasks.ts` の import に `ExtractResult` と `extractTasksFromText` を追加**

現在の import:
```typescript
import api, { type Task, type TaskListResponse, type HourEstimate, getEstimateHours } from '../lib/api'
```
以下に変更:
```typescript
import api, {
  type Task,
  type TaskListResponse,
  type HourEstimate,
  type ExtractResult,
  getEstimateHours,
  extractTasksFromText,
} from '../lib/api'
```

- [ ] **Step 2: ファイル末尾に `useExtractTasks` フックを追加**

```typescript
export function useExtractTasks() {
  return useMutation({
    mutationFn: ({
      text,
      sourceType,
    }: {
      text: string
      sourceType: string
    }): Promise<ExtractResult> => extractTasksFromText(text, sourceType),
  })
}
```

- [ ] **Step 3: TypeScript 型チェック**

```
cd frontend && npx tsc --noEmit 2>&1 | head -20
```
期待: エラーなし

- [ ] **Step 4: コミット**

```bash
git add frontend/src/hooks/useTasks.ts
git commit -m "feat: useExtractTasks フック追加"
```

---

### Task 3: `ExtractModal.tsx` 新規作成

**Files:**
- Create: `frontend/src/pages/Tasks/ExtractModal.tsx`

スプリットパネルモーダル本体。左パネルに入力エリア、右パネルに抽出候補カード一覧を表示する。

- [ ] **Step 1: `frontend/src/pages/Tasks/ExtractModal.tsx` を作成**

```tsx
import { useState } from 'react'
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
  message,
} from 'antd'
import { EditOutlined, RiseOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { useExtractTasks, useCreateTask } from '../../hooks/useTasks'
import { useUsers } from '../../hooks/useUsers'
import { useProjects } from '../../hooks/useProjects'
import type { ExtractedTask } from '../../lib/api'

const { Text, Title } = Typography
const { TextArea } = Input

const SOURCE_OPTIONS = [
  { label: 'メール', value: 'email' },
  { label: '会議文字起こし', value: 'meeting' },
  { label: 'チャット', value: 'chat' },
]

const PRIORITY_OPTIONS = [
  { label: '高', value: 'high' },
  { label: '中', value: 'medium' },
  { label: '低', value: 'low' },
]

interface CandidateTask extends ExtractedTask {
  _id: string
  selected: boolean
  promoted: boolean
  editedTitle: string
  editedAssigneeId: string | null
  editedDueDate: string | null
  editedPriority: 'high' | 'medium' | 'low'
  editedProjectId: string | null
}

interface Props {
  open: boolean
  onClose: () => void
}

export default function ExtractModal({ open, onClose }: Props) {
  const [sourceType, setSourceType] = useState<string>('email')
  const [text, setText] = useState('')
  const [candidates, setCandidates] = useState<CandidateTask[]>([])
  const [patternB, setPatternB] = useState(false)
  const [editTarget, setEditTarget] = useState<CandidateTask | null>(null)
  const [editForm] = Form.useForm()

  const extractTasks = useExtractTasks()
  const createTask = useCreateTask()
  const { data: users = [] } = useUsers()
  const { data: projects = [] } = useProjects()

  const handleClose = () => {
    setText('')
    setCandidates([])
    setPatternB(false)
    setSourceType('email')
    onClose()
  }

  const handleExtract = async () => {
    if (!text.trim()) return
    setPatternB(false)
    const result = await extractTasks.mutateAsync({ text, sourceType })
    if (result.skipped_reason) {
      setPatternB(true)
      setCandidates([])
      return
    }
    setCandidates(
      result.tasks.map((t, i) => ({
        ...t,
        _id: `${i}-${Date.now()}`,
        selected: t.is_task,
        promoted: false,
        editedTitle: t.title,
        editedAssigneeId: null,
        editedDueDate: t.deadline ?? null,
        editedPriority: t.priority,
        editedProjectId: null,
      })),
    )
  }

  const handleForceExtract = async () => {
    setPatternB(false)
    await handleExtract()
  }

  const toggleSelect = (id: string) => {
    setCandidates((prev) =>
      prev.map((c) => (c._id === id ? { ...c, selected: !c.selected } : c)),
    )
  }

  const promoteCandidate = (id: string) => {
    setCandidates((prev) =>
      prev.map((c) =>
        c._id === id ? { ...c, is_task: true, promoted: true, selected: true } : c,
      ),
    )
  }

  const openEdit = (candidate: CandidateTask) => {
    setEditTarget(candidate)
    editForm.setFieldsValue({
      title: candidate.editedTitle,
      assignee_id: candidate.editedAssigneeId,
      due_date: candidate.editedDueDate ? dayjs(candidate.editedDueDate) : null,
      priority: candidate.editedPriority,
      project_id: candidate.editedProjectId,
    })
  }

  const handleEditSave = () => {
    const values = editForm.getFieldsValue()
    if (!editTarget) return
    setCandidates((prev) =>
      prev.map((c) =>
        c._id === editTarget._id
          ? {
              ...c,
              editedTitle: values.title as string,
              editedAssigneeId: (values.assignee_id as string | null) ?? null,
              editedDueDate: values.due_date
                ? (values.due_date as dayjs.Dayjs).format('YYYY-MM-DD')
                : null,
              editedPriority: values.priority as 'high' | 'medium' | 'low',
              editedProjectId: (values.project_id as string | null) ?? null,
            }
          : c,
      ),
    )
    setEditTarget(null)
    editForm.resetFields()
  }

  const selectedCount = candidates.filter((c) => c.selected).length

  const handleCreateAll = async () => {
    const targets = candidates.filter((c) => c.selected)
    let successCount = 0
    for (const c of targets) {
      try {
        await createTask.mutateAsync({
          title: c.editedTitle,
          assignee_id: c.editedAssigneeId ?? undefined,
          due_date: c.editedDueDate ?? undefined,
          priority: c.editedPriority,
          project_id: c.editedProjectId ?? undefined,
          visibility: c.visibility,
        } as Parameters<typeof createTask.mutateAsync>[0])
        successCount++
      } catch {
        void message.error(`「${c.editedTitle}」の起票に失敗しました`)
      }
    }
    if (successCount > 0) {
      void message.success(`${successCount} 件のタスクを起票しました`)
      handleClose()
    }
  }

  const priorityColor: Record<string, string> = {
    high: 'red',
    medium: 'orange',
    low: 'default',
  }

  return (
    <>
      <Modal
        open={open}
        onCancel={handleClose}
        footer={null}
        title="テキストからタスクを抽出"
        width={1000}
        styles={{ body: { padding: 0 } }}
      >
        <Row style={{ minHeight: 480 }}>
          {/* 左パネル */}
          <Col
            span={10}
            style={{ padding: 20, borderRight: '1px solid #f0f0f0', display: 'flex', flexDirection: 'column', gap: 12 }}
          >
            <div>
              <Text strong>入力元</Text>
              <Radio.Group
                options={SOURCE_OPTIONS}
                value={sourceType}
                onChange={(e) => setSourceType(e.target.value as string)}
                optionType="button"
                buttonStyle="solid"
                size="small"
                style={{ display: 'flex', marginTop: 8 }}
              />
            </div>
            <div style={{ flex: 1 }}>
              <Text strong>テキスト</Text>
              <TextArea
                value={text}
                onChange={(e) => setText(e.target.value)}
                rows={14}
                placeholder="会議文字起こし・メール文面・チャットコメントを貼り付けてください"
                style={{ marginTop: 8, resize: 'vertical' }}
              />
            </div>
            {patternB && (
              <Alert
                type="warning"
                message="機密データが検知されました"
                description="このテキストには社外秘キーワードが含まれています。外部 LLM には送信されません。"
                action={
                  <Space direction="vertical">
                    <Button size="small" danger onClick={handleForceExtract}>
                      それでも送信
                    </Button>
                    <Button size="small" onClick={() => setPatternB(false)}>
                      キャンセル
                    </Button>
                  </Space>
                }
              />
            )}
            <Button
              type="primary"
              onClick={handleExtract}
              loading={extractTasks.isPending}
              disabled={!text.trim()}
              block
            >
              抽出する
            </Button>
          </Col>

          {/* 右パネル */}
          <Col span={14} style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 8, overflowY: 'auto', maxHeight: 560 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Title level={5} style={{ margin: 0 }}>
                抽出結果（{candidates.length} 件）
              </Title>
              {selectedCount > 0 && (
                <Popconfirm
                  title={`選択した ${selectedCount} 件を起票しますか？`}
                  onConfirm={handleCreateAll}
                  okText="起票する"
                  cancelText="キャンセル"
                >
                  <Button type="primary" size="small" loading={createTask.isPending}>
                    選択した {selectedCount} 件を起票
                  </Button>
                </Popconfirm>
              )}
            </div>

            {extractTasks.isError && (
              <Alert type="error" message="抽出に失敗しました。再試行してください。" />
            )}
            {candidates.length === 0 && !extractTasks.isPending && !extractTasks.isError && (
              <Text type="secondary" style={{ textAlign: 'center', marginTop: 40, display: 'block' }}>
                左のテキストを入力して「抽出する」を押してください
              </Text>
            )}

            {candidates.map((c) => {
              const isDisabled = !c.is_task && !c.promoted
              return (
                <Card
                  key={c._id}
                  size="small"
                  style={{
                    opacity: isDisabled ? 0.55 : 1,
                    borderColor: isDisabled ? '#d9d9d9' : undefined,
                  }}
                  extra={
                    isDisabled ? (
                      <Button
                        size="small"
                        icon={<RiseOutlined />}
                        onClick={() => promoteCandidate(c._id)}
                      >
                        昇格
                      </Button>
                    ) : (
                      <Button
                        size="small"
                        icon={<EditOutlined />}
                        onClick={() => openEdit(c)}
                      >
                        編集
                      </Button>
                    )
                  }
                  title={
                    <Space>
                      <Checkbox
                        checked={c.selected}
                        disabled={isDisabled}
                        onChange={() => toggleSelect(c._id)}
                      />
                      <Text
                        strong={!isDisabled}
                        type={isDisabled ? 'secondary' : undefined}
                        style={{ maxWidth: 260 }}
                        ellipsis={{ tooltip: c.editedTitle }}
                      >
                        {c.editedTitle}
                      </Text>
                    </Space>
                  }
                >
                  <Space wrap size={4}>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      担当: {c.editedAssigneeId
                        ? (users.find((u) => u.user_id === c.editedAssigneeId)?.display_name ?? '未設定')
                        : '未設定'}
                    </Text>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      期日: {c.editedDueDate ?? '未設定'}
                    </Text>
                    <Tag color={priorityColor[c.editedPriority]} style={{ fontSize: 11 }}>
                      {c.editedPriority === 'high' ? '高' : c.editedPriority === 'medium' ? '中' : '低'}
                    </Tag>
                  </Space>
                  <Progress
                    percent={Math.round(c.confidence_score * 100)}
                    size="small"
                    style={{ marginTop: 4, marginBottom: 0 }}
                    format={(p) => `信頼度 ${p}%`}
                  />
                </Card>
              )
            })}
          </Col>
        </Row>
      </Modal>

      {/* 編集サブモーダル */}
      <Modal
        open={!!editTarget}
        onCancel={() => { setEditTarget(null); editForm.resetFields() }}
        onOk={handleEditSave}
        title="タスクを編集"
        okText="保存"
        cancelText="キャンセル"
        width={480}
      >
        <Form form={editForm} layout="vertical">
          <Form.Item name="title" label="タイトル" rules={[{ required: true, message: 'タイトルを入力してください' }]}>
            <Input />
          </Form.Item>
          <Form.Item
            name="assignee_id"
            label={
              editTarget?.assignee_name
                ? `担当者（🤖 AI提案: ${editTarget.assignee_name}）`
                : '担当者'
            }
          >
            <Select
              allowClear
              showSearch
              placeholder="担当者を選択"
              filterOption={(input, option) =>
                String(option?.label ?? '').toLowerCase().includes(input.toLowerCase())
              }
              defaultOpen={!!editTarget?.assignee_name}
              options={users
                .filter((u) =>
                  editTarget?.assignee_name
                    ? u.display_name.includes(editTarget.assignee_name)
                    : true
                )
                .concat(
                  editTarget?.assignee_name
                    ? users.filter(
                        (u) => !u.display_name.includes(editTarget.assignee_name ?? '')
                      )
                    : [],
                )
                .map((u) => ({ label: u.display_name, value: u.user_id }))}
            />
          </Form.Item>
          <Form.Item name="due_date" label="期日">
            <DatePicker style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="priority" label="優先度">
            <Select options={PRIORITY_OPTIONS} />
          </Form.Item>
          <Form.Item name="project_id" label="プロジェクト">
            <Select
              allowClear
              placeholder="プロジェクトを選択"
              options={projects.map((p) => ({ label: p.name, value: p.id }))}
            />
          </Form.Item>
        </Form>
      </Modal>
    </>
  )
}
```

- [ ] **Step 2: TypeScript 型チェック**

```
cd frontend && npx tsc --noEmit 2>&1 | head -30
```
期待: エラーなし

- [ ] **Step 3: コミット**

```bash
git add frontend/src/pages/Tasks/ExtractModal.tsx
git commit -m "feat: ExtractModal スプリットパネルモーダル追加"
```

---

### Task 4: タスク一覧ページへの統合

**Files:**
- Modify: `frontend/src/pages/Tasks/index.tsx`

- [ ] **Step 1: `index.tsx` の現在のヘッダー周辺を読んで確認**

ファイルを読んで `<Button ... onClick={() => setOpen(true)}>` や `<PlusOutlined />` が使われている行を特定する。

- [ ] **Step 2: `ExtractModal` import を追加**

ファイル先頭の import 群に追加（`useTemplates` import の後など）:

```typescript
import ExtractModal from './ExtractModal'
```

- [ ] **Step 3: `extractModalOpen` state を追加**

`const [open, setOpen] = useState(false)` の直後に追加:

```typescript
const [extractModalOpen, setExtractModalOpen] = useState(false)
```

- [ ] **Step 4: 「テキストから作成」ボタンを追加**

タスク一覧のヘッダー（既存の「新規タスク」ボタンの横）に追加する。現在の「新規タスク」ボタンを探して、その前に挿入する:

```tsx
<Button
  icon={<RobotOutlined />}
  onClick={() => setExtractModalOpen(true)}
>
  テキストから作成
</Button>
```

`RobotOutlined` は既存 import `{ PlusOutlined, RobotOutlined, SearchOutlined }` に含まれているので追加不要。

- [ ] **Step 5: `ExtractModal` をレンダリングに追加**

既存の `<Modal ...>` （タスク作成モーダル）の後に追加:

```tsx
<ExtractModal
  open={extractModalOpen}
  onClose={() => setExtractModalOpen(false)}
/>
```

- [ ] **Step 6: TypeScript 型チェック**

```
cd frontend && npx tsc --noEmit 2>&1 | head -30
```
期待: エラーなし

- [ ] **Step 7: ビルド確認**

```
cd frontend && npm run build 2>&1 | tail -10
```
期待: `✓ built in ...`（エラーなし）

- [ ] **Step 8: コミット**

```bash
git add frontend/src/pages/Tasks/index.tsx
git commit -m "feat: タスク一覧に「テキストから作成」ボタン・ExtractModal 組み込み"
```

---

### Task 5: 最終確認・docs 更新

**Files:**
- Modify: `docs/tasks.md`
- Modify: `docs/progress.md`

- [ ] **Step 1: TypeScript 最終確認**

```
cd frontend && npx tsc --noEmit 2>&1 | head -20
```
期待: エラーなし

- [ ] **Step 2: ruff check 全体**

```
ruff check src/ 2>&1 | head -20
```
期待: 新規エラーなし

- [ ] **Step 3: `docs/tasks.md` に新機能エントリを追加**

`## Web App Phase 2B: Should 機能（残タスク）` セクションに追記:

```markdown
- [x] **F-33 テキスト抽出 UI**: メール・会議文字起こし・チャットからタスク一括抽出（2026-05-28）
```

- [ ] **Step 4: `docs/progress.md` を更新**

「最終更新」セクションの「完了した作業」に追記:

```markdown
  - **[F-33 テキスト抽出 UI]**
    - `POST /tasks/extract` を JSON ボディ対応に修正
    - `ExtractedTask`・`ExtractResult` 型追加（`api.ts`）
    - `useExtractTasks` フック追加（`useTasks.ts`）
    - `ExtractModal.tsx` 新規作成（スプリットパネル・編集サブモーダル・Pattern B 警告）
    - タスク一覧ページに「テキストから作成」ボタン追加
```

- [ ] **Step 5: コミット**

```bash
git add docs/tasks.md docs/progress.md
git commit -m "docs: F-33 テキスト抽出 UI 完了マーク・進捗ログ更新"
```
