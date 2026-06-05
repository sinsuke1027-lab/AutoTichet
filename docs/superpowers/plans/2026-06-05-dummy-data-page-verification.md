# ダミーデータ拡充 + 全ページ動作検証 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `scripts/seed_dummy_data.py` にテンプレート・マイルストーン・サブタスク・コメント・実績工数・追加タスクを追加し、全13ページをPlaywright MCP で 1 ページずつスクリーンショット付きで動作検証する

**Architecture:** シードスクリプトを拡充して本番 Supabase DB（HF Spaces バックエンド経由）へ投入し、Playwright MCP で https://auto-tichet.vercel.app を操作して検証結果をスクリーンショットで記録する。検証は「admin-seed」と「石川 智代」の2ユーザーを使い分ける。

**Tech Stack:** Python + httpx（シード）、Playwright MCP（ブラウザ検証）、DEV_MODE 認証（X-Dev-User ヘッダー）

---

## 前提・環境確認

- バックエンド: https://sinsuke1027-lab-auto-tichet.hf.space/api/v1（HF Spaces）  
- フロントエンド: https://auto-tichet.vercel.app  
- ローカル実行: `SEED_BASE_URL=https://sinsuke1027-lab-auto-tichet.hf.space/api/v1 python scripts/seed_dummy_data.py`  
- Playwright ログイン: `/dev-login` → ユーザー選択 → 「開発ログイン」ボタン  
- スクリーンショット保存先: `.playwright-mcp/screenshots/YYYY-MM-DD-<page>.png`

---

## File Structure

| 変更ファイル | 内容 |
|------------|------|
| `scripts/seed_dummy_data.py` | テンプレート・マイルストーン・サブタスク・コメント・実績工数・追加タスク追加 |
| `.playwright-mcp/screenshots/` | 各ページのスクリーンショット（自動生成） |

---

### Task 1: seed_dummy_data.py 拡充

**Files:**
- Modify: `scripts/seed_dummy_data.py`

#### 追加内容の設計

**追加するデータ一覧:**

1. **テンプレート** (3件): `POST /api/v1/templates`
   - 「採用フロー標準テンプレート」(タスク4件入り)
   - 「社内イベント準備テンプレート」(タスク3件入り)
   - 「月次報告テンプレート」(タスク2件入り)

2. **マイルストーン** (4件): `POST /api/v1/projects/{project_id}/milestones`
   - 総務: 「上期総務業務完了」(+60日)、「下期キックオフ」(+90日)
   - 人事: 「採用完了」(+40日)、「下半期評価開始」(+120日)

3. **サブタスク** (5件): `POST /tasks` で `parent_task_id` を指定
   - 「社内報作成（6月号）」のサブタスク: 「取材メモ整理」「下書き作成」「最終校正」
   - 「採用要件定義」のサブタスク: 「スキル要件確認」「給与レンジ確認」

4. **コメント** (4件): `POST /tasks/{task_id}/comments`
   - 「よく知るVORN5月」に石川・梅本からコメント
   - 「採用要件定義」に山田・鈴木からコメント

5. **実績工数** (6件): `POST /tasks/{task_id}/work-hours` (actual_hours 付き)
   - 梅本・芝田・寄田・田中 各2件（Schedule・Workload 検証用）

6. **追加タスク** (8件): Schedule/Workload ページ用に来週・再来週に分散
   - 梅本: 「6月度社内報草稿」「備品在庫棚卸し」
   - 芝田: 「入館証新規発行」「清掃業者打合せ」
   - 寄田: 「健康診断案内メール」「残業時間集計」
   - 田中: 「新卒研修日程調整」「インターン対応」

- [ ] **Step 1: TemplateCreate モデルを確認する**

```bash
# テンプレート作成 API のスキーマを確認
python -c "
import asyncio, httpx, json, os
BASE = os.environ.get('SEED_BASE_URL', 'http://localhost:8000/api/v1')
HEADER = {'X-Dev-User': json.dumps({'userId':'admin-seed','displayName':'シードデータ管理者','email':'admin@dev.example.com','role':'admin','departmentTags':[]})}
async def check():
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f'{BASE}/templates', headers=HEADER)
        print('templates:', r.status_code, r.text[:200])
        r2 = await c.get(f'{BASE}/projects', headers=HEADER)
        print('projects:', r2.status_code, r2.text[:300])
asyncio.run(check())
"
```

Expected: 200 + existing templates/projects リスト

- [ ] **Step 2: seed_dummy_data.py に拡充コードを追加する**

`scripts/seed_dummy_data.py` の `main()` 関数内の `# 6. 依存関係登録` ブロックの**後**（`print("\n=== 完了 ===")` の前）に以下を追加する:

