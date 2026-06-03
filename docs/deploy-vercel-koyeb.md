# デプロイ計画（Vercel + Koyeb + Supabase）

**目的:** 動作テスト・チームデモ用の無料環境構築。将来の Azure 移行も考慮した設計。

**構成:**
| コンポーネント | サービス | 料金 |
|--------------|---------|------|
| フロントエンド（React） | Vercel（無料） | $0 |
| バックエンド（FastAPI） | Koyeb（無料・512MB RAM） | $0 |
| データベース（PostgreSQL） | Supabase（無料・500MB） | $0 |

**注意:** 無料プランはスリープあり（無操作後 30 秒〜2 分の起動遅延）。動作テスト目的として許容。

---

## 作業ステータス

| タスク | 状態 |
|--------|------|
| A-1. フロントエンド API URL 環境変数化 | ✅ 完了（2026-06-03） |
| A-2. vercel.json 作成 | ✅ 完了（2026-06-03） |
| A-3. Dockerfile ルート配置・修正 | ✅ 完了（2026-06-03） |
| A-4. CORS 環境変数化 | ✅ 完了（2026-06-03） |
| A-5. SQLite 方針（テストはそのまま） | ✅ 確認済み |
| A-6. .env.example 更新 | ✅ 完了（2026-06-03） |
| C-1. Supabase セットアップ | ⬜ 未着手 |
| C-2. Koyeb デプロイ | ⬜ 未着手 |
| C-3. Alembic マイグレーション実行 | ⬜ 未着手 |
| C-4. Vercel デプロイ | ⬜ 未着手 |
| C-5. 仕上げ（URI 登録・動作確認） | ⬜ 未着手 |

---

## A. コード修正（デプロイ前に必須）

### A-1. フロントエンド API URL を環境変数化
**ファイル:** `frontend/src/lib/api.ts`

**現状（問題）:**
```typescript
const api = axios.create({
  baseURL: '/api/v1',  // 相対パス → 同一オリジン前提
})
```

**修正後:**
```typescript
const API_BASE = import.meta.env.VITE_API_URL ?? ''

const api = axios.create({
  baseURL: `${API_BASE}/api/v1`,
})
```

ローカル開発時は `frontend/.env.local` に以下を追加（Git 管理外）:
```
VITE_API_URL=
```
（空にすると相対パスになり、`vite.config.ts` の proxy が引き続き機能する）

Vercel の環境変数設定（デプロイ時）:
```
VITE_API_URL=https://<koyeb-app-name>.koyeb.app
```

---

### A-2. `vercel.json` 作成
**ファイル:** `frontend/vercel.json`（新規作成）

```json
{
  "rewrites": [
    { "source": "/(.*)", "destination": "/index.html" }
  ]
}
```

React Router の SPA ルーティングが Vercel で正しく動くために必要。

---

### A-3. Dockerfile をルートに配置・修正
**現状:** `docker/Dockerfile`
**必要:** リポジトリルート `Dockerfile`（Koyeb はルートを参照）

```dockerfile
FROM python:3.13-slim

WORKDIR /app

RUN adduser --disabled-password --gecos "" --uid 1001 autoticket

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini .

# SQLite 処理済みID用（テスト環境では再起動でリセット許容）
RUN mkdir -p data && chown autoticket data

USER autoticket

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Azure 移行時:** この Dockerfile は Azure Container Apps でそのまま利用可能。

---

### A-4. CORS 設定の環境変数化
**ファイル:** `src/api/main.py`

**現状（問題）:**
```python
allow_origins=[_settings.frontend_url, "http://localhost:5173"],
```

**修正後:**
```python
origins = [_settings.frontend_url]
if _settings.frontend_url != "http://localhost:5173":
    origins.append("http://localhost:5173")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    ...
)
```

Koyeb の環境変数に設定:
```
FRONTEND_URL=https://<project>.vercel.app
```

---

### A-5. SQLite（処理済みID管理）の方針
**ファイル:** `src/services/state.py`

Koyeb はエフェメラルファイルシステムのため再起動で `data/processed.db` が消える。
- **動作テスト目的なら:** 現状維持で OK（再起動でリセット許容）✅ 確認済み
- **将来 Azure 移行時:** `ProcessedItem` を PostgreSQL テーブル化し aiosqlite を除去する

---

### A-6. `.env.example` 更新
**ファイル:** `.env.example`

以下を追加・整理:
```env
# ===== Web App 設定 =====
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/dbname
FRONTEND_URL=https://<project>.vercel.app
SECRET_KEY=your-secret-key-here  # JWT 署名用・32文字以上のランダム文字列

