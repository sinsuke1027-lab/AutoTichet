# ローカルタスク入力ウィジェット 設計書

**日付:** 2026-06-08
**対象:** Windows 用デスクトップウィジェット（Python）
**目的:** 既存 AutoTicket FastAPI バックエンドと連携する「摩擦ゼロ」なタスク入力ツール

---

## 1. ゴールと制約

- グローバルホットキー一発でポップアップ → 自然言語入力 → Ollama 解析 → バックエンド起票
- バックエンド: HuggingFace Spaces 上の既存 FastAPI（`POST /api/v1/tasks`）
- 認証: DEV_MODE（`X-Dev-User` ヘッダー）。起動時にユーザーを選択して `config.json` に保存
- AI: ローカル Ollama API（`http://localhost:11434`、モデル `gemma4:e4b`）
- MVP は Python スクリプト配布。フェーズ 2 で PyInstaller .exe 化

---

## 2. ファイル構成

```
widget/
├── main.py                    # エントリーポイント・HotkeyListener・AppController
├── windows/
│   ├── input_window.py        # メイン入力ポップアップ（customtkinter）
│   └── user_select_window.py  # 初回起動時ユーザー選択ダイアログ
├── clients/
│   ├── ollama_client.py       # Ollama API 呼び出し・JSON 抽出
│   └── backend_client.py      # httpx で FastAPI POST / マスタ一覧取得
├── config.py                  # config.json 読み書き
├── config.json                # ユーザー設定（git 除外）
└── requirements.txt
```

---

## 3. 依存ライブラリ

```
customtkinter>=5.2    # モダン UI（tkinter ベース）
keyboard>=0.13        # グローバルホットキー
httpx>=0.27           # HTTP クライアント（同期）
ollama>=0.3           # Ollama API クライアント
pystray>=0.19         # システムトレイ常駐
pillow>=10.0          # pystray の画像処理
```

---

## 4. 設定ファイル（config.json）

```json
{
  "backend_url": "https://xxx.hf.space",
  "selected_user_id": "",
  "hotkey": "<ctrl>+<shift>+<space>",
  "ollama_model": "gemma4:e4b"
}
```

`selected_user_id` が空の場合、起動時に UserSelectWindow を表示してユーザーを選択・保存する。

---

## 5. 起動フロー

```
python main.py
  └─ config.json 読み込み
  └─ selected_user_id が空?
       Yes → UserSelectWindow（バックエンドからユーザー一覧取得 → 選択 → 保存）
       No  → そのまま続行
  └─ バックエンドからユーザー一覧・プロジェクト一覧をキャッシュ
  └─ システムトレイに常駐
  └─ Ctrl+Shift+Space を監視
```

---

## 6. タスク起票フロー

```
[Ctrl+Shift+Space]
  → InputWindow をフォアグラウンドに表示
  → ユーザーが自然言語テキストを入力
  → 「AIで起票する」ボタン押下
  → スピナー表示（UI をブロックしない別スレッドで Ollama 呼び出し）
  → Ollama 解析結果を受信
  → ConfirmPanel をウィンドウ内にインライン展開
      - タイトル（テキスト編集可）
      - 期限（日付ピッカー）
      - 担当者（ユーザー一覧ドロップダウン）
      - プロジェクト（プロジェクト一覧ドロップダウン、空欄可）
      - 優先度（low / medium / high / urgent）
  → 「送信する」押下
  → POST /api/v1/tasks（X-Dev-User: selected_user_id, source_type: "manual"）
  → 成功: ウィンドウを閉じ・トースト通知
  → 失敗: ウィンドウ内にエラー文言表示（データは失わない）
```

---

## 7. UI レイアウト

### InputWindow（初期状態）

```
┌─────────────────────────────────┐
│  🧩 AutoTicket              ×  │
├─────────────────────────────────┤
│  👤 石川 智代 ▼                │  ← 選択済みユーザー（変更可）
│                                 │
│  ┌─────────────────────────┐   │
│  │ 明日までに〇〇の件をまとめる │   │  ← テキスト入力欄（メイン）
│  └─────────────────────────┘   │
│                                 │
│              [AIで起票する →]   │
└─────────────────────────────────┘
```

### ConfirmPanel（インライン展開後）

```
┌─────────────────────────────────┐
│  ✅ 解析結果（編集できます）      │
├─────────────────────────────────┤
│  タイトル: 〇〇の件をまとめる    │
│  期限:     2026-06-09 ▼        │
│  担当者:   石川 智代 ▼          │
│  プロジェクト: （なし） ▼       │
│  優先度:   中 ▼                │
│                                 │
│       [キャンセル] [送信する]    │
└─────────────────────────────────┘
```

---

## 8. Ollama 解析仕様

### システムプロンプト（抜粋）

```
あなたはタスク管理システムへの入力を構造化するアシスタントです。
ユーザーの入力テキストから以下の JSON を出力してください。
今日の日付: {today}

出力形式（JSON のみ、説明不要）:
{
  "title": "タスクタイトル（必須）",
  "due_date": "YYYY-MM-DD または null",
  "assignee_name": "担当者の表示名または null",
  "priority": "low|medium|high|urgent または null"
}
```

### 担当者名の解決

`assignee_name` はユーザー一覧（`display_name`）に対して大文字小文字を区別しない部分一致で解決し、`user_id` に変換する。一致なしの場合は null として送信する。

### Ollama 未起動時のフォールバック

接続タイムアウト（3 秒）の場合は ConfirmPanel を空フォームで表示し、手入力にフォールバックする。エラーメッセージ:「Ollama に接続できませんでした。手動で入力してください。」

---

## 9. バックエンド API 呼び出し

### POST /api/v1/tasks

```
Headers:
  X-Dev-User: <selected_user_id>
  Content-Type: application/json

Body:
  {
    "title": "〇〇の件をまとめる",
    "due_date": "2026-06-09",       // null 可
    "assignee_id": "user-id-xxx",   // null 可
    "project_id": "proj-uuid-xxx",  // null 可
    "priority": "medium",
    "source_type": "manual"
  }
```

### GET /api/v1/users（マスタキャッシュ用）

起動時に一度だけ取得し、メモリにキャッシュする。

### GET /api/v1/projects?scope=all（マスタキャッシュ用）

起動時に一度だけ取得し、メモリにキャッシュする。

---

## 10. エラーハンドリング

| 状況 | 挙動 |
|---|---|
| Ollama 未起動 / タイムアウト | ConfirmPanel を空フォームで表示 |
| タイトル抽出失敗（null） | ConfirmPanel のタイトル欄を空・赤枠でフォーカス |
| バックエンド接続不可（起動時） | アラートダイアログ + 再試行ボタン |
| POST 失敗（4xx / 5xx） | ウィンドウ内にエラー文言表示、入力内容を保持 |
| ユーザー一覧取得失敗 | アラートダイアログ、`config.json` の `backend_url` 確認を促す |

---

## 11. フェーズ 2 以降（MVP 対象外）

| 機能 | 概要 |
|---|---|
| 音声入力 | `sounddevice` で録音 → `faster-whisper` で文字起こし → テキスト欄に流し込み → 以降は通常フロー |
| .exe パッケージング | PyInstaller でシングルバイナリ化、社内配布 |
| Azure AD / MSAL 認証 | DEV_MODE から正式認証へ移行。バックエンド側の変更のみで対応可能 |

---

## 12. インストール・起動手順（MVP）

```bash
cd widget
pip install -r requirements.txt
python main.py
```

初回起動時に `config.json` が生成される。`backend_url` を HuggingFace Spaces の URL に書き換えてから再起動する。