```python
        # 7. テンプレート作成
        print("\n=== 7. テンプレート作成 ===")

        async def create_template_if_missing(
            name: str, description: str, template_data: dict
        ) -> str | None:
            existing = await get(client, "/templates")
            if isinstance(existing, list):
                for t in existing:
                    if t.get("name") == name:
                        print(f"  SKIP (already exists): template '{name}'")
                        return t["id"]
            r = await post(client, "/templates", {
                "name": name,
                "description": description,
                "template_data": template_data,
            })
            if r:
                print(f"  OK template '{name}' → {r.get('id','')[:8]}...")
            return r.get("id")

        await create_template_if_missing(
            "採用フロー標準テンプレート",
            "採用開始から内定まで4ステップのタスクセット",
            {
                "tasks": [
                    {"title": "採用要件定義", "priority": "high", "estimated_days": 7},
                    {"title": "求人票作成・掲載", "priority": "high", "estimated_days": 7},
                    {"title": "書類審査・一次選考", "priority": "medium", "estimated_days": 14},
                    {"title": "最終面接・合否通知", "priority": "high", "estimated_days": 7},
                ]
            },
        )
        await create_template_if_missing(
            "社内イベント準備テンプレート",
            "社内イベント開催に必要な準備タスク3ステップ",
            {
                "tasks": [
                    {"title": "スピーカー・出演者調整", "priority": "high", "estimated_days": 14},
                    {"title": "出欠アンケート作成・送付", "priority": "medium", "estimated_days": 7},
                    {"title": "会場・配信設定確認", "priority": "medium", "estimated_days": 3},
                ]
            },
        )
        await create_template_if_missing(
            "月次報告テンプレート",
            "月次レポート作成の標準フロー",
            {
                "tasks": [
                    {"title": "データ集計・資料作成", "priority": "medium", "estimated_days": 3},
                    {"title": "上長レビュー・修正", "priority": "low", "estimated_days": 2},
                ]
            },
        )

        # 8. マイルストーン作成
        print("\n=== 8. マイルストーン作成 ===")

        async def create_milestone_if_missing(
            proj_id: str, title: str, due_days: int, description: str = ""
        ) -> None:
            milestones = await get(client, f"/projects/{proj_id}/milestones")
            if isinstance(milestones, list):
                for m in milestones:
                    if m.get("title") == title:
                        print(f"  SKIP (already exists): milestone '{title}'")
                        return
            r = await post(client, f"/projects/{proj_id}/milestones", {
                "title": title,
                "due_date": d(due_days),
                "description": description,
            }, header=ADMIN_HEADER)
            if r:
                print(f"  OK milestone '{title}' due:{d(due_days)}")

        await create_milestone_if_missing(
            soumu_id, "上期総務業務完了", 60, "6月末で総務上期タスクを完了させる"
        )
        await create_milestone_if_missing(
            soumu_id, "下期キックオフ", 90, "7月から下期の取り組みを開始"
        )
        await create_milestone_if_missing(
            jinji_id, "採用完了（夏季）", 40, "夏季採用枠の内定確定"
        )
        await create_milestone_if_missing(
            jinji_id, "下半期評価開始", 120, "9月末〜10月の評価サイクル開始"
        )

        # 9. サブタスク作成
        print("\n=== 9. サブタスク作成 ===")

        async def subtask(
            parent_id: str | None, title: str, assignee: str, priority: str, due_days: int,
            proj_id: str | None = None, section_id: str | None = None
        ) -> str | None:
            if not parent_id:
                return None
            key = (title, proj_id)
            if key in existing_tasks:
                print(f"  SKIP (already exists): [sub] {title}")
                return existing_tasks[key]
            body: dict = {
                "title": title,
                "description": "",
                "status": "not_started",
                "priority": priority,
                "assignee_id": assignee,
                "due_date": d(due_days),
                "visibility": "team",
                "tags": [],
                "project_id": proj_id,
                "section_id": section_id,
                "parent_task_id": parent_id,
            }
            r = await post(client, "/tasks", body, header=user_header(assignee))
            tid = r.get("id")
            if tid:
                print(f"  OK [sub] {title} → parent {parent_id[:8]}...")
            return tid

        report_jun_id = task_ids.get("report_jun")
        await subtask(report_jun_id, "取材メモ整理", "miyu-umemoto", "medium", 18, soumu_id, sec["report"])
        await subtask(report_jun_id, "下書き作成", "miyu-umemoto", "medium", 24, soumu_id, sec["report"])
        await subtask(report_jun_id, "最終校正・入稿", "tomoyo-ishikawa", "high", 28, soumu_id, sec["report"])

        recruit1_id = task_ids.get("recruit1")
        await subtask(recruit1_id, "スキル要件ヒアリング", "hanako-yamada", "high", 3, jinji_id, sec["recruit"])
        await subtask(recruit1_id, "給与レンジ確認", "takuya-suzuki", "medium", 5, jinji_id, sec["recruit"])

        # 10. コメント追加
        print("\n=== 10. コメント追加 ===")

        async def add_comment(task_id: str | None, author: str, content: str) -> None:
            if not task_id:
                return
            r = await post(
                client, f"/tasks/{task_id}/comments",
                {"content": content},
                header=user_header(author),
            )
            if r:
                print(f"  OK comment by {author} on task {task_id[:8]}...")

        vorn_may_id = task_ids.get("vorn_may")
        await add_comment(vorn_may_id, "tomoyo-ishikawa", "スピーカーの田中さんから資料受領済みです。当日の機材チェックをお願いします。")
        await add_comment(vorn_may_id, "miyu-umemoto", "配信用URLをSlackに共有しました。参加者への案内も完了しています。")

        recruit1_id = task_ids.get("recruit1")
        await add_comment(recruit1_id, "hanako-yamada", "各部門マネージャーへのヒアリングを完了しました。要件をドキュメントにまとめます。")
        await add_comment(recruit1_id, "takuya-suzuki", "給与レンジは市場調査後に確定します。来週中にフィードバックします。")

        # 11. 実績工数追加（Schedule / Workload 検証用）
        print("\n=== 11. 実績工数追加 ===")

        # 梅本: よく知るVORN5月に実績2h
        if task_ids.get("vorn_may"):
            r = await post(
                client, f"/tasks/{task_ids['vorn_may']}/work-hours",
                {"estimated_hours": 3.0, "actual_hours": 2.0, "notes": "スピーカー調整・連絡"},
                header=user_header("miyu-umemoto"),
            )
            if r:
                print(f"  OK 梅本 実績2h → vorn_may")

        # 芝田: 会場確認に実績1h
        venue_key = ("会場・配信設定確認", soumu_id)
        venue_id = existing_tasks.get(venue_key)
        if not venue_id:
            # task が今回作成されている可能性
            existing_list2 = await get(client, "/tasks?limit=200", header=ADMIN_HEADER)
            if isinstance(existing_list2, dict):
                for t in existing_list2.get("items", []):
                    if t["title"] == "会場・配信設定確認":
                        venue_id = t["id"]
                        break
        if venue_id:
            r = await post(
                client, f"/tasks/{venue_id}/work-hours",
                {"estimated_hours": 2.0, "actual_hours": 1.0, "notes": "機材確認完了"},
                header=user_header("tabito-shibata"),
            )
            if r:
                print(f"  OK 芝田 実績1h → 会場設定確認")

        # 寄田: 翌月残業見込みに実績3h
        if task_ids.get("overload2"):
            r = await post(
                client, f"/tasks/{task_ids['overload2']}/work-hours",
                {"estimated_hours": 3.0, "actual_hours": 3.0, "notes": "集計完了"},
                header=user_header("toshio-yorita"),
            )
            if r:
                print(f"  OK 寄田 実績3h")

        # 田中: 最終面接調整に実績2h
        if task_ids.get("recruit4"):
            r = await post(
                client, f"/tasks/{task_ids['recruit4']}/work-hours",
                {"estimated_hours": 2.0, "actual_hours": 2.0, "notes": "面接官スケジュール確認"},
                header=user_header("ichiro-tanaka"),
            )
            if r:
                print(f"  OK 田中 実績2h → 最終面接")

        # 12. Schedule/Workload 検証用追加タスク
        print("\n=== 12. 追加タスク（来週・再来週分散）===")

        for title, assignee, due, start, prio in [
            ("6月度社内報草稿",     "miyu-umemoto",    9,  7, "medium"),
            ("備品在庫棚卸し",      "tabito-shibata",  10, 8, "low"),
            ("入館証新規発行",      "tabito-shibata",  12, 10, "medium"),
            ("清掃業者打合せ",      "tabito-shibata",  14, 12, "low"),
            ("健康診断案内メール",   "toshio-yorita",   8,  7, "high"),
            ("残業時間月次集計",    "toshio-yorita",   11, 9, "medium"),
            ("新卒研修日程調整",    "ichiro-tanaka",   13, 11, "high"),
            ("インターン対応",      "ichiro-tanaka",   16, 14, "medium"),
        ]:
            proj = jinji_id if assignee in ("toshio-yorita", "ichiro-tanaka") else soumu_id
            section = sec["kintai"] if assignee == "toshio-yorita" else (
                sec["recruit"] if assignee == "ichiro-tanaka" else sec["proj"]
            )
            await task(
                title, assignee, "not_started", prio, due, start_days=start,
                proj_id=proj, section_id=section,
            )
```

