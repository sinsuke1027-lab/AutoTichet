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

---

## 社内メンバーへ共有する

ローカル PC で動いているアプリを社内の他のメンバーに使ってもらうには、2 つのステップがあります。

### ステップ 1 — 社内 LAN で即時共有（Entra ID 不要）

**所要時間: 1〜2 時間。Graph API 承認が取れる前でもフィードバック収集に使えます。**

> **注意:** DEV_MODE=true のため認証が無効です。業務データを入れず、あくまで評価・フィードバック用にとどめてください。

#### 1. フロントの接続先 IP を変更

`frontend/.env.local` を以下のように設定します（PC の IP アドレスは `ipconfig` で確認）。

```
VITE_API_BASE_URL=http://192.168.x.x:8000
VITE_DEV_BYPASS_AUTH=true
```

#### 2. バックエンドを全インターフェースでバインドして起動

```powershell
uvicorn src.api.main:app --reload --port 8000 --host 0.0.0.0
```

#### 3. フロントを全インターフェースで起動

```powershell
cd frontend
npm run dev -- --host 0.0.0.0
```

#### 4. Windows ファイアウォールでポートを開放

「Windows Defender ファイアウォール」→「受信の規則」→「新しい規則」で  
ポート **5173**（フロント）と **8000**（バックエンド）を社内 LAN に対して許可します。

#### 5. 同僚に URL を伝える

```
http://あなたのIPアドレス:5173
```

---

### ステップ 2 — 社内サーバーへ本番デプロイ（Entra ID 必要）

**Graph API 承認取得後に実施します。詳細は `docs/deployment-roadmap.md` の D-Ph0 を参照。**

#### 2-1. Entra ID アプリ登録（IT 管理者に依頼）

`docs/graph-api-setup.md` を IT 管理者に渡して以下の情報をもらいます：

| 変数 | 説明 |
|-----|------|
| `AZURE_TENANT_ID` | テナント ID |
| `AZURE_CLIENT_ID` | バックエンド用アプリ登録のクライアント ID |
| `VITE_AZURE_TENANT_ID` | フロントエンド用（SPA 登録、同じ値で可） |
| `VITE_AZURE_CLIENT_ID` | フロントエンド用 SPA のクライアント ID |

IT 管理者には Entra ID のアプリ登録で「リダイレクト URI」に  
`http://サーバーのアドレス` を追加してもらってください。

#### 2-2. フロントエンドを本番ビルド

```powershell
cd frontend

# frontend/.env.local を本番用に設定
# VITE_AZURE_TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
# VITE_AZURE_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
# VITE_API_BASE_URL=http://サーバーアドレス:8000
# VITE_DEV_BYPASS_AUTH=false   ← 必ず false

npm run build   # frontend/dist/ に静的ファイルが生成される
```

#### 2-3. FastAPI からフロントエンドを配信する（1 ポート完結）

`src/api/main.py` の末尾に以下を追加すると、バックエンドとフロントを同じ URL で提供できます：

```python
import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

if os.path.exists("frontend/dist"):
    app.mount("/assets", StaticFiles(directory="frontend/dist/assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str) -> FileResponse:
        return FileResponse("frontend/dist/index.html")
```

これで `http://サーバー:8000` にアクセスするだけでフロントもバックエンドも使えます。

#### 2-4. 本番用 .env を設定

```env
DEV_MODE=false                    # 必ず false
AZURE_TENANT_ID=本番テナントID
AZURE_CLIENT_ID=本番クライアントID
AZURE_CLIENT_SECRET=本番シークレット
DATABASE_URL=postgresql+asyncpg://user:pass@サーバーアドレス:5432/autoticket
GEMINI_API_KEY=本番APIキー
POSTGRES_PASSWORD=強力なパスワードに変更
# Langfuse も本番用シークレットに変更:
# NEXTAUTH_SECRET, SALT を docker-compose.yml で設定
```

#### 2-5. Docker Compose で起動

```powershell
# 本番サーバー上で実行
docker compose -f docker/docker-compose.yml up -d

# 初回のみ: DB マイグレーション
alembic upgrade head
```

起動確認:

```
http://サーバーアドレス:8000/api/v1/health → {"status":"ok"}
http://サーバーアドレス:8000               → ログイン画面
```

---

### ステップ別の判断フロー

```
今すぐ試してもらいたい（評価・フィードバック）
    └── ステップ 1: 社内 LAN + DEV_MODE（1〜2 時間）

Graph API 承認が取れた
    └── ステップ 2: Docker デプロイ + Entra ID（D-Ph0）

Azure サブスクリプションが使える
    └── Azure App Service（コンテナイメージを ACR に push）
```

> **関連ドキュメント:** `docs/deployment-roadmap.md` — 誰に・いつ・どのフェーズで展開するかの戦略ロードマップ
