"""Tests de usuarios: consultas (contrato con MS2/MS4/frontend) + lógica."""
from datetime import date

from app.models import Usuario


def _usuario(db, **kw):
    datos = {
        "nombre": "Ana",
        "apellido": "Quispe",
        "email": "ana.quispe@correo.pe",
        "telefono": "999111222",
        "distrito": "Miraflores",
        "fecha_nacimiento": date(1995, 4, 10),
        **kw,
    }
    u = Usuario(**datos)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def test_obtener_usuario(client, db_session):
    u = _usuario(db_session)
    cuerpo = client.get(f"/ms1/usuarios/{u.id}").json()
    assert cuerpo["nombre"] == "Ana"
    assert cuerpo["activo"] is True
    assert cuerpo["fecha_registro"].endswith("Z")


def test_usuario_inexistente_404(client):
    respuesta = client.get("/ms1/usuarios/9999")
    assert respuesta.status_code == 404
    assert respuesta.json()["error"] == "no existe"


def test_listado_paginado_con_filtro(client, db_session):
    _usuario(db_session, email="a@x.pe", distrito="Surco")
    _usuario(db_session, email="b@x.pe", distrito="Lima")
    cuerpo = client.get("/ms1/usuarios?distrito=Surco").json()
    assert (cuerpo["total"], cuerpo["page"], cuerpo["limit"]) == (1, 1, 20)
    assert cuerpo["items"][0]["distrito"] == "Surco"


def test_ya_no_se_crean_usuarios(client):
    assert client.post("/ms1/usuarios", json={}).status_code == 405


def test_validacion_usuario_ok(client, db_session):
    u = _usuario(db_session)
    cuerpo = client.get(f"/ms1/usuarios/{u.id}/validacion").json()
    assert cuerpo["puede_solicitar_viaje"] is True
    assert cuerpo["motivos"] == []


def test_validacion_usuario_menor(client, db_session):
    u = _usuario(db_session, fecha_nacimiento=date.today().replace(year=date.today().year - 15))
    cuerpo = client.get(f"/ms1/usuarios/{u.id}/validacion").json()
    assert cuerpo["puede_solicitar_viaje"] is False
    assert cuerpo["edad"] == 15


def test_suspender_y_reactivar(client, db_session):
    u = _usuario(db_session)
    assert client.post(f"/ms1/usuarios/{u.id}/suspender").json()["activo"] is False
    assert client.post(f"/ms1/usuarios/{u.id}/suspender").status_code == 409
    validacion = client.get(f"/ms1/usuarios/{u.id}/validacion").json()
    assert "usuario suspendido" in validacion["motivos"]
    assert client.post(f"/ms1/usuarios/{u.id}/reactivar").json()["activo"] is True
    assert client.post(f"/ms1/usuarios/{u.id}/reactivar").status_code == 409
