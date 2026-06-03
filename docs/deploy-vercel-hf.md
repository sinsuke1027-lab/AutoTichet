# デプロイ計画（Vercel + HuggingFace Spaces + Supabase）

**目的:** 動作テスト・チームデモ用の無料環境構築。将来の Azure 移行も考慮した設計。

**構成:**
| コンポーネント | サービス | 料金 |
|--------------|---------|------|
| フロントエンド（React） | Vercel（無料） | $0 |
| バックエンド（FastAPI） | HuggingFace Spaces（Docker・無料） | $0 |
| データベース（PostgreSQL） | Supabase（無料・500MB） | $0 |

**注意:**
- HuggingFace Spaces は無操作後しばらくするとスリープ（起動遅延あり）
- リポジトリを **public** にする必要あり（private は有料プラン）
- 動作テスト目的として許容

---

## 本番 URL（2026-06-04 時点）

| レイヤー | URL |
|---------|-----|
| フロントエンド（Vercel） | https://auto-tichet.vercel.app/ |
| バックエンド（HuggingFace Spaces） | https://shinsukei-autotichet.hf.space |
| DB（Supabase） | Session pooler: `aws-1-ap-south-1.pooler.supabase.com:5432` |

---

## 日常的な変更・デプロイ手順

### 変更の種類とデプロイコマンド

| 変更の種類 | フロントエンド push | バックエンド push |
|-----------|-----------------|----------------|
| フロント only（`frontend/` 以下） | 必要 | 不要 |
| バックエンド only（`src/` 以下） | 不要 | 必要 |
| 両方変更 | 必要 | 必要 |
| DB マイグレーション（`alembic/`） | 不要 | 必要（再起動で自動実行） |

### フロントエンドのデプロイ（Vercel）

```powershell
git push origin master
```

Vercel は GitHub の master ブランチに push されると **自動でビルド・デプロイ** する。  
数分後に https://auto-tichet.vercel.app/ に反映される。

### バックエンドのデプロイ（HuggingFace Spaces）

```powershell
# 1. まず GitHub に push
git push origin master

# 2. 次に HuggingFace Spaces に push
#    ※ HF_TOKEN は HuggingFace Settings → Access Tokens で発行したトークン
git push https://ShinsukeI:HF_TOKEN@huggingface.co/spaces/ShinsukeI/AutoTichet master:main
```

> **セキュリティ注意:** HF_TOKEN をコマンドに直打ちするとチャット履歴に残る。  
> 使用後は HuggingFace の Settings → Access Tokens で **トークンを再発行**（Regenerate）すること。  
> 代替案: `$env:HF_TOKEN = "..."` と環境変数に入れてからコマンドを実行する。

HuggingFace は push を検知してコンテナをリビルドする。`entrypoint.sh` が：
1. `alembic upgrade head`（DB マイグレーション）を実行
2. `uvicorn` を起動

するため、マイグレーションファイルを追加した場合も手動実行は不要。

---

### DB マイグレーション手順

```powershell
# 1. Alembic マイグレーションファイルを生成
cd C:\...\AutoTicket  # プロジェクトルート
alembic revision --autogenerate -m "変更内容の説明"

# 2. 生成されたファイルを確認してコミット
git add alembic/versions/
git commit -m "db: add migration for ..."

# 3. GitHub と HF の両方に push
git push origin master
git push https://ShinsukeI:HF_TOKEN@huggingface.co/spaces/ShinsukeI/AutoTichet master:main
```

HF Spaces が再起動すると `entrypoint.sh` が自動で `alembic upgrade head` を実行する。

---

### 新しいメンバーの追加

1. ブラウザで https://auto-tichet.vercel.app/ にアクセス
2. DevLogin ページから `田中 一郎`（管理者権限あり）でログイン
3. 右上アイコン → **管理設定** → **ユーザー管理**
4. 「ユーザー追加」でメンバーのメールアドレス・名前・ロールを入力
5. 追加後、そのメールアドレスで DevLogin 可能になる

> **現状の認証方式:** `VITE_DEV_BYPASS_AUTH=true` + `DEV_MODE=true` による開発者ログイン（Azure AD なし）。  
> チームメンバーはどのネットワーク環境からでも https://auto-tichet.vercel.app/ にアクセスできる。  
> ただし、DBに登録されているユーザーのみログイン可能（上記手順で事前登録が必要）。

