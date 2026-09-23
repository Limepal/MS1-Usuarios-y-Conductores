"""Tests de conductores: consultas (contrato con MS2/MS4) + lógica de negocio.

El rating de MS3 se simula con monkeypatch sobre app.clientes.
"""
from datetime import date

import pytest

from app import clientes
from app.models import Conductor, Vehiculo
from app.reglas import Rating

ANIO = date.today().year


@pytest.fixture()
def ratings(monkeypatch):
    """Diccionario conductor_id -> Rating | None que hace de MS3."""
    tabla: dict = {}
    monkeypatch.setattr(
        clientes, "rating_de_conductor",
        lambda cid, http=None: tabla.get(cid, Rating(None, 0)),
    )
    monkeypatch.setattr(
        clientes, "ratings_de_conductores",
        lambda ids: {i: tabla.get(i, Rating(None, 0)) for i in ids},
    )
    return tabla


def _conductor(db, n=1, vehiculos=({},), **kw):
    c = Conductor(
        nombre="Carlos", apellido="Torres", email=f"c{n}@correo.pe",
        telefono="988777666", nro_licencia=f"L-{n:05d}", distrito_base="Surco",
        fecha_ingreso=date(2021, 1, 15), **kw,
    )
    db.add(c)
    db.flush()
    for i, v in enumerate(vehiculos):
        db.add(Vehiculo(**{
            "conductor_id": c.id, "placa": f"A{n:02d}-{i:03d}", "marca": "Toyota",
            "modelo": "Corolla", "anio": ANIO - 2, "capacidad": 4,
            "tipo_servicio": "estandar", **v,
        }))
    db.commit()
    db.refresh(c)
    return c


# --- contrato de consultas ---------------------------------------------------
def test_conductor_con_vehiculos_embebidos(client, db_session):
    c = _conductor(db_session)
    cuerpo = client.get(f"/ms1/conductores/{c.id}").json()
    assert cuerpo["nro_licencia"] == "L-00001"
    assert len(cuerpo["vehiculos"]) == 1


def test_vehiculos_devuelve_lista(client, db_session):
    # MS4 depende de que sea una LISTA y no {items: [...]}.
    c = _conductor(db_session)
    cuerpo = client.get(f"/ms1/conductores/{c.id}/vehiculos").json()
    assert isinstance(cuerpo, list) and len(cuerpo) == 1


def test_conductor_inexistente_404(client):
    assert client.get("/ms1/conductores/9999").status_code == 404


def test_listado_conductores_paginado(client, db_session):
    _conductor(db_session, 1, distrito_base="Surco")
    _conductor(db_session, 2, distrito_base="Lima")
    cuerpo = client.get("/ms1/conductores?distrito_base=Surco").json()
    assert (cuerpo["total"], cuerpo["page"], cuerpo["limit"]) == (1, 1, 20)


def test_ya_no_se_crean_conductores(client, db_session):
    c = _conductor(db_session)
    assert client.post("/ms1/conductores", json={}).status_code == 405
    assert client.delete(f"/ms1/conductores/{c.id}").status_code == 405


# --- lógica de negocio -------------------------------------------------------
def test_elegibilidad_con_rating_de_ms3(client, db_session, ratings):
    c = _conductor(db_session)
    ratings[c.id] = Rating(4.8, 30)
    cuerpo = client.get(f"/ms1/conductores/{c.id}/elegibilidad").json()
    assert cuerpo["elegible"] is True
    assert "confort" in cuerpo["servicios_habilitados"]
    assert cuerpo["rating_promedio"] == 4.8
    assert cuerpo["advertencias"] == []


def test_elegibilidad_rating_bajo(client, db_session, ratings):
    c = _conductor(db_session)
    ratings[c.id] = Rating(2.9, 30)
    cuerpo = client.get(f"/ms1/conductores/{c.id}/elegibilidad").json()
    assert cuerpo["elegible"] is False


def test_elegibilidad_ms3_caido_no_da_500(client, db_session, ratings):
    c = _conductor(db_session)
    ratings[c.id] = None
    respuesta = client.get(f"/ms1/conductores/{c.id}/elegibilidad")
    assert respuesta.status_code == 200
    assert respuesta.json()["advertencias"]


def test_categoria(client, db_session, ratings):
    c = _conductor(db_session, fecha_ingreso=date(2018, 1, 1))
    ratings[c.id] = Rating(4.9, 100)
    cuerpo = client.get(f"/ms1/conductores/{c.id}/categoria").json()
    assert cuerpo["nivel"] == "elite"
    assert cuerpo["comision_plataforma"] == 0.10


def test_suspender_y_activar(client, db_session, ratings):
    c = _conductor(db_session)
    assert client.post(f"/ms1/conductores/{c.id}/suspender").json()["activo"] is False
    assert client.post(f"/ms1/conductores/{c.id}/suspender").status_code == 409
    assert client.post(f"/ms1/conductores/{c.id}/activar").json()["activo"] is True
    assert client.post(f"/ms1/conductores/{c.id}/activar").status_code == 409


def test_no_se_activa_sin_vehiculo_apto(client, db_session):
    c = _conductor(db_session, vehiculos=({"anio": ANIO - 20},), activo=False)
    assert client.post(f"/ms1/conductores/{c.id}/activar").status_code == 409


def test_disponibles_filtra_y_ordena(client, db_session, ratings):
    bueno = _conductor(db_session, 1, vehiculos=({"capacidad": 7},))
    regular = _conductor(db_session, 2, vehiculos=({"capacidad": 7},))
    malo = _conductor(db_session, 3, vehiculos=({"capacidad": 7},))
    _conductor(db_session, 4, vehiculos=({"capacidad": 7},), activo=False)
    _conductor(db_session, 5)  # capacidad 4: no sirve para xl
    ratings.update({bueno.id: Rating(4.9, 50), regular.id: Rating(4.1, 50), malo.id: Rating(3.0, 50)})

    cuerpo = client.get("/ms1/conductores/disponibles?tipo_servicio=xl").json()
    assert [x["conductor_id"] for x in cuerpo["items"]] == [bueno.id, regular.id]
    assert cuerpo["evaluados"] == 3


def test_disponibles_tipo_invalido(client):
    assert client.get("/ms1/conductores/disponibles?tipo_servicio=premium").status_code == 400


def test_validar_vehiculo(client):
    ok = {"placa": "ABC-123", "marca": "Kia", "modelo": "Rio", "anio": ANIO - 1,
          "tipo_servicio": "confort"}
    assert client.post("/ms1/vehiculos/validar", json=ok).json()["valido"] is True
    malo = {**ok, "placa": "123", "tipo_servicio": "xl"}
    cuerpo = client.post("/ms1/vehiculos/validar", json=malo).json()
    assert cuerpo["valido"] is False and cuerpo["problemas"]
