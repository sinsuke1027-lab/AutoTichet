"""
総務・人事チームのダミーデータ投入スクリプト

前提: バックエンドが DEV_MODE=true で localhost:8000 で動いていること
実行: python scripts/seed_dummy_data.py
"""

import asyncio
import json
import httpx
from datetime import date, timedelta

TODAY = date.today()
BASE = "http://localhost:8000/api/v1"

ADMIN_HEADER = {
    "X-Dev-User": json.dumps({
        "userId": "admin-seed",
        "displayName": "シードデータ管理者",
        "email": "admin@dev.example.com",
        "role": "admin",
        "departmentTags": [],
    })
}

# ── ユーザー定義 ──────────────────────────────────────────────
SOUMU_USERS = [
    {"user_id": "tomoyo-ishikawa", "display_name": "石川 智代", "email": "tomoyo-ishikawa@vorn.co.jp",
     "role": "leader", "department_tags": ["general_affairs"], "capacity_hours_per_day": 8.0},
    {"user_id": "miyu-umemoto",    "display_name": "梅本 美結", "email": "miyu-umemoto@vorn.co.jp",
     "role": "member", "department_tags": ["general_affairs"], "capacity_hours_per_day": 8.0},
    {"user_id": "tabito-shibata",  "display_name": "芝田 旅人", "email": "tabito-shibata@vorn.co.jp",
     "role": "member", "department_tags": ["general_affairs"], "capacity_hours_per_day": 8.0},
]

JINJI_USERS = [
    {"user_id": "takuya-suzuki",  "display_name": "鈴木 拓哉", "email": "takuya-suzuki@vorn.co.jp",
     "role": "leader", "department_tags": ["human_resources"], "capacity_hours_per_day": 8.0},
    {"user_id": "toshio-yorita",  "display_name": "寄田 俊雄", "email": "toshio-yorita@vorn.co.jp",
     "role": "member", "department_tags": ["human_resources"], "capacity_hours_per_day": 8.0},
    {"user_id": "hanako-yamada",  "display_name": "山田 花子", "email": "hanako-yamada@vorn.co.jp",
     "role": "member", "department_tags": ["human_resources"], "capacity_hours_per_day": 8.0},
    {"user_id": "ichiro-tanaka",  "display_name": "田中 一郎", "email": "ichiro-tanaka@vorn.co.jp",
     "role": "member", "department_tags": ["human_resources"], "capacity_hours_per_day": 8.0},
]

ALL_USERS = SOUMU_USERS + JINJI_USERS

# ── ヘルパー ──────────────────────────────────────────────────
def d(days: int) -> str:
    """TODAY から days 日後の日付文字列"""
    return (TODAY + timedelta(days=days)).isoformat()

def user_header(user_id: str) -> dict:
    u = next(u for u in ALL_USERS if u["user_id"] == user_id)
    return {"X-Dev-User": json.dumps({
        "userId": u["user_id"],
        "displayName": u["display_name"],
        "email": u["email"],
        "role": u["role"],
        "departmentTags": u["department_tags"],
    })}

async def post(client: httpx.AsyncClient, path: str, body: dict, header: dict = ADMIN_HEADER) -> dict:
    r = await client.post(f"{BASE}{path}", json=body, headers=header)
    if r.status_code == 409:
        print(f"  SKIP (already exists): POST {path}")
        return {}
    if not r.is_success:
        print(f"  ERROR {r.status_code}: POST {path}")
        try:
            print(f"  detail: {r.json()}")
        except Exception:
            print(f"  body: {r.text[:300]}")
        r.raise_for_status()
    return r.json()


async def get(client: httpx.AsyncClient, path: str, header: dict = ADMIN_HEADER) -> list | dict:
    r = await client.get(f"{BASE}{path}", headers=header)
    r.raise_for_status()
    return r.json()