---

### シードデータ投入（本番 DB）

```powershell
# 本番 DB に対して実行する場合は SEED_BASE_URL を設定
$env:SEED_BASE_URL = "https://shinsukei-autotichet.hf.space/api/v1"
python scripts/seed_dummy_data.py

# ローカル DB に投入する場合（デフォルト）は設定不要
python scripts/seed_dummy_data.py
```

スクリプトは既存タスクを SKIP するため、重複投入しても安全。

---

## 作業ステータス

| タスク | 状態 |
|--------|------|
| A-1. フロントエンド API URL 環境変数化 | ✅ 完了（2026-06-03） |
| A-2. vercel.json 作成 | ✅ 完了（2026-06-03） |
| A-3. Dockerfile ルート配置・修正（HF対応） | ✅ 完了（2026-06-03） |
| A-4. CORS 環境変数化 | ✅ 完了（2026-06-03） |
| A-5. SQLite 方針（テストはそのまま） | ✅ 確認済み |
| A-6. .env.example 更新 | ✅ 完了（2026-06-03） |
| A-7. entrypoint.sh 作成（alembic + uvicorn） | ✅ 完了（2026-06-03） |
| A-8. README.md HF Spaces フロントマター追加 | ✅ 完了（2026-06-03） |
| C-1. Supabase セットアップ | ✅ 完了（2026-06-04） |
| C-2. HuggingFace Space 作成・push | ✅ 完了（2026-06-04） |
| C-3. Alembic マイグレーション（entrypoint.sh で自動実行） | ✅ 完了（2026-06-04・自動） |
| C-4. Vercel デプロイ | ✅ 完了（2026-06-04） |
| C-5. 仕上げ（URI 登録・動作確認） | ✅ 完了（2026-06-04） |

---

## A. コード修正（完了済み）

### A-1. フロントエンド API URL を環境変数化
**ファイル:** `frontend/src/lib/api.ts`

```typescript
const API_BASE = import.meta.env.VITE_API_URL ?? ''

const api = axios.create({
  baseURL: `${API_BASE}/api/v1`,
})
```

ローカル開発時は `frontend/.env.local` に以下を追加:
```
VITE_API_URL=
```
（空にすると相対パスになり、`vite.config.ts` の proxy が機能する）

Vercel の環境変数設定（デプロイ時）:
```
VITE_API_URL=https://<hf-space-name>.hf.space
```

---

### A-2. `vercel.json` 作成
**ファイル:** `frontend/vercel.json`

```json
{
  "rewrites": [
    { "source": "/(.*)", "destination": "/index.html" }
  ]
}
```

---

### A-3. Dockerfile（HuggingFace Spaces 対応）
**ファイル:** `Dockerfile`（リポジトリルート）

HuggingFace Spaces は uid 1000 でコンテナを実行するため、同一 uid でユーザーを作成する。

```dockerfile
FROM python:3.13-slim

RUN useradd -m -u 1000 autoticket

ENV HOME=/home/autoticket \
    PATH=/home/autoticket/.local/bin:$PATH

WORKDIR $HOME/app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=autoticket src/ src/
COPY --chown=autoticket alembic/ alembic/
COPY --chown=autoticket alembic.ini .
COPY --chown=autoticket entrypoint.sh .

RUN mkdir -p data && chown autoticket data
RUN chmod +x entrypoint.sh

USER autoticket

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["./entrypoint.sh"]
```

---

### A-4. CORS 設定の環境変数化
**ファイル:** `src/api/main.py`

```python
_cors_origins = [_settings.frontend_url]
if _settings.frontend_url != "http://localhost:5173":
    _cors_origins.append("http://localhost:5173")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    ...
)
```

HuggingFace Spaces の環境変数に設定:
```
FRONTEND_URL=https://<project>.vercel.app
```

---

### A-5. SQLite（処理済みID管理）の方針

HuggingFace Spaces はエフェメラルファイルシステムのため再起動で `data/processed.db` が消える。
- **動作テスト目的なら:** 現状維持で OK（再起動でリセット許容）✅ 確認済み
- **将来 Azure 移行時:** `ProcessedItem` を PostgreSQL テーブル化し aiosqlite を除去する

---

### A-6. `.env.example` 更新

