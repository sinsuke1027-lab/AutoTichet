# Widget Phase 2B: 起票内容の充実化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ConfirmPanel に description（説明）フィールドを追加し、AIが1問ヒアリングして自動生成する。

**Architecture:** `OllamaClient.parse()` のレスポンスに `clarifying_question` を追加。ユーザーが回答またはスキップすると `generate_description()` が説明文を生成し、ConfirmPanel の description テキストボックスに入力する。スキップ時は description 空のまま ConfirmPanel へ進む。

**Tech Stack:** customtkinter（既存）, ollama（既存）, pytest（既存）

---

## ファイル構成

| ファイル | 変更内容 |
|---------|---------|
| `widget/clients/ollama_client.py` | `parse()` に `clarifying_question` 追加・`generate_description()` 新規追加 |
| `widget/payload_builder.py` | `build_payload()` に `description` パラメータ追加 |
| `widget/windows/input_window.py` | HearingPanel 追加・ConfirmPanel に description フィールド追加 |
| `widget/tests/test_ollama_client.py` | 新規メソッドのテスト追加 |
| `widget/tests/test_payload_builder.py` | description テスト追加 |

---

## Task 1: `OllamaClient` の拡張

**Files:**
- Modify: `widget/clients/ollama_client.py`
- Test: `widget/tests/test_ollama_client.py`

- [ ] **Step 1: 失敗テストを書く**

`widget/tests/test_ollama_client.py` の末尾に追加：

```python
# --- 2B: clarifying_question / generate_description ---

def test_parse_returns_clarifying_question():
    from widget.clients.ollama_client import OllamaClient
    mock_content = (
        '{"title": "報告書作成", "due_date": null, "assignee_name": null, '
        '"priority": "medium", "clarifying_question": "目的を一言で教えてください"}'
    )
    with patch("ollama.chat", return_value=_mock_ollama_response(mock_content)):
        client = OllamaClient()
        result = client.parse("報告書を作る")
    assert result["clarifying_question"] == "目的を一言で教えてください"


def test_parse_clarifying_question_can_be_null():
    from widget.clients.ollama_client import OllamaClient
    mock_content = (
        '{"title": "定例MTG", "due_date": null, "assignee_name": null, '
        '"priority": "low", "clarifying_question": null}'
    )
    with patch("ollama.chat", return_value=_mock_ollama_response(mock_content)):
        client = OllamaClient()
        result = client.parse("定例MTGの準備")
    assert result["clarifying_question"] is None


def test_generate_description_returns_string():
    from widget.clients.ollama_client import OllamaClient
    with patch("ollama.chat", return_value=_mock_ollama_response("月次報告書を作成します。期限は月末です。")):
        client = OllamaClient()
        result = client.generate_description(
            original_text="月次報告書を作る",
            answer="月末締め切りの提出用です",
        )
    assert isinstance(result, str)
    assert len(result) > 0


def test_generate_description_returns_empty_on_error():
    from widget.clients.ollama_client import OllamaClient
    with patch("ollama.chat", side_effect=Exception("error")):
        client = OllamaClient()
        result = client.generate_description("テキスト", "回答")
    assert result == ""
```

- [ ] **Step 2: テストが失敗することを確認**

```
pytest widget/tests/test_ollama_client.py::test_parse_returns_clarifying_question -v
```
Expected: FAIL（`clarifying_question` キーが存在しない）

- [ ] **Step 3: `ollama_client.py` を実装**

`_SYSTEM_PROMPT` を以下に置き換え：

```python
_SYSTEM_PROMPT = """\
タスク管理アシスタント。今日: {today}
入力からタスク情報を抽出し、JSON のみ出力（他のテキスト・コードブロック不要）。

{{"title":"タスク名(必須)","due_date":"YYYY-MM-DD or null","assignee_name":"担当者名 or null","priority":"low|medium|high|urgent or null","clarifying_question":"説明文作成のためのヒアリング質問1問 or null"}}\
"""
```

`_EMPTY` を更新：

```python
_EMPTY: dict = {
    "title": None,
    "due_date": None,
    "assignee_name": None,
    "priority": None,
    "clarifying_question": None,
}
```

`_DESCRIBE_PROMPT` 定数を追加（クラス外、`_VISION_PROMPT` の後）：

```python
_DESCRIBE_PROMPT = """\
以下の情報をもとにタスクの説明文を1〜3文で生成してください（JSON不要・自然文で）。

元のテキスト: {original_text}
ヒアリング回答: {answer}\
"""
```

`OllamaClient` クラスに `generate_description` メソッドを追加：