- [ ] **Step 3: 追加コードに「完了」メッセージのコンソール出力を更新する**

`print("【検証ポイント】")` ブロックに以下を追記する（既存のprint文の**後**に追加）:

```python
        print("  テンプレート      : 採用フロー・社内イベント・月次報告の3件")
        print("  マイルストーン    : 総務2件・人事2件")
        print("  サブタスク        : 社内報6月号に3件・採用要件定義に2件")
        print("  コメント          : VORNタスク・採用タスクに各2件")
        print("  実績工数          : 梅本・芝田・寄田・田中に各1件")
        print("  追加タスク        : 来週〜再来週に8件分散配置")
```

- [ ] **Step 4: シードスクリプトを本番環境に対して実行する**

```bash
SEED_BASE_URL=https://sinsuke1027-lab-auto-tichet.hf.space/api/v1 python scripts/seed_dummy_data.py
```

Expected output (抜粋):
```
=== 7. テンプレート作成 ===
  OK template '採用フロー標準テンプレート' → xxxxxxxx...
  OK template '社内イベント準備テンプレート' → xxxxxxxx...
  OK template '月次報告テンプレート' → xxxxxxxx...

=== 8. マイルストーン作成 ===
  OK milestone '上期総務業務完了' due:2026-08-04
  ...

=== 9. サブタスク作成 ===
  OK [sub] 取材メモ整理 → parent xxxxxxxx...
  ...

=== 10. コメント追加 ===
  OK comment by tomoyo-ishikawa on task xxxxxxxx...
  ...
```

