# ウィジェット拡張ロードマップ 設計書

作成日: 2026-06-09

---

## 概要

`widget/` ディレクトリのデスクトップウィジェットを、単なる「テキスト起票ツール」から**タスク管理の入口となるAIアシスタント**へ段階的に拡張する。

現状（MVP）: テキスト入力 → Ollama 解析 → 起票  
最終形: 複数の入力手段 ＋ 充実した起票内容 ＋ タスク管理との対話

---

## フェーズ構成

| フェーズ | 内容 | 優先度 |
|---------|------|--------|
| 2A | 入力手段の拡張（クリップボード・スクショ） | 最優先 |
| 2B | 起票内容の充実化（description・AIヒアリング） | 高 |
| 2C | 音声入力（faster-whisper） | 中 |
| 3  | 対話AI化（ChatWindow） | 中長期 |

---

## フェーズ 2A：入力手段の拡張

### 目標
クリップボードにコピーしたテキスト、または画面のスクリーンショットをそのまま起票入力に使えるようにする。

### 2A-1：クリップボード入力

**UX フロー**
1. ユーザーがメール・チャット等のテキストをコピー
2. ホットキー（`Ctrl+Shift+Space`）で InputWindow を開く
3. ウィンドウ上部に「📋 クリップボードから入力」ボタンを表示
4. ボタン押下でクリップボードの内容がテキストボックスに自動入力される
5. 以降は既存の「AIで起票する →」フローに合流

**実装方針**
- `tkinter.clipboard_get()` でクリップボード取得（追加ライブラリ不要）
- InputWindow 起動時にクリップボードに内容があればボタンを有効化
- テキストが長い場合（1000文字超）は先頭1000文字に切り詰め、Ollama に渡す

**注意点**
- クリップボード自動監視（バックグラウンド常時チェック）は実装しない。ユーザーが明示的にボタンを押す方式にとどめる（意図しない起票を防ぐため）

### 2A-2：スクリーンショット入力

**UX フロー**
1. InputWindow 上部の「📸 スクリーンショット」ボタンを押す
2. ウィンドウが一時的に非表示になり、0.5秒後に即時キャプチャ
3. `mss` または `Pillow` でスクリーン全体をキャプチャ
4. Ollama Vision モデル（`gemma4:e4b` は画像入力対応）に画像を渡す
5. 画像内のタスク関連情報をJSON構造で抽出
6. ConfirmPanel に結果を表示

**実装方針**
- `Pillow` の `ImageGrab.grab()` でキャプチャ（追加ライブラリ不要）
- 画像は PNG として一時ファイルに保存 → `ollama.chat()` の `images` 引数に渡す
- Vision 用システムプロンプトを別途定義（テキスト用と分離）
- キャプチャ後は一時ファイルを削除

**Ollama Vision プロンプト**
```
画像からタスク管理に関連する情報を抽出してください。
以下の JSON のみを出力してください（説明不要）:
{
  "title": "タスクタイトル（日本語で簡潔に）",
  "due_date": "YYYY-MM-DD または null",
  "assignee_name": "担当者名または null",
  "priority": "low|medium|high|urgent または null",
  "description_hint": "画像から読み取れる補足情報（1〜2文）または null"
}
```

**技術スタック追加**
- `Pillow`（既存 requirements.txt に含まれる）

---

## フェーズ 2B：起票内容の充実化

### 目標
起票時に description（説明文）を含められるようにし、Ollama が簡単なヒアリングを通じて説明文を自動生成する。

### 2B-1：description フィールドの追加

**ConfirmPanel の変更**
- 「優先度」の下に「説明」テキストボックスを追加（高さ 60px・任意入力）
- Ollama の解析結果に `description` が含まれれば自動入力
- ウィンドウ高さを 330px → 420px に拡張

**バックエンド API**
- `POST /api/v1/tasks` の `description` フィールドは既存モデルに存在するため追加不要
- `build_payload()` に `description` 引数を追加するのみ

### 2B-2：AIヒアリング → 説明文自動生成

**UX フロー**
1. ユーザーがテキスト入力後「AIで起票する →」を押す
2. Ollama がまず通常の構造化（title/due_date/assignee/priority）を実施
3. 続けて Ollama が**1問だけ**ヒアリング質問を生成
   - 例：「このタスクの目的や完了条件を一言で教えてください」
4. ユーザーが短く回答、または「スキップ」ボタンで省略（スキップ時は description 空のまま ConfirmPanel へ）
5. 元のテキスト ＋ 回答をもとに Ollama が description を生成
6. ConfirmPanel に description を含めて表示

**時間について**
- ヒアリング問生成は既存の構造化と同じ Ollama 呼び出しに統合（1回の chat() で title+question を同時生成）
- description 生成は別呼び出し（1〜3秒追加）
- 合計で既存比 +3〜5秒程度の見込み
- ヒアリングをスキップした場合は description 生成もスキップ

**Ollama レスポンス形式（拡張）**
```json
{
  "title": "...",
  "due_date": "...",
  "assignee_name": "...",
  "priority": "...",
  "clarifying_question": "このタスクの目的を一言で教えてください"
}
```

---

## フェーズ 2C：音声入力

### 目標
マイクに向かって話すだけでタスクを起票できる。テキスト入力の代替手段として機能する。