追加済み:
```env
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/dbname
FRONTEND_URL=https://<project>.vercel.app
SECRET_KEY=your-secret-key-here
```

---

### A-7. `entrypoint.sh` 作成
**ファイル:** `entrypoint.sh`（リポジトリルート）

```bash
#!/bin/bash
set -e
alembic upgrade head
exec uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

起動時に自動で Alembic マイグレーションを実行してから uvicorn を起動する。

---

### A-8. README.md HuggingFace Spaces フロントマター

`README.md` の先頭に以下を追加済み:
```yaml
---
title: AutoTicket Backend
emoji: 🎫
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 8000
pinned: false
---
```

---

## B. Azure 将来対応（確認完了）

| 項目 | 状態 | 備考 |
|------|------|------|
| Dockerfile 非 root ユーザー | ✅ 対応済み | `USER autoticket`（uid 1000） |
| ポート 8000 公開 | ✅ 対応済み | `EXPOSE 8000` + `--host 0.0.0.0` |
| ヘルスチェック `/health` | ✅ 対応済み | `HEALTHCHECK` + エンドポイント存在 |
| alembic 同梱 | ✅ 対応済み | `entrypoint.sh` で自動実行 |
| 全設定を環境変数化 | ✅ 対応済み | config.py のデフォルトは env var で上書き可能 |
| PostgreSQL ドライバー（asyncpg） | ✅ 対応済み | Supabase・Azure DB for PG 両対応 |
| SQLite 処理済みID | ⚠️ 将来要対応 | Azure 移行時に PostgreSQL テーブル化が必要 |

---

## C. デプロイ手順（コード修正完了後）

### C-1. Supabase セットアップ
1. https://supabase.com でアカウント作成
2. 新規プロジェクト作成（リージョン: ap-northeast-1 東京推奨）
3. Settings → Database → Connection string（URI）をコピー
4. `postgresql+asyncpg://postgres.<id>:<password>@...` 形式に変換して `DATABASE_URL` として使用

### C-2. HuggingFace Space 作成・push
1. https://huggingface.co でアカウント作成
2. New Space → Docker SDK を選択
3. Space 名を決定（例: `autoticket-backend`）
4. リポジトリを public に設定
5. HuggingFace リモートを追加:
   ```bash
   git remote add hf https://huggingface.co/spaces/<username>/autoticket-backend
   git push hf master
   ```
6. Space の Settings → Repository secrets に環境変数を設定:
   ```
   DATABASE_URL=<Supabase の接続文字列>
   FRONTEND_URL=https://<project>.vercel.app  ← Vercel デプロイ後に更新
   SECRET_KEY=<32文字以上のランダム文字列>
   AZURE_TENANT_ID=<テナントID>
   AZURE_CLIENT_ID=<クライアントID>
   AZURE_CLIENT_SECRET=<シークレット>
   GEMINI_API_KEY=<Gemini キー>
   LLM_PROVIDER=gemini
   DEV_MODE=true  ← Azure AD なしのテスト時のみ
   ```
7. push 後、Space がビルドされ自動起動（`entrypoint.sh` で alembic も実行される）
8. `https://<username>-autoticket-backend.hf.space/health` で動作確認

**注意:** C-3（Alembic マイグレーション）は `entrypoint.sh` により起動時に自動実行されるため、手動実行不要。

### C-4. Vercel セットアップ（フロントエンド）
1. https://vercel.com でアカウント作成（GitHub 連携）
2. New Project → リポジトリ選択
3. Framework: **Vite**、Root Directory: `frontend`
4. 環境変数:
   ```
   VITE_API_URL=https://<username>-autoticket-backend.hf.space
   VITE_AZURE_CLIENT_ID=<クライアントID>
   VITE_AZURE_TENANT_ID=<テナントID>
   VITE_DEV_BYPASS_AUTH=true  ← Azure AD なしのテスト時のみ
   ```
5. デプロイ → URL を取得

### C-5. 仕上げ
1. HuggingFace Space の `FRONTEND_URL` を Vercel の URL に更新（Repository secrets 更新 → 再起動）
2. Azure Entra ID のアプリ登録 → Redirect URI に追加:
   ```
   https://<project>.vercel.app
   https://<project>.vercel.app/auth/callback
   ```
3. ブラウザで動作確認（ログイン → タスク一覧 → Cmd+K 検索）
