from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok():
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_openapi_is_exposed():
    r = client.get("/api/v1/openapi.json")
    assert r.status_code == 200
    assert r.json()["info"]["title"] == "Portale Conti Economici"
