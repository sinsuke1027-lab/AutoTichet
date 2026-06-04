# Security Fixes (VULN-02/04/06) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** セキュリティレビューで確認された3件の脆弱性（未認証 extract エンドポイント・DEV_MODE バイパス警告なし・タスク IDOR）を修正する。

**Architecture:** 各修正は独立しており、既存のコードパターンに沿う形で最小変更にとどめる。VULN-04 は `current_user: CurrentUser` 依存注入を追加するだけ、VULN-02 は lifespan に警告ログを追加するだけ、VULN-06 は 3 エンドポイントに共通の権限チェックブロックを挿入する。

**Tech Stack:** FastAPI, pytest, Python 3.12, SQLAlchemy 2.x, `ROLE_HIERARCHY` from `src.api.auth`

---

## ファイル変更一覧

| ファイル | 変更種別 | 内容 |
|---------|---------|------|
| `src/api/routers/tasks_crud.py` | 修正 | `extract_from_text` に `current_user` 追加・`update_task`/`delete_task`/`duplicate_task` に ownership check 追加 |
| `src/api/main.py` | 修正 | `lifespan()` に DEV_MODE 起動警告を追加 |
| `tests/unit/test_security_fixes.py` | 新規 | 3 件の脆弱性修正を検証するテスト 7 件 |

---

## Task 1: VULN-04 — extract エンドポイントに認証を追加

**Files:**
- Modify: `src/api/routers/tasks_crud.py:337-359`
- Test: `tests/unit/test_security_fixes.py`

### 問題

`POST /api/v1/tasks/extract` は `current_user: CurrentUser` がなく、認証なしでアクセスできる。

### 修正内容

`extract_from_text` のシグネチャに `current_user: CurrentUser` を追加する。

- [ ] **Step 1: 失敗するテストを書く**

`tests/unit/test_security_fixes.py` を新規作成:

```python
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import TokenPayload, get_current_user
from src.api.routers.tasks_crud import router
from src.db.engine import get_db

_member = TokenPayload(sub="user-1", name="Test", email="t@t.com", roles=["member"], tid="tid")
_manager = TokenPayload(sub="mgr-1", name="Mgr", email="m@t.com", roles=["manager"], tid="tid")


def _make_app(user: TokenPayload | None = _member) -> FastAPI:
    """テスト用 FastAPI アプリ（user=None のとき認証なし）"""
    app = FastAPI()
    app.include_router(router)
    if user is not None:
        app.dependency_overrides[get_current_user] = lambda: user
    return app


# --- VULN-04: extract エンドポイント認証 ---

def test_extract_requires_auth() -> None:
    """認証なしで POST /api/v1/tasks/extract → 401"""
    app = _make_app(user=None)
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post("/api/v1/tasks/extract", json={"text": "テスト", "source_type": "email"})
    assert resp.status_code == 401
```

- [ ] **Step 2: テストが失敗することを確認する**

```
cd "C:\Users\shinsuke-imanaka\OneDrive - 株式会社デジタルフォルン\デスクトップ\研修・各スキル\Google Antigravity Apps\AutoTicket"
pytest tests/unit/test_security_fixes.py::test_extract_requires_auth -v
```

期待: FAILED（現在は 422 か 200 が返るため）

- [ ] **Step 3: `extract_from_text` に `current_user: CurrentUser` を追加する**

`src/api/routers/tasks_crud.py` の `extract_from_text` を以下のように修正:

```python
@router.post("/extract", response_model=ExtractResponse)
async def extract_from_text(
    body: ExtractRequest,
    current_user: CurrentUser,
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> ExtractResponse:
```

（関数本体は変更なし）

- [ ] **Step 4: テストが通ることを確認する**

```
pytest tests/unit/test_security_fixes.py::test_extract_requires_auth -v
```

期待: PASSED

- [ ] **Step 5: 既存テストも壊れていないことを確認する**

```
pytest tests/unit/test_tasks_crud_router.py -v
```

期待: 全件 PASSED

- [ ] **Step 6: コミット**

```
git add src/api/routers/tasks_crud.py tests/unit/test_security_fixes.py
git commit -m "fix: VULN-04 extract エンドポイントに認証を追加"
```

---

## Task 2: VULN-02 — DEV_MODE 起動時 CRITICAL 警告を追加

**Files:**
- Modify: `src/api/main.py:204-216`
- Test: `tests/unit/test_security_fixes.py`

### 問題

`DEV_MODE=true` で起動しても警告が一切出ないため、本番環境への誤適用に気づけない。

### 修正内容

`lifespan()` 内で `settings.dev_mode` が `True` のとき `logger.critical()` で警告を出す。

- [ ] **Step 1: 失敗するテストを追加する**

`tests/unit/test_security_fixes.py` に追記:

```python
# --- VULN-02: DEV_MODE 起動警告 ---

def test_dev_mode_logs_critical_warning() -> None:
    """DEV_MODE=true のとき lifespan が CRITICAL ログを出力する"""
    from unittest.mock import patch as _patch
    import logging

    with _patch("src.api.main.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            dev_mode=True,
            polling_interval_seconds=60,
        )
        with _patch("src.api.main.init_db", new_callable=AsyncMock):
            with _patch("src.api.main.scheduler"):
                import asyncio
                from contextlib import asynccontextmanager
                # lifespan を直接テストするため main モジュールをインポート
                from src.api.main import lifespan, app as main_app
                import logging

                with patch("src.api.main.logger") as mock_logger:
                    # lifespan を実行
                    async def run():
                        async with lifespan(main_app):
                            pass
                    asyncio.run(run())

                mock_logger.critical.assert_called_once()
                call_args = mock_logger.critical.call_args[0][0]
                assert "DEV_MODE" in call_args
```

- [ ] **Step 2: テストが失敗することを確認する**

```
pytest tests/unit/test_security_fixes.py::test_dev_mode_logs_critical_warning -v
```

期待: FAILED（`mock_logger.critical.assert_called_once()` で AssertionError）

- [ ] **Step 3: `lifespan()` に DEV_MODE 警告を追加する**

`src/api/main.py` の `lifespan()` を以下のように修正:

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await init_db()
    settings = get_settings()
    if settings.dev_mode:
        logger.critical(
            "DEV_MODE=true が有効です。本番環境では絶対に使用しないでください。"
        )
    scheduler.add_job(
        polling_job,
        "interval",
        seconds=settings.polling_interval_seconds,
        id="polling",
    )
    scheduler.start()
    yield
    scheduler.shutdown()
```

`logger` が `lifespan` のスコープで参照できることを確認する。`main.py` の上部を確認し、なければ追加:

```python
logger = logging.getLogger(__name__)
```

- [ ] **Step 4: テストが通ることを確認する**

```
pytest tests/unit/test_security_fixes.py::test_dev_mode_logs_critical_warning -v
```

期待: PASSED

- [ ] **Step 5: コミット**

```
git add src/api/main.py tests/unit/test_security_fixes.py
git commit -m "fix: VULN-02 DEV_MODE 起動時に CRITICAL 警告を出力"
```

---

## Task 3: VULN-06 — タスク更新・削除・複製に ownership check を追加

**Files:**
- Modify: `src/api/routers/tasks_crud.py:437-523`
- Test: `tests/unit/test_security_fixes.py`

### 問題

`update_task` / `delete_task` / `duplicate_task` はタスクの担当者でなくても、認証さえ通れば任意のタスクを変更・削除できる（IDOR）。

### 修正方針

- `task.assignee_id == current_user.sub` → 操作許可
- `ROLE_HIERARCHY.get(role) >= ROLE_HIERARCHY["manager"]` (レベル 2 以上) → 操作許可
- それ以外 → 403

`ROLE_HIERARCHY` はすでに `tasks_crud.py` に import 済みであることを確認する。

### ownership チェックのヘルパー（インライン）

各エンドポイントで以下のブロックを `task is None` チェックの直後に挿入する（関数は作らず、3か所に書く）:

```python
user_role = max((ROLE_HIERARCHY.get(r, 0) for r in current_user.roles), default=0)
if task.assignee_id != current_user.sub and user_role < ROLE_HIERARCHY.get("manager", 2):
    raise HTTPException(status_code=403, detail="このタスクを操作する権限がありません")
```

- [ ] **Step 1: 失敗するテストを追加する**

`tests/unit/test_security_fixes.py` に追記:

```python
# --- VULN-06: タスク IDOR 修正 ---

def _make_mock_task(assignee_id: str = "owner-1") -> MagicMock:
    task = MagicMock()
    task.id = uuid.uuid4()
    task.assignee_id = assignee_id
    task.tags = []
    task.sub_assignees = []
    task.subtasks = []
    return task


def _make_db_with_task(task: MagicMock) -> AsyncMock:
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = task
    mock_result.scalar_one.return_value = task
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.delete = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.flush = AsyncMock()
    return mock_db


def test_update_task_by_non_owner_member_returns_403() -> None:
    """member が他人のタスクを更新しようとすると 403"""
    task = _make_mock_task(assignee_id="owner-1")
    mock_db = _make_db_with_task(task)

    app = _make_app(user=_member)  # sub="user-1"（owner でない）
    app.dependency_overrides[get_db] = lambda: mock_db
    client = TestClient(app, raise_server_exceptions=False)

    resp = client.put(f"/api/v1/tasks/{task.id}", json={"title": "ハック"})
    assert resp.status_code == 403


def test_delete_task_by_non_owner_member_returns_403() -> None:
    """member が他人のタスクを削除しようとすると 403"""
    task = _make_mock_task(assignee_id="owner-1")
    mock_db = _make_db_with_task(task)

    app = _make_app(user=_member)
    app.dependency_overrides[get_db] = lambda: mock_db
    client = TestClient(app, raise_server_exceptions=False)

    resp = client.delete(f"/api/v1/tasks/{task.id}")
    assert resp.status_code == 403