- [ ] **Step 5: コミットする**

```bash
git add scripts/seed_dummy_data.py
git commit -m "feat: seed data 拡充（テンプレート・マイルストーン・サブタスク・コメント・実績工数・追加タスク）"
```

---

### Task 2: Dashboard ページ検証

**Files:** なし（検証のみ）

- [ ] **Step 1: DEV ログイン（admin-seed）**

Playwright で https://auto-tichet.vercel.app/dev-login を開き、「シードデータ管理者」を選択してログイン

```
browser_navigate: https://auto-tichet.vercel.app/dev-login
browser_snapshot: ログイン画面を確認
browser_select_option または browser_click: シードデータ管理者 を選択
browser_click: 開発ログインボタン
browser_wait_for: /dashboard へのリダイレクト完了
```

- [ ] **Step 2: Dashboard 全体スクリーンショット**

```
browser_navigate: https://auto-tichet.vercel.app/dashboard
browser_take_screenshot: .playwright-mcp/screenshots/2026-06-05-dashboard-admin.png
```

Expected: KPI カード（総タスク数、完了率、期限超過、今日締め）が表示される

- [ ] **Step 3: KPI 数値を確認する**

```
browser_snapshot: Dashboard の KPI カード内容を読み取る
```

Expected:
- 総タスク数: 40件以上（拡充後）
- 期限超過: 1件以上（勤怠制度の見直し）
- 今日締め: 3件（石川の overload タスク群）※ admin は全件見える

- [ ] **Step 4: 「石川 智代」でログインして自分のタスクのみ表示を確認**

```
browser_navigate: https://auto-tichet.vercel.app/dev-login
browser_click: 石川 智代 を選択
browser_click: 開発ログインボタン
browser_navigate: https://auto-tichet.vercel.app/dashboard
browser_take_screenshot: .playwright-mcp/screenshots/2026-06-05-dashboard-soumu.png
```

Expected: 石川担当タスクのみ KPI に反映、負荷アラートバッジが表示される

---

### Task 3: MyPage 検証

**Files:** なし（検証のみ）

- [ ] **Step 1: 石川 智代 でログインして MyPage を開く**

```
browser_navigate: https://auto-tichet.vercel.app/my-page
browser_take_screenshot: .playwright-mcp/screenshots/2026-06-05-mypage-ishikawa.png
```

Expected: プロフィールカード（氏名・部署・日次キャパシティ）、自分の未完了タスク一覧が表示される

- [ ] **Step 2: 週次サマリーを確認する**

```
browser_snapshot: WeeklySummary コンポーネントの内容を読み取る
```

Expected: 今週の完了数・進行中数・未着手数が数値で表示される

- [ ] **Step 3: 担当タスク一覧をフィルターする**

```
browser_click: ステータスフィルター「進行中」を選択
browser_take_screenshot: .playwright-mcp/screenshots/2026-06-05-mypage-inprogress.png
```

Expected: 石川の進行中タスクのみ表示（月末経費精算取りまとめ 等）

---

### Task 4: Tasks 一覧・詳細 検証

**Files:** なし（検証のみ）

- [ ] **Step 1: Tasks 一覧を開く**

```
browser_navigate: https://auto-tichet.vercel.app/tasks
browser_take_screenshot: .playwright-mcp/screenshots/2026-06-05-tasks-list.png
```

Expected: 担当者列・プロジェクト列が表示、全タスクが一覧表示される

- [ ] **Step 2: 担当者フィルターを使う**

```
browser_click: 担当者フィルターのドロップダウン
browser_click: 石川 智代 を選択
browser_take_screenshot: .playwright-mcp/screenshots/2026-06-05-tasks-filter-ishikawa.png
```

Expected: 石川担当タスク（月末経費精算・社員名簿更新等）のみ表示

- [ ] **Step 3: 「社内報作成（6月号）」の詳細を開く**

```
browser_click: 社内報作成（6月号） の行をクリック
browser_take_screenshot: .playwright-mcp/screenshots/2026-06-05-task-detail-report-jun.png
```

Expected: タスク詳細モーダル/ページが開く

- [ ] **Step 4: サブタスクパネルを確認する**

```
browser_click: サブタスク タブ/セクション
browser_take_screenshot: .playwright-mcp/screenshots/2026-06-05-task-detail-subtasks.png
```

Expected: 「取材メモ整理」「下書き作成」「最終校正・入稿」の3件が表示される

- [ ] **Step 5: コメントパネルを確認する**

```
browser_click: コメント タブ/セクション
browser_take_screenshot: .playwright-mcp/screenshots/2026-06-05-task-detail-comments-vorn.png
```

（よく知るVORN5月 の詳細に移動してコメントを確認）

Expected: 石川・梅本のコメントが時系列で表示される

- [ ] **Step 6: 工数パネルを確認する**

