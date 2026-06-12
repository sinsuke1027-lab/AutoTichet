# ウィジェット チーム配布対応 設計書

**日付**: 2026-06-12
**対象**: `widget/` ディレクトリ
**目的**: `.exe` でチームへ配布し、日常業務で使い続けてもらえるレベルのUXを実現する

---

## 背景・課題

ウィジェット Phase 3 で機能実装は完了した。次のステップはチームへの配布だが、以下の2点が障壁となっている：

- **エラー時に何も言わず止まる**: バックエンドが落ちていると原因不明のまま詰まる
- **見た目が素朴すぎる**: 業務ツールとして信頼感・完成度が足りない

配布方法は「共有フォルダに `.exe` を置いてダブルクリック」を前提とする。

---

## スコープ

| 機能 | 優先度 |
|------|-------|
| 初回起動ウィザード | 高 |
| バックエンド切断時のエラーダイアログ | 高 |
| トレイアイコンで接続状態を表示 | 高 |
| オフラインドラフトキュー | 中 |
| UIテーマ統一 | 中 |
| Windowsログイン時の自動起動オプション | 中 |

---

## 全体アーキテクチャ

### 新規ファイル

| ファイル | 役割 |
|---------|------|
| `widget/windows/first_run_wizard.py` | 3ステップ初回セットアップウィザード |
| `widget/services/connection_monitor.py` | バックエンド接続状態の定期チェック |
| `widget/services/draft_queue.py` | オフライン時のドラフト保存・自動再送 |
| `widget/services/autostart.py` | Windowsレジストリへの自動起動登録/解除 |
| `widget/ui_constants.py` | 色・フォント・余白の定数集 |

### 変更ファイル

| ファイル | 変更内容 |
|---------|---------|
| `widget/main.py` | 初回起動チェック・ConnectionMonitor統合・トレイアイコン色変更 |
| `widget/windows/settings_window.py` | 自動起動トグル追加・UIテーマ適用 |
| `widget/windows/input_window.py` | オフライン時ドラフト保存切り替え・UIテーマ適用 |
| `widget/config.py` | `first_run_complete: bool` フラグ追加 |

### 新規データファイル

- `widget/data/drafts.db` — ドラフトキュー用SQLite（`history.db` と分離）

### コンポーネント間の関係

```
main.py
  ├─ 起動時 → first_run_complete が False なら FirstRunWizard を表示
  ├─ ConnectionMonitor を起動（バックグラウンドスレッド）
  │     └─ 状態変化時にトレイアイコン色を更新（緑/黄/赤）
  └─ InputWindow
        └─ 送信時にバックエンド切断中 → DraftQueue に保存
              └─ ConnectionMonitor が復旧を検知 → 自動再送
```

---

## 機能詳細

### 1. 初回起動ウィザード（FirstRunWizard）

#### 起動条件
`config.json` の `first_run_complete: false`（または未存在）の場合のみ、`main.py` 起動時に `UserSelectWindow` の代わりに表示する。

#### Step 1 — バックエンドURL設定
- デフォルト値は `config.json` の `backend_url`
- 「接続テスト」ボタンで `GET /health` を実行
  - 成功: 緑✓ 表示、「次へ」ボタンを有効化
  - 失敗: 赤✗ ＋ エラーメッセージ表示
- 「スキップ」で接続テストを省略して次へ進める

#### Step 2 — ユーザー選択
- 既存の `BackendClient.get_users_dev()` でユーザー一覧を取得
- バックエンド未接続の場合は「後で設定する」ボタンで Step 3 へスキップ可能

#### Step 3 — 完了
- 設定サマリー（URL・ユーザー名）を表示
- 自動起動トグルスイッチを配置（その場で設定可能）
- 「起動する」で `config.first_run_complete = true` を保存し通常起動フローへ

#### エッジケース

| ケース | 挙動 |
|-------|------|
| ×ボタンで閉じる | アプリ終了（未完了のまま常駐させない） |
| 接続失敗のままスキップ | 起動後トレイアイコンが赤になり、クリックでエラーダイアログ |
| 2回目以降の起動 | ウィザードをスキップして通常起動 |

---

### 2. 接続状態管理（ConnectionMonitor）

#### 状態定義

| 状態 | 判定条件 | チェック間隔 | トレイアイコン |
|------|---------|------------|-------------|
| `connected` | `/health` 200、応答 ≤2秒 | 30秒 | 🟢 緑丸 |
| `degraded` | `/health` 200、応答 >2秒 | 10秒 | 🟡 黄丸 |
| `disconnected` | タイムアウト or 非200 | 10秒 | 🔴 赤丸 |

状態が変化したときのみ `on_state_change` コールバックを呼び出す。

#### トレイツールチップ

| 状態 | テキスト |
|------|---------|
| `connected` | AutoTicket — 接続中 |
| `degraded` | AutoTicket — 応答遅延 |
| `disconnected` | AutoTicket — バックエンド未接続 |

#### エラーダイアログ

バックエンド切断中に送信ボタンを押したとき表示：

```
⚠️  バックエンドに接続できません

このまま送信すると下書きとして保存され、
復旧後に自動送信されます。

[設定を開く]  [下書き保存]  [閉じる]
```

- **設定を開く**: `SettingsWindow` を表示
- **下書き保存**: `DraftQueue` に保存してフォームをリセット
- **閉じる**: 何もしない（入力内容は保持）

#### main.py の変更

`ConnectionMonitor` と `DraftQueue` は `main.py` で生成し、`InputWindow` に依存注入する。

