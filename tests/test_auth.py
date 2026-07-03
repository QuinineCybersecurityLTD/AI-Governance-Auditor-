import pytest
from fastapi.testclient import TestClient

from aigov.api import app
from aigov.auth import rate_limiter

RECORD = {"name": "AuthTest"}


@pytest.fixture()
def client():
    rate_limiter.reset()
    return TestClient(app)


def test_open_mode_when_no_keys_configured(client, monkeypatch):
    monkeypatch.delenv("AIGOV_API_KEYS", raising=False)
    assert client.post("/v1/classify", json=RECORD).status_code == 200


def test_missing_key_is_401(client, monkeypatch):
    monkeypatch.setenv("AIGOV_API_KEYS", "sk-good-key")
    assert client.post("/v1/classify", json=RECORD).status_code == 401


def test_wrong_key_is_403(client, monkeypatch):
    monkeypatch.setenv("AIGOV_API_KEYS", "sk-good-key")
    r = client.post("/v1/classify", json=RECORD, headers={"X-API-Key": "sk-wrong"})
    assert r.status_code == 403


def test_valid_key_passes(client, monkeypatch):
    monkeypatch.setenv("AIGOV_API_KEYS", "sk-good-key, sk-second-key")
    for key in ("sk-good-key", "sk-second-key"):
        r = client.post("/v1/classify", json=RECORD, headers={"X-API-Key": key})
        assert r.status_code == 200


def test_health_stays_open_with_keys_configured(client, monkeypatch):
    monkeypatch.setenv("AIGOV_API_KEYS", "sk-good-key")
    assert client.get("/health").status_code == 200


def test_rate_limit_429_and_per_key_isolation(client, monkeypatch):
    monkeypatch.setenv("AIGOV_API_KEYS", "sk-a,sk-b")
    monkeypatch.setenv("AIGOV_RATE_LIMIT", "3")
    for _ in range(3):
        assert client.post("/v1/classify", json=RECORD,
                           headers={"X-API-Key": "sk-a"}).status_code == 200
    over = client.post("/v1/classify", json=RECORD, headers={"X-API-Key": "sk-a"})
    assert over.status_code == 429
    assert over.headers["Retry-After"] == "60"
    # a different key has its own window
    assert client.post("/v1/classify", json=RECORD,
                       headers={"X-API-Key": "sk-b"}).status_code == 200
