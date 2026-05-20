# AutoTicket 起動ガイド

**対象:** 開発・動作確認を行うエンジニア  
**最終更新:** 2026-05-20

---

## 前提：ソフトウェアの確認

以下がインストールされていることを確認してください。

| ソフトウェア | 確認コマンド | 必要バージョン |
|------------|------------|--------------|
| Python | `python --version` | 3.11 以上 |
| Node.js | `node --version` | 18 以上 |
| Docker Desktop | Docker Desktop アプリが起動していること | 最新版 |
| Git | `git --version` | 任意 |

---

## 初回セットアップ（リポジトリ取得後に 1 回だけ実行）

### 1. Python 仮想環境を作成

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1   # PowerShell
```

> **ヒント:** 以降のすべての Python コマンドは仮想環境を有効化した状態で実行してください。

### 2. Python 依存パッケージをインストール

```powershell
pip install -e ".[dev]"
```

### 3. バックエンド環境変数を設定

```powershell
copy .env.example .env
```

`.env` を開いて最低限以下を設定します：

| キー | 説明 | デフォルト値 |
|-----|------|------------|
| `DATABASE_URL` | PostgreSQL 接続文字列 | `postgresql+asyncpg://autoticket:autoticket@localhost:5432/autoticket` |
| `GOOGLE_API_KEY` | Gemini API キー（LLM 処理に必要） | — |
| `DEV_MODE` | 開発用バイパスモード（Azure AD 不要） | `false` |

Azure AD 連携が必要な場合は `AZURE_TENANT_ID` / `AZURE_CLIENT_ID` / `AZURE_CLIENT_SECRET` も設定してください。

### 4. フロントエンド依存パッケージをインストール

```powershell
cd frontend
npm install
copy .env.example .env.local
cd ..
```

`frontend/.env.local` を開いて設定します：

| キー | 説明 |
|-----|------|
| `VITE_AZURE_TENANT_ID` | Azure AD テナント ID |
| `VITE_AZURE_CLIENT_ID` | Azure AD SPA クライアント ID |
| `VITE_DEV_BYPASS_AUTH` | `true` にすると Azure AD なしでログインできる |

> Azure AD の情報がない場合は `VITE_DEV_BYPASS_AUTH=true` を設定して開発用バイパスモードを使用してください（詳細は後述）。

---

## 毎回の起動手順（起動順序を守ってください）

### ステップ 1: Docker コンテナを起動

PostgreSQL と Langfuse を起動します。

```powershell
docker compose -f docker/docker-compose.yml up -d
```

起動確認：

```powershell
docker compose -f docker/docker-compose.yml ps
```

`postgresql` と `langfuse` が `running` になっていれば OK です。

> **初回または DB スキーマ変更後のみ:** Alembic マイグレーションを実行してください。
>
> ```powershell
> alembic upgrade head
> ```

### ステップ 2: バックエンド（FastAPI）を起動

```powershell
# 仮想環境が有効なことを確認（プロンプトに (.venv) が表示される）
uvicorn src.api.main:app --reload --port 8000
```

起動確認:
- `http://localhost:8000/api/v1/health` にアクセスして `{"status":"ok"}` が返ればOK

### ステップ 3: フロントエンド（Vite 開発サーバー）を起動

新しいターミナルを開いて実行：

```powershell
cd frontend
npm run dev
```

起動確認:
- `http://localhost:5173` にアクセスしてログイン画面が表示されれば OK

---

## 開発用バイパスモード（Azure AD なしで複数メンバーがテストする場合）

Azure AD のテナント ID・クライアント ID がない段階でも動作確認できるモードです。

### 設定手順

**バックエンド（`.env`）:**
```
DEV_MODE=true
```

**フロントエンド（`frontend/.env.local`）:**
```
VITE_DEV_BYPASS_AUTH=true
```

### 使い方

1. 上記を設定してサーバーを再起動
2. `http://localhost:5173` にアクセス
3. 「開発用ログイン」フォームが表示される
4. **表示名**・**ユーザーID**・**ロール**（member / leader / manager / admin）を入力してログイン

ログイン後はヘッダーに `[DEV] 名前` と「ログアウト」ボタンが表示されます。

> **注意:** `DEV_MODE=true` は JWT 検証を完全にスキップします。本番環境・外部公開環境では絶対に使用しないでください。

---

## 停止手順

```powershell
# フロントエンド・バックエンドは Ctrl+C で停止

# Docker コンテナを停止（データは保持）
docker compose -f docker/docker-compose.yml stop

# Docker コンテナを削除（データも削除する場合）
docker compose -f docker/docker-compose.yml down -v
```

---

## ポート一覧

| サービス | URL | 備考 |
|---------|-----|------|
| フロントエンド | http://localhost:5173 | Vite 開発サーバー |
| バックエンド API | http://localhost:8000 | FastAPI |
| API ドキュメント | http://localhost:8000/docs | Swagger UI |
| PostgreSQL | localhost:5432 | DB クライアントで接続可 |
| Langfuse | http://localhost:3000 | 監査ログ UI |

---

## よくあるトラブル

### `alembic upgrade head` が失敗する

PostgreSQL が起動していない可能性があります。

```powershell
docker compose -f docker/docker-compose.yml ps
# State が running でなければ:
docker compose -f docker/docker-compose.yml up -d
```

### フロントエンドで `Failed to resolve import` エラーが出る

Vite のキャッシュが壊れている場合があります。

```powershell
cd frontend
Remove-Item -Recurse -Force node_modules\.vite
npm run dev
```

### バックエンドで `401 Unauthorized` が返る

- 通常モード: `VITE_AZURE_TENANT_ID` / `VITE_AZURE_CLIENT_ID` が正しく設定されているか確認
- バイパスモード: `.env` の `DEV_MODE=true` と `frontend/.env.local` の `VITE_DEV_BYPASS_AUTH=true` が両方設定されているか確認し、**サーバーを再起動**してください

### `uvicorn` 起動時に `ModuleNotFoundError`

仮想環境が有効になっていません。

```powershell
.venv\Scripts\Activate.ps1
```

### ログイン後に画面が真っ白になる

ブラウザの開発者ツール（F12）でコンソールエラーを確認してください。多くの場合は API 接続エラー（バックエンドが起動していない）です。
