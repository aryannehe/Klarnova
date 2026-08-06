"""Health endpoint tests."""



def test_liveness(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_incidents_list_empty(client):
    resp = client.get("/api/v1/incidents")
    assert resp.status_code == 200
    assert resp.json() == []


def test_incident_not_found(client):
    resp = client.get("/api/v1/incidents/does-not-exist")
    assert resp.status_code == 404
