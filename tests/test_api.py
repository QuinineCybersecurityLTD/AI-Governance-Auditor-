from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aigov.api import app

EXAMPLE = Path(__file__).parent.parent / "examples" / "resume_screener.yaml"


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def record_json():
    # round-trip through the model so dates become JSON-safe strings,
    # exactly as a real API client would send them
    from aigov.record import SystemRecord
    return SystemRecord.from_yaml(EXAMPLE).model_dump(mode="json")


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["articles_covered"] == ["10", "11", "13", "14", "15", "9"]


def test_classify_endpoint(client, record_json):
    r = client.post("/v1/classify", json=record_json)
    assert r.status_code == 200
    assert r.json()["tier"] == "high_risk_annex_iii"


def test_audit_endpoint_with_report(client, record_json):
    r = client.post("/v1/audit?assessment_date=2026-07-03&include_report=true",
                    json=record_json)
    assert r.status_code == 200
    body = r.json()
    assert len(body["result"]["findings"]) == 32
    assert "Prioritized gap list" in body["report_markdown"]


def test_bom_endpoint_returns_validated_boms(client, record_json):
    r = client.post("/v1/bom", json=record_json)
    assert r.status_code == 200
    body = r.json()
    assert body["spdx"]["@context"] == "https://spdx.org/rdf/3.0.1/spdx-context.jsonld"
    assert body["cyclonedx"]["specVersion"] == "1.7"
    assert body["spdx_validation_errors"] == []
    assert any(g["field"] == "provenance" for g in body["manual_input_required"])


def test_invalid_record_is_422(client):
    r = client.post("/v1/audit", json={"description": "no name field"})
    assert r.status_code == 422


def test_crosswalk_and_timeline(client):
    xw = client.get("/v1/crosswalk").json()
    assert len(xw["articles"]) == 6
    tl = client.get("/v1/timeline").json()
    assert tl["regimes"]["high_risk_annex_iii"]["applies_from"] == "2027-12-02"
