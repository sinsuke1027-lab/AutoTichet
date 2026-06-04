# 本番デプロイ作業 — 実施記録（2026-06-04）

Vercel + HuggingFace Spaces + Supabase への初回デプロイで発生した問題・対処・教訓をまとめた備忘録。

---

## 1. 作業の流れ（時系列）

| # | 作業 | 結果 |
|---|------|------|
| 1 | Supabase プロジェクト作成・DATABASE_URL 取得 | ✅ 完了 |
| 2 | HuggingFace Space（Docker）作成・環境変数設定 | ✅ 完了 |
| 3 | `git push hf master:main --force` でバックエンドをデプロイ | ✅ 完了 |
| 4 | Vercel フロントエンドデプロイ | ✅ 完了 |
| 5 | タスク作成を試みると **500 エラー** が発生 → 原因調査・修正 | ✅ 修正済み |
| 6 | シードデータ投入 → ローカル DB に誤投入が発覚 → 修正して再投入 | ✅ 修正済み |
| 7 | Playwright で全機能の動作確認 | ✅ 全 PASS |

---

## 2. 発生した問題と対処

### 問題 A: タスク作成・更新・複製で 500 エラー（最重要）

**症状**
```
POST /api/v1/tasks → HTTP 500 "Internal Server Error"（plain-text、JSON ではない）
```

**根本原因**

`db.commit()` を実行すると SQLAlchemy は全属性を expire（無効化）する。
その後 `_task_to_response()` → `_compute_risk_level()` が `task.work_hours` にアクセスすると、
async SQLAlchemy の lazy load が起動しようとするが、async コンテキスト外で失敗し
`MissingGreenlet` 例外を送出する。
この例外が FastAPI のエラーハンドラーで捕捉されず、ASGI が plain-text 500 を返す。

**修正箇所**（`src/api/routers/tasks_crud.py`）

```python
# create_task: db.refresh に "work_hours" を追加
await db.refresh(task, ["tags", "sub_assignees", "subtasks", "work_hours"])

# update_task: selectinload に Task.work_hours を追加
result = await db.execute(
    select(Task)
    .where(Task.id == task_id)
    .options(
        selectinload(Task.tags),
        selectinload(Task.sub_assignees),
        selectinload(Task.subtasks),
        selectinload(Task.work_hours),  # ← 追加
    )
)

# duplicate_task: db.refresh に "work_hours" を追加
await db.refresh(new_task, ["tags", "sub_assignees", "subtasks", "work_hours"])
```

**教訓**
- `_task_to_response()` が参照するリレーションシップはすべて eager load に含める
- 新しいリレーションシップをモデルに追加したときは、同時に全エンドポイントの eager load も確認する
- async SQLAlchemy では `db.commit()` 後に lazy load は原則不可能と考える

**コミット:** `b5bb4e5`

---

### 問題 B: シードスクリプトがローカル DB に投入されていた

**症状**

本番 DB（Supabase）でタスクが 1 件しか見当たらない。
`python scripts/seed_dummy_data.py` 実行時に全タスクが "SKIP (already exists)" になった。

**根本原因**

`scripts/seed_dummy_data.py` の接続先がハードコードされていた。

```python
BASE = "http://localhost:8000/api/v1"  # ← 修正前
```

ローカルで FastAPI が動いていたため、シードデータがローカル SQLite DB に入っていた。
HF Supabase DB には最初の 1 リクエスト（エラーで終わった CREATE）の残骸が 1 件のみ存在。

**修正**

```python
import os
BASE = os.environ.get("SEED_BASE_URL", "http://localhost:8000/api/v1")
```

**本番 DB への投入方法（修正後）**

```powershell
$env:SEED_BASE_URL = "https://shinsukei-autotichet.hf.space/api/v1"
python scripts/seed_dummy_data.py
```

**コミット:** `f736547`

---

### 問題 C: Supabase Direct Connection が ENETUNREACH

**症状**

HuggingFace Spaces から Supabase の Direct Connection（`db.xxxx.supabase.co:5432`）に接続すると
`ENETUNREACH` エラーが発生し、コンテナが起動しない。

**原因**

HuggingFace Spaces のコンテナは Supabase の Direct Connection ポートへの外向きアクセスが制限されている。

**対処**

Supabase の **Session pooler** URL（pgBouncer 経由）を使用する。

```
# NG（Direct）
postgresql+asyncpg://postgres.<id>:<pass>@db.<id>.supabase.co:5432/postgres

# OK（Session pooler）
postgresql+asyncpg://postgres.<id>:<pass>@aws-1-ap-south-1.pooler.supabase.com:5432/postgres
```

HuggingFace Space の Repository secrets `DATABASE_URL` を Session pooler URL に変更して解決。

---

### 問題 D: DevLogin が本番フロントエンドで機能しない

