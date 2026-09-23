"""Tests unitarios de las reglas de negocio (sin BD ni HTTP)."""
from datetime import date
from types import SimpleNamespace

from app import reglas
from app.reglas import Rating

HOY = date(2026, 9, 22)
SIN_RESENAS = Rating(promedio=None, total=0)


def _vehiculo(**kw):
    base = {"placa": "ABC-123", "anio": 2022, "capacidad": 4, "tipo_servicio": "estandar"}
    return SimpleNamespace(**{**base, **kw})


# --- pasajeros --------------------------------------------------------------
def test_pasajero_valido():
    r = reglas.validar_pasajero(True, date(1995, 4, 10), "999111222", HOY)
    assert r == {"puede_solicitar_viaje": True, "edad": 31, "motivos": []}


def test_pasajero_menor_suspendido_sin_telefono():
    r = reglas.validar_pasajero(False, date(2010, 1, 1), None, HOY)
    assert r["puede_solicitar_viaje"] is False
    assert len(r["motivos"]) == 3


def test_edad_cumple_el_dia_exacto():
    assert reglas.anios_cumplidos(date(2008, 9, 22), HOY) == 18
    assert reglas.anios_cumplidos(date(2008, 9, 23), HOY) == 17


# --- vehículos --------------------------------------------------------------
def test_servicios_por_antiguedad_y_capacidad():
    assert reglas.servicios_del_vehiculo(_vehiculo(anio=2024), HOY) == [
        "economico", "estandar", "confort"
    ]
    assert reglas.servicios_del_vehiculo(_vehiculo(anio=2024, capacidad=7), HOY) == [
        "economico", "estandar", "confort", "xl"
    ]
    assert reglas.servicios_del_vehiculo(_vehiculo(anio=2012), HOY) == ["economico"]


def test_vehiculo_muy_viejo_o_placa_invalida():
    assert reglas.servicios_del_vehiculo(_vehiculo(anio=2005), HOY) == []
    assert reglas.validar_vehiculo(_vehiculo(placa="AB123"), HOY)["valido"] is False


def test_xl_requiere_capacidad():
    r = reglas.validar_vehiculo(_vehiculo(tipo_servicio="xl", capacidad=4), HOY)
    assert r["valido"] is False
    assert "xl" not in r["servicios_habilitados"]


# --- conductores ------------------------------------------------------------
def test_conductor_elegible_sin_historial():
    r = reglas.evaluar_conductor(True, [_vehiculo(anio=2024)], SIN_RESENAS, HOY)
    assert r["elegible"] is True
    assert r["servicios_habilitados"] == ["confort", "economico", "estandar"]


def test_rating_bajo_bloquea_con_resenas_suficientes():
    r = reglas.evaluar_conductor(True, [_vehiculo()], Rating(3.0, 10), HOY)
    assert r["elegible"] is False
    assert any("rating" in m for m in r["motivos"])


def test_rating_bajo_ignorado_con_pocas_resenas():
    assert reglas.evaluar_conductor(True, [_vehiculo()], Rating(2.0, 3), HOY)["elegible"]


def test_rating_filtra_servicios_premium():
    r = reglas.evaluar_conductor(True, [_vehiculo(anio=2024)], Rating(4.2, 20), HOY)
    assert r["servicios_habilitados"] == ["economico", "estandar"]


def test_conductor_suspendido_o_sin_vehiculos():
    r = reglas.evaluar_conductor(False, [], SIN_RESENAS, HOY)
    assert r["elegible"] is False
    assert r["servicios_habilitados"] == []
    assert len(r["motivos"]) == 2


def test_categorias():
    assert reglas.categoria_conductor(date(2026, 3, 1), SIN_RESENAS, HOY)["nivel"] == "nuevo"
    assert reglas.categoria_conductor(date(2024, 1, 1), SIN_RESENAS, HOY)["nivel"] == "regular"
    assert reglas.categoria_conductor(date(2022, 1, 1), Rating(4.5, 50), HOY)["nivel"] == "senior"
    elite = reglas.categoria_conductor(date(2020, 1, 1), Rating(4.8, 50), HOY)
    assert elite == {"nivel": "elite", "antiguedad_anios": 6, "comision_plataforma": 0.10}


def test_puntaje_premia_rating_y_antiguedad():
    nuevo = reglas.puntaje_asignacion(date(2026, 1, 1), Rating(4.0, 10), HOY)
    veterano = reglas.puntaje_asignacion(date(2020, 1, 1), Rating(4.9, 10), HOY)
    assert veterano > nuevo
    assert veterano <= 100