```
browser_click: 工数 タブ/セクション
browser_take_screenshot: .playwright-mcp/screenshots/2026-06-05-task-detail-workhours.png
```

Expected: 見積工数・実績工数が表示（梅本のエントリー: 見積3h / 実績2h）

---

### Task 5: Board（カンバン）ページ検証

**Files:** なし（検証のみ）

**実装メモ:** `@dnd-kit/core` + `SortableContext` を使用。カラム間ドラッグ → `PATCH /tasks/{id}` でステータス更新（楽観的更新あり・失敗時ロールバック）。同カラム内ドラッグ → `reorder` API で順序変更。

- [ ] **Step 1: Board を開く（プロジェクトなし）**

```
browser_navigate: https://auto-tichet.vercel.app/board
browser_take_screenshot: .playwright-mcp/screenshots/2026-06-05-board-all.png
```

Expected: 未着手・進行中・完了・キャンセル の4カラムにタスクが分散している

- [ ] **Step 2: 総務業務管理プロジェクトでフィルター**

```
browser_click: プロジェクト選択ドロップダウン
browser_click: 総務業務管理 を選択
browser_take_screenshot: .playwright-mcp/screenshots/2026-06-05-board-soumu.png
```

Expected: 総務タスクのみカンバンに表示される

- [ ] **Step 3: 各カラムのタスク件数を確認する**

```
browser_snapshot: 各カラムの件数バッジ（未着手 N / 進行中 N / 完了 N）を読み取る
```

Expected: いずれかのカラムに1件以上タスクが存在する

- [ ] **Step 4: カードを別カラムへドラッグしてステータスが変わることを確認**

未着手カラムの「出欠アンケート作成」を「進行中」カラムへドラッグする:

```
browser_snapshot: 「出欠アンケート作成」カードの位置を取得（未着手カラム内）
browser_drag:
  startElement: 「出欠アンケート作成」カード
  endElement:   「進行中」カラムのドロップゾーン
browser_take_screenshot: .playwright-mcp/screenshots/2026-06-05-board-drag-cross-column.png
```

Expected:
- ドラッグ中: カードが半透明になり DragOverlay が表示される
- ドロップ後: 楽観的更新でカードが「進行中」カラムに即座に移動
- 「進行中」件数カウントが+1、「未着手」が-1 になる

- [ ] **Step 5: ドラッグ後のステータス変更が API に永続化されていることを確認**

```
browser_navigate: https://auto-tichet.vercel.app/board
browser_click: 総務業務管理 プロジェクトフィルター再選択
browser_take_screenshot: .playwright-mcp/screenshots/2026-06-05-board-after-reload.png
browser_snapshot: 「出欠アンケート作成」が「進行中」カラムにあることを確認
```

Expected: リロード後も「進行中」カラムに表示される（DB に永続化済み）

- [ ] **Step 6: 同カラム内ドラッグで並び替えを確認**

「進行中」カラム内で先頭カードを末尾へドラッグする:

```
browser_snapshot: 「進行中」カラム内のカード順序を記録（before）
browser_drag:
  startElement: 「進行中」カラムの先頭カード
  endElement:   「進行中」カラムの末尾カード
browser_take_screenshot: .playwright-mcp/screenshots/2026-06-05-board-drag-reorder.png
browser_snapshot: カード順序が変わっていることを確認（after）
```

Expected: 並び替え後、`reorder` API が呼ばれて順序が変わる。リロード後も順序が維持される。

- [ ] **Step 7: タスクカードをクリックして詳細に遷移することを確認**

```
browser_click: 「よく知るVORN5月」カードをクリック（ドラッグなし・クリックのみ）
browser_take_screenshot: .playwright-mcp/screenshots/2026-06-05-board-task-detail.png
browser_navigate_back: ボードに戻る
```

Expected: タスク詳細ページ（/tasks/{id}）に遷移し、戻れる

---

### Task 6: Calendar ページ検証

**Files:** なし（検証のみ）

**実装メモ:** `react-big-calendar` を使用。ドラッグ＆ドロップ用アドオン（`withDragAndDrop`）は**未導入**のため日付変更ドラッグは非対応。`onSelectEvent` でタスク詳細ページへ遷移するのみ。

- [ ] **Step 1: Calendar を開く**

```
browser_navigate: https://auto-tichet.vercel.app/calendar
browser_take_screenshot: .playwright-mcp/screenshots/2026-06-05-calendar-month.png
```

Expected: 当月カレンダービューが表示され、各日にタスクイベントバーが分散している

- [ ] **Step 2: 「前」「次」ボタンで月を移動できることを確認**

```
browser_click: 「次」ボタン（翌月へ）
browser_take_screenshot: .playwright-mcp/screenshots/2026-06-05-calendar-next-month.png
browser_click: 「前」ボタン（当月に戻る）
```

Expected: 月が切り替わり、タスクの表示も変わる

- [ ] **Step 3: 担当者フィルターで田中 一郎 を選択**

```
browser_click: 担当者フィルタードロップダウン
browser_click: 田中 一郎 を選択
browser_take_screenshot: .playwright-mcp/screenshots/2026-06-05-calendar-tanaka.png
```