**症状**

`https://auto-tichet.vercel.app/dev-login` にアクセスすると、ユーザー一覧が空のまま。
コンソールには `GET https://auto-tichet.vercel.app/api/v1/dev/users` への fetch エラー。

**原因**

`frontend/src/pages/DevLogin/index.tsx` が API URL を相対パスで fetch していた。
Vercel はフロントエンドのみホストしているため、`/api/v1/...` は Vercel 側に届いてしまう。

**修正**

```typescript
const API_BASE = import.meta.env.VITE_API_URL ?? ''
// ...
const res = await fetch(`${API_BASE}/api/v1/dev/users`)
```

`frontend/.env.production` に以下を設定済み:
```
VITE_API_URL=https://shinsukei-autotichet.hf.space
VITE_DEV_BYPASS_AUTH=true
```

---

### 問題 E: HF Access Token がチャット履歴に残った

**経緯**

`git push https://ShinsukeI:hf_msELkkppHz...@huggingface.co/spaces/...` をコマンドとして
チャットに直接入力したため、トークンが会話ログに残った。

**対処**

HuggingFace の Settings → Access Tokens で当該トークンを **Revoke（削除）→ 再発行**。

**今後の運用**

```powershell
# トークンを環境変数に入れてからコマンドを実行する
$env:HF_TOKEN = "hf_xxxxx"
git push "https://ShinsukeI:$env:HF_TOKEN@huggingface.co/spaces/ShinsukeI/AutoTichet" master:main
```

コマンド実行後はターミナルの環境変数をクリアし、トークンは定期的に再発行する。

---

## 3. Playwright 動作確認結果（全 PASS）

デプロイ後、Playwright MCP で以下を確認した。

| 確認項目 | 結果 | 備考 |
|---------|------|------|
| DevLogin（ユーザー選択カード） | ✅ | 8 ユーザー表示・石川 智代でログイン |
| タスク一覧（32 件表示・高リスクバッジ） | ✅ | シードデータ反映確認 |
| タスク新規作成（500 エラーなし） | ✅ | "動作確認テストタスク（Playwright）"を作成・DB 保存確認 |
| ガントチャート・依存関係表示 | ✅ | 人事業務管理プロジェクトで 3 件の依存関係確認 |
| F-14 負荷アラート（ベルバッジ・赤タグ） | ✅ | 石川 智代 9h > 8h・ベルに「1」バッジ |
| ワークロード工数表示 | ✅ | 9h / 40h（23%）表示 |

---

## 4. デプロイ構成サマリー（確定値）

| レイヤー | サービス | URL | 備考 |
|---------|---------|-----|------|
| フロントエンド | Vercel | https://auto-tichet.vercel.app/ | master push で自動デプロイ |
| バックエンド | HuggingFace Spaces（Docker） | https://shinsukei-autotichet.hf.space | master:main push が必要 |
| DB | Supabase PostgreSQL | Session pooler: `aws-1-ap-south-1.pooler.supabase.com:5432` | Direct connection は使用不可 |

**HuggingFace 環境変数（Repository secrets）**

```
DATABASE_URL   = postgresql+asyncpg://postgres.xxx:<pass>@aws-1-ap-south-1.pooler.supabase.com:5432/postgres
FRONTEND_URL   = https://auto-tichet.vercel.app
SECRET_KEY     = <32文字以上>
GEMINI_API_KEY = <Gemini キー>
LLM_PROVIDER   = gemini
DEV_MODE       = true
```

**Vercel 環境変数（`frontend/.env.production` でも管理）**

```
VITE_API_URL          = https://shinsukei-autotichet.hf.space
VITE_DEV_BYPASS_AUTH  = true
```

---

## 5. DB マイグレーションについて

`entrypoint.sh` の内容:

```bash
#!/bin/bash
set -e
alembic upgrade head
exec uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

HF Spaces への push → コンテナ再ビルド → `entrypoint.sh` が自動実行される。
つまり **新しい Alembic マイグレーションファイルをコミットして HF に push するだけ** で
DB マイグレーションが適用される。手動の `alembic upgrade head` は不要。

初回デプロイ時も同様に自動実行され、全テーブルが正常に作成された（Alembic 0001〜0008 適用済み）。

---

## 6. 今後の注意点

1. **HF Token は使い捨て**: コマンドに直接書いた場合は即座に再発行する
2. **シードデータは環境変数で制御**: `SEED_BASE_URL` 未設定ではローカルに入る
3. **Session pooler を使う**: HF Spaces から Supabase Direct Connection は到達不可
4. **新しいリレーションシップ追加時**: `tasks_crud.py` の全エンドポイントの eager load を確認する
5. **HF スリープ**: 無操作時にスリープする（初回アクセスで 30 秒〜数分の起動遅延あり）
