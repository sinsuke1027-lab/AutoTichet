import pytest
from widget.clients.backend_client import UserInfo, ProjectInfo


def test_build_payload_basic():
    from widget.payload_builder import build_payload
    users = [UserInfo("u1", "山田 太郎"), UserInfo("u2", "田中 花子")]
    projects = [ProjectInfo("p1", "総務業務管理")]
    result = build_payload(
        title="報告書を書く",
        due_date_str="2026-06-10",
        assignee_display="山田 太郎",
        project_name="総務業務管理",
        priority_jp="高",
        users=users,
        projects=projects,
    )
    assert result["title"] == "報告書を書く"
    assert result["due_date"] == "2026-06-10"
    assert result["assignee_id"] == "u1"
    assert result["project_id"] == "p1"
    assert result["priority"] == "high"
    assert result["source_type"] == "manual"


def test_build_payload_no_assignee_no_project():
    from widget.payload_builder import build_payload
    result = build_payload(
        title="タスクA",
        due_date_str="",
        assignee_display="（なし）",
        project_name="（なし）",
        priority_jp="中",
        users=[],
        projects=[],
    )
    assert result["assignee_id"] is None
    assert result["project_id"] is None
    assert result["due_date"] is None
    assert result["priority"] == "medium"


def test_resolve_assignee_case_insensitive_partial_match():
    from widget.payload_builder import resolve_assignee
    users = [UserInfo("u1", "Tanaka Hanako"), UserInfo("u2", "Yamada Taro")]
    assert resolve_assignee("tanaka", users) == "u1"
    assert resolve_assignee("YAMADA", users) == "u2"
    assert resolve_assignee("存在しない", users) is None


def test_priority_map_all_values():
    from widget.payload_builder import jp_to_priority
    assert jp_to_priority("低") == "low"
    assert jp_to_priority("中") == "medium"
    assert jp_to_priority("高") == "high"
    assert jp_to_priority("緊急") == "urgent"
    assert jp_to_priority("不明") == "medium"
