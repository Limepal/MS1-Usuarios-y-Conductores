"""Reglas de negocio de MS1 (dominio puro).

Sin FastAPI ni SQLAlchemy: solo funciones que reciben datos y devuelven
decisiones con sus motivos. Así se prueban sin base de datos y los routers
quedan como una capa delgada (leer BD -> aplicar regla -> responder).

Ninguna regla requiere columnas nuevas: todo se deriva del esquema del
Contrato Cero (activo, fecha_nacimiento, fecha_ingreso, anio, capacidad...).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Iterable, Protocol

# ---------------------------------------------------------------------------
# Parámetros de negocio
# ---------------------------------------------------------------------------
EDAD_MINIMA_PASAJERO = 18
RATING_MINIMO = 3.5          # por debajo de esto el conductor no opera
MIN_RESENAS_PARA_RATING = 5  # con menos reseñas el rating aún no es representativo
ANTIGUEDAD_MAX_VEHICULO = 15 # años; ningún servicio acepta autos más viejos

# Placa peruana: 3 alfanuméricos, guion, 3 alfanuméricos (ABC-123, A1B-234).
PLACA_RE = re.compile(r"^[A-Z0-9]{3}-[A-Z0-9]{3}$")

# Requisitos por tipo de servicio. Un vehículo "sube" de categoría: un auto
# que califica para confort también puede hacer estandar/economico.
REQUISITOS_SERVICIO: dict[str, dict] = {
    "economico": {"antiguedad_max": 15, "capacidad_min": 4, "rating_min": 3.5},
    "estandar":  {"antiguedad_max": 12, "capacidad_min": 4, "rating_min": 4.0},
    "confort":   {"antiguedad_max": 6,  "capacidad_min": 4, "rating_min": 4.5},
    "xl":        {"antiguedad_max": 10, "capacidad_min": 6, "rating_min": 4.0},
}
TIPOS_SERVICIO = set(REQUISITOS_SERVICIO)

# Niveles del conductor: (nombre, años mínimos, rating mínimo, comisión plataforma)
# Se evalúan en orden; gana el primero que se cumple.
NIVELES = [
    ("elite",   5, 4.7, 0.10),
    ("senior",  3, 4.3, 0.15),
    ("regular", 1, 0.0, 0.20),
    ("nuevo",   0, 0.0, 0.25),
]


class VehiculoLike(Protocol):
    placa: str
    anio: int
    capacidad: int
    tipo_servicio: str


@dataclass
class Rating:
    """Rating del conductor tal como lo reporta MS3 (o None si no se pudo leer)."""

    promedio: float | None
    total: int = 0

    @property
    def representativo(self) -> bool:
        return self.promedio is not None and self.total >= MIN_RESENAS_PARA_RATING


# ---------------------------------------------------------------------------
# Utilidades de fechas
# ---------------------------------------------------------------------------
def anios_cumplidos(desde: date, hoy: date) -> int:
    """Años completos entre dos fechas (edad o antigüedad)."""
    return hoy.year - desde.year - ((hoy.month, hoy.day) < (desde.month, desde.day))


# ---------------------------------------------------------------------------
# Pasajeros
# ---------------------------------------------------------------------------
def validar_pasajero(
    activo: bool, fecha_nacimiento: date | None, telefono: str | None, hoy: date
) -> dict:
    """¿Puede este usuario solicitar un viaje? Devuelve decisión + motivos."""
    motivos: list[str] = []
    edad = anios_cumplidos(fecha_nacimiento, hoy) if fecha_nacimiento else None

    if not activo:
        motivos.append("usuario suspendido")
    if edad is None:
        motivos.append("sin fecha de nacimiento registrada")
    elif edad < EDAD_MINIMA_PASAJERO:
        motivos.append(f"menor de edad ({edad} años, mínimo {EDAD_MINIMA_PASAJERO})")
    if not telefono:
        motivos.append("sin teléfono de contacto")

    return {"puede_solicitar_viaje": not motivos, "edad": edad, "motivos": motivos}


# ---------------------------------------------------------------------------
# Vehículos
# ---------------------------------------------------------------------------
def problemas_vehiculo(v: VehiculoLike, hoy: date) -> list[str]:
    """Problemas que impiden que el vehículo opere en cualquier servicio."""
    problemas: list[str] = []
    if not PLACA_RE.match(v.placa or ""):
        problemas.append(f"placa '{v.placa}' con formato inválido (esperado ABC-123)")
    if v.anio > hoy.year + 1:
        problemas.append(f"año {v.anio} en el futuro")
    elif hoy.year - v.anio > ANTIGUEDAD_MAX_VEHICULO:
        problemas.append(
            f"vehículo de {hoy.year - v.anio} años (máximo {ANTIGUEDAD_MAX_VEHICULO})"
        )
    if v.tipo_servicio not in TIPOS_SERVICIO:
        problemas.append(f"tipo_servicio '{v.tipo_servicio}' no existe")
    return problemas


def servicios_del_vehiculo(v: VehiculoLike, hoy: date) -> list[str]:
    """Servicios para los que el vehículo cumple antigüedad y capacidad."""
    if problemas_vehiculo(v, hoy):
        return []
    antiguedad = hoy.year - v.anio
    return [
        s for s, req in REQUISITOS_SERVICIO.items()
        if antiguedad <= req["antiguedad_max"] and v.capacidad >= req["capacidad_min"]
    ]


def validar_vehiculo(v: VehiculoLike, hoy: date) -> dict:
    """Valida un vehículo (sin guardarlo) y explica qué servicios puede hacer."""
    problemas = problemas_vehiculo(v, hoy)
    servicios = servicios_del_vehiculo(v, hoy)
    if not problemas and v.tipo_servicio not in servicios:
        problemas.append(
            f"no cumple requisitos de '{v.tipo_servicio}' "
            f"(habilitado para: {', '.join(servicios) or 'ninguno'})"
        )
    return {
        "valido": not problemas,
        "antiguedad_anios": hoy.year - v.anio,
        "servicios_habilitados": servicios,
        "problemas": problemas,
    }


# ---------------------------------------------------------------------------
# Conductores
# ---------------------------------------------------------------------------
def _rating_cumple(rating: Rating, minimo: float) -> bool:
    # Sin historial suficiente se le da el beneficio de la duda al conductor.
    return not rating.representativo or rating.promedio >= minimo


def evaluar_conductor(
    activo: bool, vehiculos: Iterable[VehiculoLike], rating: Rating, hoy: date
) -> dict:
    """Elegibilidad general del conductor + servicios que puede ofrecer."""
    vehiculos = list(vehiculos)
    motivos: list[str] = []

    if not activo:
        motivos.append("conductor suspendido")
    if not vehiculos:
        motivos.append("sin vehículos registrados")

    servicios_vehiculos = {s for v in vehiculos for s in servicios_del_vehiculo(v, hoy)}
    if vehiculos and not servicios_vehiculos:
        motivos.append("ningún vehículo cumple los requisitos mínimos")

    if not _rating_cumple(rating, RATING_MINIMO):
        motivos.append(f"rating {rating.promedio} por debajo del mínimo {RATING_MINIMO}")

    servicios = [] if motivos else sorted(
        s for s in servicios_vehiculos
        if _rating_cumple(rating, REQUISITOS_SERVICIO[s]["rating_min"])
    )
    return {"elegible": not motivos, "servicios_habilitados": servicios, "motivos": motivos}


def categoria_conductor(fecha_ingreso: date, rating: Rating, hoy: date) -> dict:
    """Nivel del conductor por antigüedad + rating, y la comisión que le toca."""
    antiguedad = anios_cumplidos(fecha_ingreso, hoy)
    promedio = rating.promedio if rating.representativo else 0.0
    for nombre, anios_min, rating_min, comision in NIVELES:
        if antiguedad >= anios_min and promedio >= rating_min:
            return {
                "nivel": nombre,
                "antiguedad_anios": antiguedad,
                "comision_plataforma": comision,
            }
    raise AssertionError("NIVELES debe terminar en un nivel sin requisitos")


def puntaje_asignacion(fecha_ingreso: date, rating: Rating, hoy: date) -> float:
    """Puntaje para ordenar conductores disponibles (mayor = mejor).

    80% rating (sobre 5; sin historial se asume 4.0 neutral) + 20% antigüedad
    (saturada a 5 años). Rango 0..100.
    """
    promedio = rating.promedio if rating.representativo else 4.0
    antiguedad = min(anios_cumplidos(fecha_ingreso, hoy), 5)
    return round(80 * promedio / 5 + 20 * antiguedad / 5, 2)
