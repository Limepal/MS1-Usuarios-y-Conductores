"""Tests de conductores y vehículos (relación conductores -> vehiculos)."""
CONDUCTOR = {
    "nombre": "Carlos",
    "apellido": "Torres",
    "email": "carlos.torres@correo.pe",
    "telefono": "988777666",
    "nro_licencia": "L-10001",
    "distrito_base": "Surco",
    "fecha_ingreso": "2023-01-15",
    "calificacion_promedio": 4.5,
}

VEHICULO = {
    "placa": "ABC-123",
    "marca": "Toyota",
    "modelo": "Corolla",
    "anio": 2020,
    "color": "blanco",
    "capacidad": 4,
    "tipo_servicio": "confort",
}


def _crear_conductor(client, **overrides):
    return client.post("/ms1/conductores", json={**CONDUCTOR, **overrides})


def test_crear_conductor(client):
    respuesta = _crear_conductor(client)
    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["id"] > 0
    assert cuerpo["nro_licencia"] == "L-10001"
    assert cuerpo["activo"] is True


def test_conductor_inexistente_404(client):
    assert client.get("/ms1/conductores/9999").status_code == 404


def test_crear_conductor_y_vehiculo(client):
    conductor = _crear_conductor(client).json()
    respuesta = client.post(
        f"/ms1/conductores/{conductor['id']}/vehiculos", json=VEHICULO
    )
    assert respuesta.status_code == 201
    vehiculo = respuesta.json()
    assert vehiculo["conductor_id"] == conductor["id"]
    assert vehiculo["placa"] == "ABC-123"

    # El conductor devuelve su vehículo embebido
    detalle = client.get(f"/ms1/conductores/{conductor['id']}").json()
    assert len(detalle["vehiculos"]) == 1
    assert detalle["vehiculos"][0]["placa"] == "ABC-123"


def test_listar_vehiculos_de_conductor(client):
    conductor = _crear_conductor(client, email="c2@correo.pe", nro_licencia="L-10002").json()
    client.post(f"/ms1/conductores/{conductor['id']}/vehiculos", json=VEHICULO)
    respuesta = client.get(f"/ms1/conductores/{conductor['id']}/vehiculos")
    assert respuesta.status_code == 200
    assert len(respuesta.json()) == 1


def test_tipo_servicio_invalido_400(client):
    conductor = _crear_conductor(client).json()
    invalido = {**VEHICULO, "tipo_servicio": "premium"}
    respuesta = client.post(f"/ms1/conductores/{conductor['id']}/vehiculos", json=invalido)
    assert respuesta.status_code == 400


def test_placa_duplicada_409(client):
    conductor_a = _crear_conductor(client).json()
    conductor_b = _crear_conductor(client, email="c3@correo.pe", nro_licencia="L-10003").json()
    client.post(f"/ms1/conductores/{conductor_a['id']}/vehiculos", json=VEHICULO)
    respuesta = client.post(
        f"/ms1/conductores/{conductor_b['id']}/vehiculos", json=VEHICULO
    )
    assert respuesta.status_code == 409


def test_eliminar_conductor_cascada(client):
    conductor = _crear_conductor(client).json()
    client.post(f"/ms1/conductores/{conductor['id']}/vehiculos", json=VEHICULO)
    respuesta = client.delete(f"/ms1/conductores/{conductor['id']}")
    assert respuesta.status_code == 204
    # Vehículos eliminados en cascada
    assert client.get(f"/ms1/conductores/{conductor['id']}").status_code == 404


def test_listado_conductores_paginado(client):
    _crear_conductor(client, email="d1@correo.pe", nro_licencia="L-20001", distrito_base="Surco")
    _crear_conductor(client, email="d2@correo.pe", nro_licencia="L-20002", distrito_base="Lima")
    respuesta = client.get("/ms1/conductores?distrito_base=Surco")
    cuerpo = respuesta.json()
    assert cuerpo["total"] == 1
    assert cuerpo["page"] == 1
    assert cuerpo["limit"] == 20
    assert len(cuerpo["items"]) == 1
    assert cuerpo["items"][0]["distrito_base"] == "Surco"