```python
def generate_description(self, original_text: str, answer: str) -> str:
    prompt = _DESCRIBE_PROMPT.format(
        original_text=original_text[:500],
        answer=answer[:200],
    )
    logging.debug("OllamaClient.generate_description model=%s", self.model)
    try:
        response = ollama.chat(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.3},
        )
        return response["message"]["content"].strip()
    except Exception as exc:
        logging.error("OllamaClient.generate_description error: %s", exc)
        return ""
```

- [ ] **Step 4: テストが通ることを確認**

```
pytest widget/tests/test_ollama_client.py -v
```
Expected: 11 passed（既存 7 + 新規 4）

- [ ] **Step 5: コミット**

```
git add widget/clients/ollama_client.py widget/tests/test_ollama_client.py
git commit -m "feat(widget): parse() に clarifying_question 追加・generate_description() 実装"
```

---

## Task 2: `build_payload()` に description を追加

**Files:**
- Modify: `widget/payload_builder.py`
- Test: `widget/tests/test_payload_builder.py`

- [ ] **Step 1: 失敗テストを書く**

`widget/tests/test_payload_builder.py` の末尾に追加：

```python
def test_build_payload_includes_description():
    from widget.payload_builder import build_payload
    payload = build_payload(
        title="テストタスク",
        due_date_str="",
        assignee_display="（なし）",
        project_name="（なし）",
        priority_jp="中",
        users=[],
        projects=[],
        description="これはテスト用の説明文です。",
    )
    assert payload["description"] == "これはテスト用の説明文です。"


def test_build_payload_description_defaults_to_empty():
    from widget.payload_builder import build_payload
    payload = build_payload(
        title="テストタスク",
        due_date_str="",
        assignee_display="（なし）",
        project_name="（なし）",
        priority_jp="中",
        users=[],
        projects=[],
    )
    assert payload["description"] == ""
```

- [ ] **Step 2: テストが失敗することを確認**

```
pytest widget/tests/test_payload_builder.py::test_build_payload_includes_description -v
```
Expected: FAIL（`description` 引数が存在しない）

- [ ] **Step 3: `payload_builder.py` を実装**

`build_payload()` のシグネチャを以下に変更：

```python
def build_payload(
    title: str,
    due_date_str: str,
    assignee_display: str,
    project_name: str,
    priority_jp: str,
    users: list[UserInfo],
    projects: list[ProjectInfo],
    description: str = "",
) -> dict:
```

戻り値の dict に `"description": description` を追加：

```python
    return {
        "title": title,
        "due_date": normalize_date(due_date_str),
        "assignee_id": assignee_id,
        "project_id": project_id,
        "priority": jp_to_priority(priority_jp),
        "description": description,
        "source_type": "manual",
    }
```

- [ ] **Step 4: テストが通ることを確認**

```
pytest widget/tests/test_payload_builder.py -v
```
Expected: 7 passed（既存 5 + 新規 2）

- [ ] **Step 5: コミット**

```
git add widget/payload_builder.py widget/tests/test_payload_builder.py
git commit -m "feat(widget): build_payload() に description フィールドを追加"
```

---

## Task 3: ConfirmPanel に description フィールドを追加（2B-1）

**Files:**
- Modify: `widget/windows/input_window.py`

- [ ] **Step 1: `_build_confirm_panel` を編集**

`widget/windows/input_window.py` の `_build_confirm_panel` 内で、優先度行の直後（`_row("優先度", ...)` の後）に以下を追加：

```python
        # 説明（任意）
        self._desc_text = ctk.CTkTextbox(frame, height=60)
        _row("説明", self._desc_text)
        desc_val = parsed.get("description") or ""
        if desc_val:
            self._desc_text.insert("1.0", desc_val)
```

ウィンドウ高さを 330 → 420 に変更：

```python
        self.geometry("440x420")
```

- [ ] **Step 2: `_on_send` で description を渡す**

`_on_send` 内の `build_payload` 呼び出しを以下に変更：

```python
        payload = build_payload(
            title=title,
            due_date_str=self._due_entry.get(),
            assignee_display=self._assignee_combo.get(),
            project_name=self._project_combo.get(),
            priority_jp=self._priority_combo.get(),
            users=self._users,
            projects=self._projects,
            description=self._desc_text.get("1.0", "end").strip(),
        )
```

- [ ] **Step 3: 手動動作確認**

ウィジェットを起動し、テキストを入力 → 「AIで起票する」→ ConfirmPanel に「説明」欄が表示されることを確認。

- [ ] **Step 4: テストが引き続き通ることを確認**

```
pytest widget/tests/ -v
```
Expected: 全テスト PASS

- [ ] **Step 5: コミット**