Expected: 田中担当タスク（新卒研修日程調整・インターン対応等）のみ日付セルに表示

- [ ] **Step 4: 複数担当者フィルターを確認**

```
browser_click: 担当者フィルター → 田中 一郎 + 山田 花子 を複数選択
browser_take_screenshot: .playwright-mcp/screenshots/2026-06-05-calendar-multi-assignee.png
```

Expected: 2名のタスクが両方表示される（採用タスク群が見える）

- [ ] **Step 5: イベントをクリックしてタスク詳細に遷移することを確認**

```
browser_click: 日付セル内の任意のタスクイベントをクリック
browser_take_screenshot: .playwright-mcp/screenshots/2026-06-05-calendar-task-detail.png
browser_navigate_back
```

Expected: `/tasks/{id}` の詳細ページへ遷移する（react-big-calendar はクリックのみ対応、日程ドラッグは非対応）

- [ ] **Step 6: 密度ヒートマップを確認（タスクが多い日ほど青く塗られる）**

```
browser_snapshot: 担当者フィルターをクリア → 全タスク表示
browser_evaluate: 
  const cells = document.querySelectorAll('.rbc-date-cell')
  const colored = [...cells].filter(c => c.style.background || c.querySelector('[style*="background"]'))
  colored.length
```

Expected: タスクが集中している日付のセルが青みがかった背景色になっている（count 1-2: 薄青、3-5: 中青）

---

### Task 7: Gantt ページ検証

**Files:** なし（検証のみ）

**実装メモ:** `gantt-task-react` ライブラリ使用。バードラッグ → `onDateChange` → `reschedule.mutate({ taskId, { new_start_date, new_due_date } })` で PATCH API 呼び出し。バー右端リサイズも同 handler 経由で `due_date` を更新。

- [ ] **Step 1: Gantt を開く（人事業務管理プロジェクト）**

```
browser_navigate: https://auto-tichet.vercel.app/gantt
browser_click: プロジェクト選択ドロップダウン
browser_click: 人事業務管理 を選択
browser_take_screenshot: .playwright-mcp/screenshots/2026-06-05-gantt-jinji.png
```

Expected: 採用タスク4件（採用要件定義→求人票→選考→面接）のガントバーが表示される

- [ ] **Step 2: 依存関係の矢印が描画されることを確認**

```
browser_snapshot: ガントチャートのSVG/依存線の存在を確認
browser_take_screenshot: .playwright-mcp/screenshots/2026-06-05-gantt-dependencies.png
```

Expected: バー間に依存関係を示す矢印線（折れ線）が表示されている

- [ ] **Step 3: 今日ラインが表示されることを確認**

```
browser_evaluate: document.querySelector('.gantt-today-line, [data-today], ._3NhEf') !== null
```

Expected: `true`（`gantt-task-react` が描画する今日縦線が存在する）

- [ ] **Step 4: ガントバーをドラッグして日程を移動する**

「求人票作成」のバーを右へ3〜5日ドラッグする:

```
browser_snapshot: 「求人票作成」バーの位置（開始日・終了日）を記録（before）
browser_drag:
  startElement: 「求人票作成」バー中央
  endElement:   バー中央から右へ約3日分の位置（ピクセル換算: day_width × 3 px 右）
browser_take_screenshot: .playwright-mcp/screenshots/2026-06-05-gantt-drag-move.png
```

Expected:
- ドラッグ中: バーが右へスライドしてプレビュー表示される
- ドロップ後: `reschedule` API が呼ばれ、`new_start_date` と `new_due_date` が3日後にずれる
- ガント上でバーの位置が変わる

- [ ] **Step 5: バー右端をドラッグしてリサイズ（due_date 延長）する**

「採用要件定義」バーの右端（リサイズハンドル）を右へ2日ドラッグ:

```
browser_snapshot: 「採用要件定義」バーの due_date を記録（before）
browser_drag:
  startElement: 「採用要件定義」バーの右端リサイズハンドル
  endElement:   右端から右へ約2日分の位置
browser_take_screenshot: .playwright-mcp/screenshots/2026-06-05-gantt-drag-resize.png
```

Expected:
- ドロップ後: `new_due_date` が2日延長される、`new_start_date` は変わらない
- バーが右に長くなる

- [ ] **Step 6: リロードして日程変更が永続化されていることを確認**

```
browser_navigate: https://auto-tichet.vercel.app/gantt
browser_click: 人事業務管理 を再選択
browser_take_screenshot: .playwright-mcp/screenshots/2026-06-05-gantt-after-reload.png
browser_snapshot: 「求人票作成」「採用要件定義」の新しい日程を確認（before と異なる位置）
```

Expected: ドラッグ後の日程が DB に永続化されており、リロード後も変更が反映されている

- [ ] **Step 7: 依存関係の追加 UI を確認する**

```
browser_click: 「依存関係を追加」ボタン
browser_take_screenshot: .playwright-mcp/screenshots/2026-06-05-gantt-add-dep-modal.png
browser_click: キャンセル（モーダルを閉じる）
```

Expected: 先行タスク・後続タスクを選択するモーダルが開く