def test_duplicate_task_by_non_owner_member_returns_403() -> None:
    """member が他人のタスクを複製しようとすると 403"""
    task = _make_mock_task(assignee_id="owner-1")
    mock_db = _make_db_with_task(task)

    app = _make_app(user=_member)
    app.dependency_overrides[get_db] = lambda: mock_db
    client = TestClient(app, raise_server_exceptions=False)

    resp = client.post(f"/api/v1/tasks/{task.id}/duplicate")
    assert resp.status_code == 403


def test_update_task_by_manager_succeeds() -> None:
    """manager ロールなら他人のタスクでも更新できる"""
    task = _make_mock_task(assignee_id="owner-1")

    # update_task は commit 後に再クエリするため、execute を 2 回呼ぶ
    mock_result_1 = MagicMock()
    mock_result_1.scalar_one_or_none.return_value = task
    mock_result_2 = MagicMock()
    mock_result_2.scalar_one.return_value = task
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=[mock_result_1, mock_result_2])
    mock_db.commit = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.delete = AsyncMock()
    mock_db.add = MagicMock()

    app = _make_app(user=_manager)  # sub="mgr-1"
    app.dependency_overrides[get_db] = lambda: mock_db
    client = TestClient(app, raise_server_exceptions=False)

    resp = client.put(f"/api/v1/tasks/{task.id}", json={"title": "管理者が更新"})
    assert resp.status_code == 200
```

- [ ] **Step 2: テストが失敗することを確認する**

```
pytest tests/unit/test_security_fixes.py::test_update_task_by_non_owner_member_returns_403 tests/unit/test_security_fixes.py::test_delete_task_by_non_owner_member_returns_403 tests/unit/test_security_fixes.py::test_duplicate_task_by_non_owner_member_returns_403 -v
```

期待: 全件 FAILED（現在は 200/204 が返るため）

- [ ] **Step 3: `update_task` に ownership check を追加する**

`src/api/routers/tasks_crud.py` の `update_task` で `task is None` チェックの直後（`for field, value in ...` の前）に追加:

```python
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="タスクが見つかりません")
    user_role = max((ROLE_HIERARCHY.get(r, 0) for r in current_user.roles), default=0)
    if task.assignee_id != current_user.sub and user_role < ROLE_HIERARCHY.get("manager", 2):
        raise HTTPException(status_code=403, detail="このタスクを操作する権限がありません")
    for field, value in body.model_dump(exclude_unset=True, exclude={"tags"}).items():
```

- [ ] **Step 4: `delete_task` に ownership check を追加する**

`delete_task` で `task is None` チェックの直後（`await db.delete(task)` の前）に追加:

```python
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="タスクが見つかりません")
    user_role = max((ROLE_HIERARCHY.get(r, 0) for r in current_user.roles), default=0)
    if task.assignee_id != current_user.sub and user_role < ROLE_HIERARCHY.get("manager", 2):
        raise HTTPException(status_code=403, detail="このタスクを操作する権限がありません")
    await db.delete(task)
    await db.commit()
```

- [ ] **Step 5: `duplicate_task` に ownership check を追加する**

`duplicate_task` で `original is None` チェックの直後（`new_task = Task(...)` の前）に追加:

```python
    original = result.scalar_one_or_none()
    if original is None:
        raise HTTPException(status_code=404, detail="タスクが見つかりません")
    user_role = max((ROLE_HIERARCHY.get(r, 0) for r in current_user.roles), default=0)
    if original.assignee_id != current_user.sub and user_role < ROLE_HIERARCHY.get("manager", 2):
        raise HTTPException(status_code=403, detail="このタスクを操作する権限がありません")
    new_task = Task(
```

- [ ] **Step 6: 全テストが通ることを確認する**

```
pytest tests/unit/test_security_fixes.py -v
```

期待: 7 件 PASSED

- [ ] **Step 7: 既存テストが壊れていないことを確認する**

```
pytest tests/unit/ -v
```

期待: 全件 PASSED

- [ ] **Step 8: コミット**

```
git add src/api/routers/tasks_crud.py tests/unit/test_security_fixes.py
git commit -m "fix: VULN-06 update/delete/duplicate タスクに ownership check を追加"
```

---

## 検証手順（全修正後）

```
pytest tests/unit/ -v
```

期待: 全件 PASSED（既存テスト含む）

---

## 注意事項

- `ROLE_HIERARCHY` は `src.api.auth` からすでに import 済みであることを確認する。未 import の場合は `from src.api.auth import ..., ROLE_HIERARCHY` に追加する。
- `duplicate_task` の `assignee_id` は `original.assignee_id`（コピー元のオーナー）でチェックする。
- `update_task` の ownership check は `task` フェッチ直後、`body.model_dump()` ループの前に入れる。