### UX フロー
1. InputWindow の「🎤 音声入力」ボタンを押す（またはホットキー変更）
2. 録音中インジケーター表示（赤丸点滅）
3. ボタン再押下 or 無音2秒で録音停止
4. `faster-whisper`（ローカル）で文字起こし
5. 文字起こし結果がテキストボックスに入力される
6. 以降は既存の「AIで起票する →」フローに合流

### 技術スタック
| ライブラリ | 用途 |
|-----------|------|
| `sounddevice` | マイク録音（WAV） |
| `scipy` | WAV ファイル書き出し |
| `faster-whisper` | ローカル音声認識（small モデル推奨） |

### モデル選定
- `small`（244MB）: 日本語精度 ◎、速度 ◎（2〜3秒）
- `medium`（769MB）: 精度 ◎◎、速度 △（5〜8秒）
- 初期は `small` を使用し、精度が不十分なら `medium` に切り替え

### 注意点
- `faster-whisper` の初回ロードは 3〜5秒かかるため、ウィジェット起動時にバックグラウンドでプリロードする
- GPU 非使用時（CPU）でも `small` モデルなら実用速度

---

## フェーズ 3：対話AI化（ChatWindow）

### 目標
ホットキーでチャット画面を開き、タスク管理に関する質問を自然言語で行える。バックエンドAPIとOllamaを組み合わせて回答する。

### UX フロー
1. 専用ホットキー（例：`Ctrl+Shift+A`）または トレイメニュー「AIに聞く」で ChatWindow を起動
2. テキストボックスに質問を入力して送信
3. Ollama がバックエンドAPIのデータを参照しながら回答
4. チャット履歴をウィンドウ内に表示（セッション内保持）

### 対応クエリ例
| 質問例 | 処理 |
|--------|------|
| 「今日のタスクは？」 | `GET /api/v1/tasks?due_date=today` → Ollama で要約 |
| 「石川さんの未完了タスクは？」 | `GET /api/v1/tasks?assignee=...&status=todo` → 一覧返答 |
| 「遅延リスクが高いタスクは？」 | `GET /api/v1/tasks?risk_level=high` → 一覧返答 |
| 「〇〇プロジェクトの進捗は？」 | `GET /api/v1/projects/:id` + タスク集計 → 要約 |
| 自由な質問 | Ollama のみで回答（APIコールなし） |

### アーキテクチャ
```
ChatWindow
    ├── メッセージ履歴（リスト表示）
    ├── 入力ボックス + 送信ボタン
    └── AIAgent（新規クラス）
            ├── intent_classify()   ← API呼び出しが必要か判定
            ├── fetch_context()     ← BackendClient 経由でデータ取得
            └── generate_reply()    ← Ollama でテキスト生成
```

### 技術スタック
- `AIAgent` クラスを `widget/clients/ai_agent.py` として新規作成
- Ollama モデルはウィジェット設定の `ollama_model` を共用
- チャット履歴は `list[dict]` でメモリ保持（ファイル永続化はしない）

---

## ファイル構成の変化

```
widget/
├── clients/
│   ├── ollama_client.py       # 既存・フェーズ2Bで拡張
│   ├── backend_client.py      # 既存・フェーズ3で拡張
│   └── ai_agent.py            # 新規（フェーズ3）
├── windows/
│   ├── input_window.py        # 既存・各フェーズで拡張
│   └── chat_window.py         # 新規（フェーズ3）
├── services/
│   ├── clipboard_reader.py    # 新規（フェーズ2A）
│   ├── screenshot_capture.py  # 新規（フェーズ2A）
│   └── audio_recorder.py      # 新規（フェーズ2C）
├── main.py                    # ホットキー追加（フェーズ3）
├── config.py                  # 設定追加（フェーズ2C・3）
└── requirements.txt           # ライブラリ追加（各フェーズ）
```

---

## 依存ライブラリ追加計画

| フェーズ | 追加ライブラリ | 備考 |
|---------|--------------|------|
| 2A      | なし | Pillow は既存 |
| 2B      | なし | Ollama 多段呼び出しのみ |
| 2C      | `sounddevice`, `scipy`, `faster-whisper` | faster-whisper は別途 `pip install` |
| 3       | なし | 既存ライブラリで実装可能 |

---

## テスト方針

各フェーズとも既存の `widget/tests/` に追加：

| フェーズ | テストファイル | 内容 |
|---------|-------------|------|
| 2A | `test_clipboard_reader.py` | テキスト取得・長文切り詰め |
| 2A | `test_screenshot_capture.py` | キャプチャ・一時ファイル削除 |
| 2B | `test_ollama_client.py`（拡張） | ヒアリング質問生成・description 生成 |
| 2C | `test_audio_recorder.py` | 録音・文字起こしのモックテスト |
| 3  | `test_ai_agent.py` | intent 分類・API呼び出し有無の判定 |

---

## 未決事項

- フェーズ 2A スクショ：Ollama の `gemma4:e4b` が Vision 対応かどうか起動前に確認が必要
- フェーズ 2C：`faster-whisper` の Windows 環境での動作確認（CUDA 不要の CPU モード）
- フェーズ 3：ホットキーの割り当て（`Ctrl+Shift+A` は仮）