---

### Task 8: Schedule ページ検証

**Files:** なし（検証のみ）

**実装メモ:** `@dnd-kit/core` + `useDraggable/useDroppable` で週次7日カラムに対応。今日-3日〜今日+3日の7列 + 「未配置（`__unassigned__`）」列。ドラッグ → `updateTask.mutate({ id, start_date: newDate })` で PATCH API 呼び出し。未配置列へドラッグすると `start_date: null` になる。

- [ ] **Step 1: Schedule を開く**

```
browser_navigate: https://auto-tichet.vercel.app/schedule
browser_take_screenshot: .playwright-mcp/screenshots/2026-06-05-schedule-all.png
```

Expected: 今日-3日〜今日+3日の7日カラム + 「未配置」カラムにタスクが分散表示される

- [ ] **Step 2: タスクカードを別の日付列へドラッグして start_date が変わることを確認**

「未配置」列または任意の日付列のタスクを、今日の列へドラッグする:

```
browser_snapshot: ドラッグ対象タスク（例: 「6月度社内報草稿」）の現在の列を確認（before）
browser_drag:
  startElement: 「6月度社内報草稿」カード
  endElement:   今日の日付列のドロップゾーン
browser_take_screenshot: .playwright-mcp/screenshots/2026-06-05-schedule-drag-to-today.png
```

Expected:
- ドラッグ中: 対象カラムが青色ハイライト（`border: 2px solid #1677ff`）になる
- ドロップ後: カードが今日の列に移動し、`PATCH /tasks/{id}` で `start_date` が今日の日付に更新される

- [ ] **Step 3: タスクを「未配置」列へドラッグして start_date を外す**

任意の日付列のタスクを「未配置」列へドラッグする:

```
browser_drag:
  startElement: 任意の日付列のタスクカード
  endElement:   「未配置」列のドロップゾーン（点線ボーダー）
browser_take_screenshot: .playwright-mcp/screenshots/2026-06-05-schedule-drag-to-unassigned.png
```

Expected:
- ドロップ後: カードが「未配置」列に移動し、`start_date: null` が API に送信される

- [ ] **Step 4: リロードしてスケジュール変更が永続化されていることを確認**

```
browser_navigate: https://auto-tichet.vercel.app/schedule
browser_take_screenshot: .playwright-mcp/screenshots/2026-06-05-schedule-after-reload.png
browser_snapshot: 「6月度社内報草稿」が今日の列にあることを確認
```

Expected: リロード後も移動先の列に表示される（DB 永続化済み）

- [ ] **Step 5: 複数タスクが同一列に積み重なることを確認**

```
browser_snapshot: 「今日」列に複数タスクが縦に並んでいることを確認
```

Expected: 同じ `start_date` のタスクが同一列に複数表示される（スクロール可能）

---

### Task 9: Workload ページ検証

**Files:** なし（検証のみ）

- [ ] **Step 1: Workload を開く**

```
browser_navigate: https://auto-tichet.vercel.app/workload
browser_take_screenshot: .playwright-mcp/screenshots/2026-06-05-workload-all.png
```

Expected: ユーザーごとの工数棒グラフ/タイムラインが表示される

- [ ] **Step 2: 石川 智代 の負荷アラートバッジを確認**

```
browser_snapshot: 石川 智代 の行に 🔴 または警告バッジが存在することを確認
browser_take_screenshot: .playwright-mcp/screenshots/2026-06-05-workload-overload.png
```

Expected: 石川の今日分が 9h > 8h（capacity）のため超過バッジが表示される

- [ ] **Step 3: 部署フィルターで総務のみ表示**

```
browser_click: 部署フィルター → 総務（general_affairs）
browser_take_screenshot: .playwright-mcp/screenshots/2026-06-05-workload-soumu.png
```

Expected: 石川・梅本・芝田の3名分のみ表示される

---

### Task 10: Templates ページ検証

**Files:** なし（検証のみ）

- [ ] **Step 1: Templates を開く**

```
browser_navigate: https://auto-tichet.vercel.app/templates
browser_take_screenshot: .playwright-mcp/screenshots/2026-06-05-templates-list.png
```

Expected: 「採用フロー標準テンプレート」「社内イベント準備テンプレート」「月次報告テンプレート」の3件が表示される

- [ ] **Step 2: テンプレートの詳細を確認する**

```
browser_click: 採用フロー標準テンプレート をクリックまたは展開
browser_take_screenshot: .playwright-mcp/screenshots/2026-06-05-templates-detail.png
```

Expected: テンプレート内のタスク4件（採用要件定義・求人票作成・書類審査・最終面接）が表示される

- [ ] **Step 3: テンプレートを使ってタスク生成する（任意）**

```
browser_click: 「適用」または「このテンプレートを使う」ボタン
browser_take_screenshot: .playwright-mcp/screenshots/2026-06-05-templates-apply.png
```

Expected: タスク生成ダイアログまたは確認モーダルが表示される

---

### Task 11: Projects ページ検証

**Files:** なし（検証のみ）

- [ ] **Step 1: Projects 一覧を開く**

