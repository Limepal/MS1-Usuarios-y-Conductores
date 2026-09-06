"""Tests de usuarios."""
PAYLOAD = {
    "nombre": "Ana",
    "apellido": "Quispe",
    "email": "ana.quispe@correo.pe",
    "telefono": "999111222",
    "distrito": "Miraflores",
    "fecha_nacimiento": "1995-04-10",
}


def _crear_usuario(client, **overrides):
    payload = {**PAYLOAD, **overrides}
    return client.post("/ms1/usuarios", json=payload)


def test_crear_usuario(client):
    respuesta = _crear_usuario(client)
    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["id"] > 0
    assert cuerpo["nombre"] == "Ana"
    assert cuerpo["email"] == "ana.quispe@correo.pe"
    assert cuerpo["activo"] is True
    # fecha_registro en ISO 8601 UTC con Z
    assert "Z" in cuerpo["fecha_registro"]


def test_usuario_inexistente_404(client):
    respuesta = client.get("/ms1/usuarios/9999")
    assert respuesta.status_code == 404
    cuerpo = respuesta.json()
    assert "detalle" in cuerpo


def test_email_duplicado_409(client):
    _crear_usuario(client)
    respuesta = _crear_usuario(client, email="ana.quispe@correo.pe")
    assert respuesta.status_code == 409


def test_obtener_usuario(client):
    creado = _crear_usuario(client).json()
    respuesta = client.get(f"/ms1/usuarios/{creado['id']}")
    assert respuesta.status_code == 200
    assert respuesta.json()["email"] == creado["email"]


def test_actualizar_usuario_completo(client):
    creado = _crear_usuario(client).json()
    actualizado = {**PAYLOAD, "nombre": "Ana Lucia", "activo": False}
    respuesta = client.put(f"/ms1/usuarios/{creado['id']}", json=actualizado)
    assert respuesta.status_code == 200
    assert respuesta.json()["nombre"] == "Ana Lucia"
    assert respuesta.json()["activo"] is False


def test_eliminar_usuario(client):
    creado = _crear_usuario(client).json()
    respuesta = client.delete(f"/ms1/usuarios/{creado['id']}")
    assert respuesta.status_code == 204
    assert client.get(f"/ms1/usuarios/{creado['id']}").status_code == 404


def test_listado_paginado_con_filtro(client):
    _crear_usuario(client, email="a@correo.pe", distrito="Miraflores")
    _crear_usuario(client, email="b@correo.pe", distrito="Lince")
    _crear_usuario(client, email="c@correo.pe", distrito="Miraflores")

    respuesta = client.get("/ms1/usuarios?distrito=Miraflores")
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["total"] == 2
    assert cuerpo["page"] == 1
    assert cuerpo["limit"] == 20
    assert len(cuerpo["items"]) == 2

    respuesta = client.get("/ms1/usuarios?page=1&limit=2")
    assert respuesta.json()["limit"] == 2
    assert respuesta.json()["total"] == 3