# ===== Supabase 接続文字列例 =====
# DATABASE_URL=postgresql+asyncpg://postgres.<project-id>:<password>@aws-0-ap-northeast-1.pooler.supabase.com:5432/postgres
```

---

## B. Azure 将来対応（先行確認）✅ 確認完了（2026-06-03）

| 項目 | 状態 | 備考 |
|------|------|------|
| Dockerfile 非 root ユーザー | ✅ 対応済み | `USER autoticket` |
| ポート 8000 公開 | ✅ 対応済み | `EXPOSE 8000` + `--host 0.0.0.0` |
| ヘルスチェック `/health` | ✅ 対応済み | `HEALTHCHECK` + エンドポイント存在 |
| alembic 同梱 | ✅ 対応済み | `COPY alembic/ alembic/` + `alembic.ini` |
| 全設定を環境変数化 | ✅ 対応済み | config.py のデフォルトはすべて env var で上書き可能 |
| PostgreSQL ドライバー（asyncpg） | ✅ 対応済み | Supabase・Azure DB for PG 両対応 |
| Alembic マイグレーション | ✅ 対応済み | 0001〜0008 |
| localhost ハードコード（B-8） | ✅ 問題なし | config.py はデフォルト値のみ・CORS は将来本番化時に要見直し |
| SQLite 処理済みID | ⚠️ 将来要対応 | Azure 移行時に PostgreSQL テーブル化が必要 |

**Azure 移行時の追加作業（将来）:**
- Azure Container Registry に Docker イメージを push
- Azure Container Apps または App Service にデプロイ
- Azure Database for PostgreSQL に `DATABASE_URL` を切り替え
- Azure Key Vault でシークレット管理（オプション）

---

## C. デプロイ手順（コード修正完了後）

### C-1. Supabase セットアップ
1. https://supabase.com でアカウント作成
2. 新規プロジェクト作成（リージョン: ap-northeast-1 東京推奨）
3. Settings → Database → Connection string（URI）をコピー
4. `postgresql+asyncpg://postgres.<id>:<password>@...` 形式に変換して `DATABASE_URL` として使用

### C-2. Koyeb セットアップ（バックエンド）
1. https://www.koyeb.com でアカウント作成（GitHub 連携）
2. New App → GitHub リポジトリ選択 → Builder: **Dockerfile**
3. Port: `8000`
4. 環境変数を設定:
   ```
   DATABASE_URL=<Supabase の接続文字列>
   FRONTEND_URL=https://<project>.vercel.app  ← Vercel デプロイ後に更新
   SECRET_KEY=<32文字以上のランダム文字列>
   AZURE_TENANT_ID=<テナントID>
   AZURE_CLIENT_ID=<クライアントID>
   AZURE_CLIENT_SECRET=<シークレット>
   GEMINI_API_KEY=<Gemini キー>
   LLM_PROVIDER=gemini
   ```
5. デプロイ後に `https://<app>.koyeb.app/health` で動作確認

### C-3. Alembic マイグレーション実行
Koyeb の Console（ターミナル）または `koyeb exec` コマンドで:
```bash
alembic upgrade head
```

### C-4. Vercel セットアップ（フロントエンド）
1. https://vercel.com でアカウント作成（GitHub 連携）
2. New Project → リポジトリ選択
3. Framework: **Vite**、Root Directory: `frontend`
4. 環境変数:
   ```
   VITE_API_URL=https://<app>.koyeb.app
   VITE_AZURE_CLIENT_ID=<クライアントID>
   VITE_AZURE_TENANT_ID=<テナントID>
   ```
5. デプロイ → URL を取得

### C-5. 仕上げ
1. Koyeb の `FRONTEND_URL` を Vercel の URL に更新（再デプロイ）
2. Azure Entra ID のアプリ登録 → Redirect URI に追加:
   ```
   https://<project>.vercel.app
   https://<project>.vercel.app/auth/callback
   ```
3. ブラウザで動作確認（ログイン → タスク一覧 → Cmd+K 検索）