```
browser_navigate: https://auto-tichet.vercel.app/projects
browser_take_screenshot: .playwright-mcp/screenshots/2026-06-05-projects-list.png
```

Expected: 総務業務管理・人事業務管理の2プロジェクトが表示される

- [ ] **Step 2: 総務プロジェクトの詳細を開く**

```
browser_click: 総務業務管理 をクリック
browser_take_screenshot: .playwright-mcp/screenshots/2026-06-05-projects-soumu-detail.png
```

Expected: プロジェクト詳細（セクション一覧・タスク数・マイルストーンタイムライン）が表示される

- [ ] **Step 3: マイルストーンタイムラインを確認する**

```
browser_snapshot: マイルストーン（上期総務業務完了・下期キックオフ）が表示されることを確認
browser_take_screenshot: .playwright-mcp/screenshots/2026-06-05-projects-milestones.png
```

Expected: 2件のマイルストーンが日付順に表示される

---

### Task 12: Import ページ検証

**Files:** なし（検証のみ）

- [ ] **Step 1: Import を開く**

```
browser_navigate: https://auto-tichet.vercel.app/import
browser_take_screenshot: .playwright-mcp/screenshots/2026-06-05-import-top.png
```

Expected: CSV/Excel ファイルアップロードエリアが表示される

- [ ] **Step 2: CSV テンプレートのダウンロードリンクを確認**

```
browser_snapshot: 「CSVテンプレートをダウンロード」リンクの存在を確認
```

Expected: ダウンロードリンクが存在する

- [ ] **Step 3: 既存CSVをアップロードして解析プレビューを確認**

既存の `.playwright-mcp/tasks-20260604.csv` をアップロードする:
```
browser_file_upload: .playwright-mcp/tasks-20260604.csv をアップロードフィールドに設定
browser_take_screenshot: .playwright-mcp/screenshots/2026-06-05-import-preview.png
```

Expected: CSVの内容がプレビューテーブルに表示され、インポート対象件数が表示される

---

### Task 13: Admin ページ検証

**Files:** なし（検証のみ）

前提: admin-seed でログインしている状態

- [ ] **Step 1: Admin を開く**

```
browser_navigate: https://auto-tichet.vercel.app/admin
browser_take_screenshot: .playwright-mcp/screenshots/2026-06-05-admin-top.png
```

Expected: Users タブが選択された状態の管理画面が表示される

- [ ] **Step 2: Users タブでユーザー一覧を確認**

```
browser_snapshot: ユーザー一覧（8件: 管理者1 + 総務3 + 人事4）を確認
browser_take_screenshot: .playwright-mcp/screenshots/2026-06-05-admin-users.png
```

Expected: 全8ユーザーが一覧表示され、role・department_tags が表示される

- [ ] **Step 3: AlertSettings タブを確認**

```
browser_click: 「アラート設定」タブ
browser_take_screenshot: .playwright-mcp/screenshots/2026-06-05-admin-alert-settings.png
```

Expected: 負荷アラートのしきい値設定フォームが表示される（デフォルト値が入力されている）

- [ ] **Step 4: OrgSettings タブを確認**

```
browser_click: 「組織設定」タブ
browser_take_screenshot: .playwright-mcp/screenshots/2026-06-05-admin-org-settings.png
```

Expected: 組織名・タイムゾーン等の設定フォームが表示される

---

### Task 14: Help ページ検証

**Files:** なし（検証のみ）

- [ ] **Step 1: Help を開く**

```
browser_navigate: https://auto-tichet.vercel.app/help
browser_take_screenshot: .playwright-mcp/screenshots/2026-06-05-help-top.png
```

Expected: ヘルプページが表示される（FAQまたは機能説明が含まれる）

- [ ] **Step 2: ページ内容を確認する**

```
browser_snapshot: ヘルプコンテンツのセクション見出しを確認
```

Expected: 主要機能（タスク管理・カンバン・ガント・インポート等）の説明が含まれる

---

## 検証完了基準

| ページ | 最低確認項目 |
|------|-------------|
| Dashboard | KPI 4件表示・石川の負荷アラート |
| MyPage | 自分のタスク一覧・週次サマリー |
| Tasks 一覧 | 担当者/プロジェクト列・フィルター動作 |
| Tasks 詳細 | サブタスク3件・コメント2件・工数表示 |
| Board | 4カラム表示・カラム間ドラッグ（ステータス変更）・同カラムドラッグ（並び替え）・リロード永続化 |
| Calendar | タスクイベント表示・担当者フィルター・月ナビゲーション・クリックで詳細遷移（DnD 非対応確認） |
| Gantt | 採用4タスクバー・依存矢印・バードラッグ日程移動・バーリサイズ・リロード永続化 |
| Schedule | 7日カラム表示・タスクドラッグで日付変更・未配置列へドラッグ・リロード永続化 |
| Workload | 石川の超過バッジ・部署フィルター |
| Templates | 3件表示・タスク内容展開 |
| Projects | 2プロジェクト・マイルストーン2件 |
| Import | CSV アップロードプレビュー |
| Admin | ユーザー8件・AlertSettings 表示 |
| Help | ページが開いてコンテンツ表示 |