```
git add widget/windows/input_window.py
git commit -m "feat(widget): ConfirmPanel に description フィールドを追加（2B-1）"
```

---

## Task 4: HearingPanel の実装（2B-2）

**Files:**
- Modify: `widget/windows/input_window.py`

ヒアリングフローの概要：
1. `_on_ai_done(parsed)` → `clarifying_question` があれば `_build_hearing_panel(parsed)` へ
2. HearingPanel: 質問テキスト + 回答ボックス + 「スキップ」「回答して起票」ボタン
3. スキップ → `_build_confirm_panel(parsed)`（description は空）
4. 回答 → `generate_description()` をスレッドで実行 → `parsed["description"]` にセット → `_build_confirm_panel(parsed)`

- [ ] **Step 1: `_on_ai_done` を修正**

現在の `_on_ai_done` を以下に置き換え：

```python
    def _on_ai_done(self, parsed: dict) -> None:
        self._stop_elapsed_timer()
        self._submit_btn.configure(state="normal", text="AIで起票する →")
        self._status_lbl.configure(text="")
        question = parsed.get("clarifying_question")
        if question:
            self._build_hearing_panel(parsed, question)
        else:
            self._build_confirm_panel(parsed)
```

- [ ] **Step 2: `_build_hearing_panel` を追加**

`_on_ai_done` の直後に追加：

```python
    def _build_hearing_panel(self, parsed: dict, question: str) -> None:
        for w in self.winfo_children():
            w.destroy()
        self.geometry("440x260")
        self.title("AutoTicket - ヒアリング")

        ctk.CTkLabel(
            self, text="💬 AIからの質問", font=ctk.CTkFont(weight="bold")
        ).pack(pady=(14, 6))

        ctk.CTkLabel(
            self, text=question, wraplength=400, justify="left"
        ).pack(padx=20, pady=(0, 10))

        self._hearing_text = ctk.CTkTextbox(self, height=60, width=400)
        self._hearing_text.pack(padx=20, pady=(0, 10))
        self._hearing_text.focus()

        self._hearing_status = ctk.CTkLabel(self, text="", text_color="gray")
        self._hearing_status.pack()

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(pady=(4, 12))

        ctk.CTkButton(
            btn_row, text="スキップ", width=110,
            fg_color="gray40", hover_color="gray30",
            command=lambda: self._build_confirm_panel(parsed),
        ).pack(side="left", padx=8)

        self._hearing_btn = ctk.CTkButton(
            btn_row, text="回答して起票へ →", width=160,
            command=lambda: self._on_hearing_answer(parsed),
        )
        self._hearing_btn.pack(side="left", padx=8)

    def _on_hearing_answer(self, parsed: dict) -> None:
        answer = self._hearing_text.get("1.0", "end").strip()
        if not answer:
            self._build_confirm_panel(parsed)
            return

        self._hearing_btn.configure(state="disabled", text="生成中…")
        self._start_elapsed_timer("説明文を生成中")
        original_text = getattr(self, "_last_input_text", "")

        def _run() -> None:
            description = self._ollama.generate_description(original_text, answer)
            parsed["description"] = description
            self.after(0, lambda: self._on_description_done(parsed))

        threading.Thread(target=_run, daemon=True).start()

    def _on_description_done(self, parsed: dict) -> None:
        self._stop_elapsed_timer()
        self._build_confirm_panel(parsed)
```

- [ ] **Step 3: `_on_ai_submit` で入力テキストを保持**

`_on_ai_submit` 内で `parsed = self._ollama.parse(text)` を呼ぶ前に入力テキストを保存：

`_on_ai_submit` の `def _run() -> None:` を以下に変更：

```python
        self._last_input_text = text

        def _run() -> None:
            parsed = self._ollama.parse(text)
            self.after(0, lambda: self._on_ai_done(parsed))
```

- [ ] **Step 4: テストが引き続き通ることを確認**

```
pytest widget/tests/ -v
```
Expected: 全テスト PASS

- [ ] **Step 5: コミット**

```
git add widget/windows/input_window.py
git commit -m "feat(widget): AIヒアリング → description 自動生成を実装（2B-2）"
```

---

## 完了確認チェックリスト

- [ ] `parse()` が `clarifying_question` を含む dict を返す
- [ ] `generate_description()` が文字列を返す
- [ ] `build_payload()` が `description` を含む
- [ ] ConfirmPanel に description テキストボックスが表示される
- [ ] ヒアリング質問がある場合 HearingPanel が表示される
- [ ] スキップで description 空のまま ConfirmPanel へ進む
- [ ] 回答で description が生成されて ConfirmPanel に表示される
- [ ] 全テスト通過（`pytest widget/tests/ -v`）
