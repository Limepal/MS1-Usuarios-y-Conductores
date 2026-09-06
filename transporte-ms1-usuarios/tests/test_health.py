"""Health check: GET /ms1/health -> 200 {"status":"ok","servicio":"ms1"}."""


def test_health_ok(client):
    respuesta = client.get("/ms1/health")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"status": "ok", "servicio": "ms1"}


def test_swagger_expuesto(client):
    respuesta = client.get("/ms1/docs")
    assert respuesta.status_code == 200
    assert "swagger" in respuesta.text.lower()