```python
self.connection_monitor = ConnectionMonitor(
    url=cfg.backend_url,
    on_state_change=self._on_connection_state_changed,
)
self.connection_monitor.start()
self.draft_queue = DraftQueue()

# InputWindow 生成時に渡す
input_win = InputWindow(
    ...,
    connection_monitor=self.connection_monitor,
    draft_queue=self.draft_queue,
)

def _on_connection_state_changed(self, state: ConnectionState) -> None:
    icon_img = _make_tray_image(state)
    self.tray_icon.icon = icon_img
```

---

### 3. オフラインドラフトキュー（DraftQueue）

#### データモデル（`widget/data/drafts.db`）

```sql
CREATE TABLE drafts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    payload     TEXT NOT NULL,      -- JSON文字列（create_task のリクエストボディ）
    created_at  TEXT NOT NULL,      -- ISO 8601
    retry_count INTEGER DEFAULT 0,
    last_error  TEXT                -- 最後のエラーメッセージ
);
```

#### 公開インターフェース

```python
class DraftQueue:
    def add(self, payload: dict) -> int
    def get_pending(self) -> list[DraftEntry]
    def remove(self, draft_id: int) -> None
    def increment_retry(self, draft_id: int, error: str) -> None
```

#### 自動再送ロジック

`ConnectionMonitor` が `disconnected → connected` に遷移したとき：

1. `DraftQueue.get_pending()` で未送信ドラフトを取得
2. 1件ずつ `BackendClient.create_task()` を試みる
3. 成功 → `DraftQueue.remove()` ＋ `notify_success()` トースト
4. 失敗 → `increment_retry()`、`retry_count ≥ 3` になったドラフトはキューに残したまま「送信に失敗しました。下書き一覧から手動で再送してください」トーストを表示する

#### トレイメニュー

ドラフトが1件以上あるとき追加表示：

```
📋 下書き (2件)  ← クリックで一覧ウィンドウを表示
```

一覧から「今すぐ送信」「削除」が可能。

---

### 4. UIテーマ統一（ui_constants.py）

#### `widget/ui_constants.py`

```python
# カラーパレット
PRIMARY   = "#2563EB"   # ボタン・アクセント（青）
SUCCESS   = "#16A34A"   # 成功メッセージ（緑）
WARNING   = "#D97706"   # 警告（黄）
DANGER    = "#DC2626"   # エラー・削除（赤）

# フォントサイズ階層
FONT_H1   = ("Meiryo UI", 16, "bold")
FONT_H2   = ("Meiryo UI", 13, "bold")
FONT_BODY = ("Meiryo UI", 12)
FONT_SMALL= ("Meiryo UI", 10)

# 余白グリッド（8px基準）
PAD_S  = 8
PAD_M  = 16
PAD_L  = 24

# ウィンドウサイズ
WIN_INPUT    = (480, 520)
WIN_WIZARD   = (480, 340)
WIN_SETTINGS = (400, 480)
WIN_HISTORY  = (420, 380)
WIN_TODO     = (400, 480)
```

#### ボタンスタイル統一

| 種類 | 用途 | 見た目 |
|------|------|--------|
| Primary | 送信・次へ・起動 | 青塗りつぶし・白文字 |
| Secondary | 戻る・キャンセル | グレー枠・通常文字 |
| Danger | 削除・解除 | 赤塗りつぶし・白文字 |
| Ghost | スキップ・閉じる | 背景なし・テキストのみ |

#### 適用スコープ（優先順）

| 優先度 | 対象ファイル | 理由 |
|-------|------------|------|
| 高 | `input_window.py` | 最も頻繁に目に触れる |
| 高 | `first_run_wizard.py` | 新規作成のため最初から定数を使用 |
| 中 | `settings_window.py` | 配布時に必ず触れる設定画面 |
| 低 | その他ウィンドウ | 次回以降に対応 |

- `main.py` の先頭で `ctk.set_appearance_mode("system")` を追加（Windows ライト/ダーク自動追従）

---

### 5. Windows自動起動オプション（autostart.py）

#### 実装方針

`HKCU\Software\Microsoft\Windows\CurrentVersion\Run` レジストリキーを使用。管理者権限不要。

```python
REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "AutoTicket"

def is_enabled() -> bool: ...
def enable(exe_path: str) -> None: ...   # sys.executable を渡す
def disable() -> None: ...
```

#### SettingsWindow への追加

既存設定項目の末尾にCTkSwitchを1行追加：

```
Windowsログイン時に自動起動  [ON/OFF]
```

「保存」ボタン押下時に `autostart.enable()` または `autostart.disable()` を呼び出す。

初回ウィザードのStep 3にも同じトグルを配置する。

#### エッジケース

| ケース | 挙動 |
|-------|------|
| `.py` で実行中（開発時）| `getattr(sys, 'frozen', False)` が False のときグレーアウト、「.exeビルド後に有効」と表示 |
| レジストリ書き込み失敗 | エラートースト表示 |
| exeを別フォルダに移動 | 起動時にパス不一致を検知し再登録を促すトースト |

---

## テスト方針

| テストファイル | 主要テストケース |
|-------------|--------------|
| `test_connection_monitor.py` | 状態遷移・コールバック発火タイミング・チェック間隔 |
| `test_draft_queue.py` | 追加・取得・削除・retry_count上限・空時の動作 |
| `test_autostart.py` | 登録・解除・is_enabled・py実行時のグレーアウト判定 |
| `test_first_run_wizard.py` | 各ステップ遷移・スキップ動作・config保存 |

既存の50件に加え、新規テスト約15件を追加予定。
