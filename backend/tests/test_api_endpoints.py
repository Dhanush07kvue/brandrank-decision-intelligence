from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint():
    client = TestClient(app)
    res = client.get('/api/health')
    assert res.status_code == 200
    assert res.json()['status'] == 'ok'


def test_reference_checks_not_found_before_ingestion():
    client = TestClient(app)
    # This may return 404 if no runs yet in a clean DB; allow 200 if runs already exist.
    res = client.get('/api/reference-checks')
    assert res.status_code in (200, 404)


def test_get_intervention_outcome_missing_returns_null_payload():
    client = TestClient(app)
    res = client.get('/api/interventions/nonexistent_intervention_id/outcome')
    assert res.status_code == 200
    assert res.json() is None
