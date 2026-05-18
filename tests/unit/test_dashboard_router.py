from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import TokenPayload, get_current_user
from src.api.routers.dashboard import router

app = FastAPI()
app.include_router(router)
_user = TokenPayload(sub="user-1", name="Test", email="t@t.com", roles=["member"], tid="tid")
app.dependency_overrides[get_current_user] = lambda: _user


def test_dashboard_routes_registered() -> None:
    routes = [r.path for r in app.routes]
    assert any("summary" in r for r in routes)
    assert any("workload" in r for r in routes)
    assert any("today" in r for r in routes)
    assert any("overdue" in r for r in routes)


def test_summary_endpoint_exists() -> None:
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/api/v1/dashboard/summary")
    assert resp.status_code != 404