async def get_or_create_project(client: httpx.AsyncClient, name: str, description: str) -> str | None:
    """既存プロジェクトを名前で検索し、なければ作成して ID を返す。"""
    projects = await get(client, "/projects")
    if isinstance(projects, list):
        for p in projects:
            if p.get("name") == name:
                print(f"  SKIP (already exists): project '{name}' → {p['id']}")
                return p["id"]
    result = await post(client, "/projects", {"name": name, "description": description, "status": "active"})
    return result.get("id")


async def get_or_create_section(client: httpx.AsyncClient, proj_id: str, name: str) -> str | None:
    """既存セクションを名前で検索し、なければ作成して ID を返す。"""
    sections = await get(client, f"/projects/{proj_id}/sections")
    if isinstance(sections, list):
        for s in sections:
            if s.get("name") == name:
                print(f"  SKIP (already exists): section '{name}' → {s['id']}")
                return s["id"]
    result = await post(client, f"/projects/{proj_id}/sections", {"name": name})
    return result.get("id")

# ── メイン ────────────────────────────────────────────────────
async def main() -> None:
    async with httpx.AsyncClient(timeout=30) as client:

        # 1. ユーザー作成（admin-seed を先に作成してから一般ユーザーを作成）
        print("\n=== 1. ユーザー作成 ===")
        admin_user = {
            "user_id": "admin-seed",
            "display_name": "シードデータ管理者",
            "email": "admin@dev.example.com",
            "role": "admin",
            "department_tags": [],
            "capacity_hours_per_day": 8.0,
        }
        result = await post(client, "/admin/users", admin_user)
        if result:
            print(f"  OK {admin_user['display_name']} ({admin_user['role']})")
        for u in ALL_USERS:
            result = await post(client, "/admin/users", u)
            if result:
                print(f"  OK {u['display_name']} ({u['role']})")

        # 2. プロジェクト作成（既存あればスキップ）
        print("\n=== 2. プロジェクト作成 ===")
        soumu_id = await get_or_create_project(
            client, "総務業務管理", "社内イベント・オフィス管理・社内報等の総務業務"
        )
        jinji_id = await get_or_create_project(
            client, "人事業務管理", "勤怠・資格・採用・保険料率変更等の人事業務"
        )
        print(f"  総務業務管理: {soumu_id}")
        print(f"  人事業務管理: {jinji_id}")

        if not soumu_id or not jinji_id:
            print("プロジェクト取得/作成に失敗しました。終了します。")
            return

        # 3. セクション作成（既存あればスキップ）
        print("\n=== 3. セクション作成 ===")
        sec = {}
        for sec_name, proj_id, key in [
            ("よく知るVORN",       soumu_id, "vorn"),
            ("まとめ・社内報",     soumu_id, "report"),
            ("プロジェクト",       soumu_id, "proj"),
            ("勤怠管理",           jinji_id, "kintai"),
            ("キャリア・資格管理", jinji_id, "career"),
            ("保険料率等変更",     jinji_id, "insurance"),
            ("採用",               jinji_id, "recruit"),
        ]:
            sec[key] = await get_or_create_section(client, proj_id, sec_name)
            print(f"  {sec_name}: {sec[key]}")

        # 4. タスク作成（プロジェクトにタスクが既にあればスキップ）
        print("\n=== 4. タスク作成 ===")

        # 既存タスクを title+project_id で索引化して重複防止
        existing_tasks: dict[tuple[str, str | None], str] = {}
        existing_list = await get(client, "/tasks?limit=200", header=ADMIN_HEADER)
        if isinstance(existing_list, dict):
            for t in existing_list.get("items", []):
                existing_tasks[(t["title"], t.get("project_id"))] = t["id"]

        task_ids: dict[str, str] = {}

        async def task(title, assignee, status, priority, due_days, start_days=None,
                       desc="", tags=None, visibility="team", proj_id=None, section_id=None) -> str | None:
            key = (title, proj_id)
            if key in existing_tasks:
                print(f"  SKIP (already exists): [{priority}] {title}")
                return existing_tasks[key]
            body: dict = {
                "title": title,
                "description": desc,
                "status": status,
                "priority": priority,
                "assignee_id": assignee,
                "due_date": d(due_days) if due_days is not None else None,
                "start_date": d(start_days) if start_days is not None else None,
                "visibility": visibility,
                "tags": tags or [],
                "project_id": proj_id,
                "section_id": section_id,
            }
            r = await post(client, "/tasks", body, header=user_header(assignee))
            tid = r.get("id")
            if tid:
                print(f"  OK [{priority}] {title} → {assignee} / due:{d(due_days) if due_days is not None else '-'}")
            return tid

        # ─── 総務: よく知るVORN ───────────────────────────────
        task_ids["vorn_may"] = await task(
            "よく知るVORN5月（横浜）5/29",
            "miyu-umemoto", "in_progress", "high", 8,
            desc="5月のよく知るVORN開催準備。スピーカー調整・アジェンダ確定・会場手配が必要。",
            tags=["社内イベント"], proj_id=soumu_id, section_id=sec["vorn"],
        )
        task_ids["vorn_jun"] = await task(
            "よく知るVORN6月（横浜）6/26",
            "miyu-umemoto", "not_started", "medium", 36,
            desc="6月のよく知るVORN開催準備。",
            tags=["社内イベント"], proj_id=soumu_id, section_id=sec["vorn"],
        )
        await task(
            "スピーカー調整（1か月前目途）",
            "tomoyo-ishikawa", "not_started", "high", 5,
            desc="6月開催スピーカーへの依頼連絡。",
            proj_id=soumu_id, section_id=sec["vorn"],
        )
        await task(
            "出欠アンケート作成",
            "miyu-umemoto", "not_started", "medium", 15,
            proj_id=soumu_id, section_id=sec["vorn"],
        )
        await task(
            "会場・配信設定確認",
            "tabito-shibata", "not_started", "medium", 2,
            proj_id=soumu_id, section_id=sec["vorn"],
        )

        # ─── 総務: まとめ・社内報 ────────────────────────────
        await task(
            "6月10日まとめ（議事録修正）",
            "tomoyo-ishikawa", "in_progress", "low", 40,
            desc="よく知るVORN6月回の議事録をまとめて社内報へ反映する。",
            proj_id=soumu_id, section_id=sec["report"],
        )
        await task(
            "社内報作成（5月号）",
            "miyu-umemoto", "completed", "medium", -6,
            desc="5月号社内報。完了済み。",
            proj_id=soumu_id, section_id=sec["report"],
        )
        # ← F-04 類似タスク検証用（「社内報作成」という共通キーワード）
        task_ids["report_jun"] = await task(
            "社内報作成（6月号）",
            "miyu-umemoto", "not_started", "medium", 30,
            desc="6月号社内報の作成。5月号と類似タイトルのため、F-04 の重複警告が表示されることを確認。",
            proj_id=soumu_id, section_id=sec["report"],
        )
        await task(
            "社内報校正・最終確認",
            "tomoyo-ishikawa", "not_started", "low", 35,
            proj_id=soumu_id, section_id=sec["report"],
        )

        # ─── 総務: プロジェクト ──────────────────────────────
        await task(
            "AIでまとめる社内オフィスガイド作成",
            "miyu-umemoto", "in_progress", "high", 10,
            desc="3月〜4月のよく知るVORN内容をもとに社内オフィスガイドを AI でまとめ、5月末に展開する。",
            tags=["AI活用", "ドキュメント"], proj_id=soumu_id, section_id=sec["proj"],
        )
        await task(
            "写真・動画の撮影、利用に関する留意事項について",
            "miyu-umemoto", "not_started", "medium", 8,
            desc="社内撮影ルールの周知資料を作成して展開する。",
            proj_id=soumu_id, section_id=sec["proj"],
        )
        await task(
            "オフィス備品発注（ホワイトボード）",
            "tabito-shibata", "not_started", "low", 7,
            proj_id=soumu_id, section_id=sec["proj"],
        )

        # ─── 総務: 負荷アラート検証用（今日締め・過負荷）────────
        # tomoyo-ishikawa に今日締めタスクを集中させて F-14 の超過バッジを確認
        task_ids["overload1"] = await task(
            "月末経費精算取りまとめ",
            "tomoyo-ishikawa", "in_progress", "urgent", 0,
            desc="部門全員の経費申請を集約してシステムへ入力する。",
            tags=["経理連携"], proj_id=soumu_id, section_id=sec["proj"],
        )
        task_ids["overload2"] = await task(
            "社員名簿更新",
            "tomoyo-ishikawa", "not_started", "high", 0,
            desc="5月入退社分の社員名簿を更新し共有フォルダへ格納する。",
            proj_id=soumu_id, section_id=sec["proj"],
        )
        task_ids["overload3"] = await task(
            "勤怠締め確認メール送信",
            "tomoyo-ishikawa", "not_started", "high", 0,
            desc="月末勤怠入力を未提出の社員へリマインドメールを送付する。",
            proj_id=soumu_id, section_id=sec["proj"],
        )

        # ─── 人事: 勤怠管理 ─────────────────────────────────
        await task(
            "勤怠制度の見直し",
            "takuya-suzuki", "in_progress", "high", -110,  # 過去（期限超過）
            desc="フレックスタイム制度の範囲拡大に伴い勤怠ルールを更新する。",
            tags=["制度改定"], proj_id=jinji_id, section_id=sec["kintai"],
        )
        await task(
            "PC利用ログの提出",
            "takuya-suzuki", "completed", "medium", -1,
            proj_id=jinji_id, section_id=sec["kintai"],
        )
        await task(
            "PCログが取れていない人に人事個別連絡",
            "takuya-suzuki", "in_progress", "medium", 10,
            desc="PCログ未取得者リストを確認し個別に連絡する。",
            proj_id=jinji_id, section_id=sec["kintai"],
        )
        await task(
            "80時間超え者への通知",
            "toshio-yorita", "completed", "high", -11,
            desc="月次の残業80時間超え者に産業医面談の案内を送付する。",
            proj_id=jinji_id, section_id=sec["kintai"],
        )
        await task(
            "翌月残業見込みアラートレポート作成",
            "toshio-yorita", "not_started", "medium", 6,
            proj_id=jinji_id, section_id=sec["kintai"],
        )

        # ─── 人事: キャリア・資格管理 ────────────────────────
        await task(
            "キャリアレベル認定：2026年度",
            "takuya-suzuki", "not_started", "medium", 330,
            proj_id=jinji_id, section_id=sec["career"],
        )
        await task(
            "ファミリーサポート支援",
            "takuya-suzuki", "completed", "low", -142,
            proj_id=jinji_id, section_id=sec["career"],
        )
        await task(
            "資格取得スタンプチェック",
            "toshio-yorita", "not_started", "low", 132,
            desc="2026年度上期の資格取得者を確認しシステムにポイントを付与する。",
            proj_id=jinji_id, section_id=sec["career"],
        )

        # ─── 人事: 保険料率等変更 ────────────────────────────
        await task(
            "令和8年度　健康保険料/協会けんぽ",
            "takuya-suzuki", "not_started", "high", 8,
            desc="協会けんぽ保険料率改定対応。システム変更・社内通知・給与確認を実施する。",
            tags=["保険料"], proj_id=jinji_id, section_id=sec["insurance"],
        )
        await task(
            "令和8年度　子ども・子育て支援金",
            "toshio-yorita", "not_started", "medium", 8,
            tags=["保険料"], proj_id=jinji_id, section_id=sec["insurance"],
        )
        await task(
            "令和8年度　雇用保険料",
            "takuya-suzuki", "completed", "high", -21,
            tags=["保険料"], proj_id=jinji_id, section_id=sec["insurance"],
        )

        # ─── 人事: 採用（ガントチャート依存関係検証用）─────────
        task_ids["recruit1"] = await task(
            "採用要件定義",
            "hanako-yamada", "in_progress", "high", 7, start_days=0,
            desc="採用ポジションの要件（スキル・経験・年収）を確定する。",
            tags=["採用"], proj_id=jinji_id, section_id=sec["recruit"],
        )
        task_ids["recruit2"] = await task(
            "求人票作成",
            "hanako-yamada", "not_started", "high", 14, start_days=7,
            desc="採用要件定義完了後に求人票を作成し媒体へ掲載する。",
            tags=["採用"], proj_id=jinji_id, section_id=sec["recruit"],
        )
        task_ids["recruit3"] = await task(
            "候補者選考・書類審査",
            "ichiro-tanaka", "not_started", "medium", 28, start_days=14,
            desc="応募書類の審査と一次選考を実施する。",
            tags=["採用"], proj_id=jinji_id, section_id=sec["recruit"],
        )
        task_ids["recruit4"] = await task(
            "最終面接調整",
            "takuya-suzuki", "not_started", "high", 35, start_days=28,
            desc="最終面接の日程調整と面接官への事前案内を行う。",
            tags=["採用"], proj_id=jinji_id, section_id=sec["recruit"],
        )

        # ─── F-07 visibility=private タスク（個人メモ）─────────
        await task(
            "自己評価フォーム作成（個人メモ）",
            "toshio-yorita", "not_started", "low", 9,
            desc="上期振り返りの自己評価。自分だけに見えるタスク。",
            visibility="private", proj_id=jinji_id, section_id=sec["career"],
        )
        await task(
            "山田さんへのフィードバックメモ整理",
            "ichiro-tanaka", "not_started", "low", 5,
            desc="1on1 前に整理しておく。プライベートタスク。",
            visibility="private",
        )

        # 5. 工数登録（overload テスト: tomoyo-ishikawa 今日分合計 9h → 超過）
        print("\n=== 5. 工数登録（F-14 負荷アラート検証用）===")
        wh_map = {
            task_ids.get("overload1"): 4.0,
            task_ids.get("overload2"): 3.0,
            task_ids.get("overload3"): 2.0,
        }
        for tid, hours in wh_map.items():
            if not tid:
                continue
            r = await post(
                client, f"/tasks/{tid}/work-hours",
                {"estimated_hours": hours, "actual_hours": None, "notes": "seed data"},
                header=user_header("tomoyo-ishikawa"),
            )
            if r:
                print(f"  OK {hours}h 登録 → task {tid[:8]}...")

        # 6. 依存関係登録（ガントチャート検証用）
        print("\n=== 6. 依存関係登録（ガント検証用）===")
        dep_chain = [
            (task_ids.get("recruit2"), task_ids.get("recruit1")),
            (task_ids.get("recruit3"), task_ids.get("recruit2")),
            (task_ids.get("recruit4"), task_ids.get("recruit3")),
        ]
        for task_id, depends_on in dep_chain:
            if not task_id or not depends_on:
                continue
            r = await post(
                client, f"/tasks/{task_id}/dependencies",
                {"depends_on_task_id": depends_on},
            )
            if r:
                print(f"  OK {task_id[:8]}... → depends on {depends_on[:8]}...")

        print("\n=== 完了 ===")
        print(f"  総務チーム 3名 / 人事チーム 4名")
        print(f"  総務プロジェクト: {soumu_id}")
        print(f"  人事プロジェクト: {jinji_id}")
        print()
        print("【検証ポイント】")
        print("  F-14 負荷アラート : 石川 智代（今日締め 9h > 8h）でバッジが表示されることを確認")
        print("  期限超過          : 勤怠制度の見直し（取鈴木 拓哉、約110日超過）")
        print("  F-04 重複警告     : 「社内報作成（6月号）」作成時に「社内報作成（5月号）」が候補表示")
        print("  F-07 プライベート : 寄田・田中の private タスクは本人のみ閲覧可")
        print("  ガントチャート    : 採用タスク4件に依存関係あり（採用要件定義→求人票→選考→面接）")
        print("  カレンダー        : 今後35日間にタスクが分散配置")
        print("  ワークロード      : 人事チームと総務チームの部署別集計を確認")

if __name__ == "__main__":
    asyncio.run(main())
