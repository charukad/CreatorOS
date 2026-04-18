from apps.api.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_live_health() -> None:
    response = client.get("/api/health/live")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "api"


def test_ready_health_includes_dependencies() -> None:
    response = client.get("/api/health/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "database" in payload["dependencies"]
    assert "redis" in payload["dependencies"]

