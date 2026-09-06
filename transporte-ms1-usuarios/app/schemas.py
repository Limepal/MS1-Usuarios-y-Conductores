"""Esquemas Pydantic de MS1.

Regla 8.1 del contrato: mismo nombre en la respuesta que en la tabla
(snake_case en español). Nunca camelCase.
Regla 3: fechas en ISO 8601 UTC con 'Z' (nunca epoch, nunca formato local).
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_serializer

# Enum de tipo_servicio válido (Contrato Cero v1.0 §4)
TIPOS_SERVICIO = {"economico", "estandar", "confort", "xl"}


def _formatear_utc_z(valor: datetime) -> str:
    """Convierte a UTC y lo formatea como ISO 8601 con sufijo 'Z'."""
    if valor.tzinfo is None:
        valor = valor.replace(tzinfo=timezone.utc)
    return valor.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Usuarios
# ---------------------------------------------------------------------------
class UsuarioBase(BaseModel):
    nombre: str = Field(max_length=60)
    apellido: str = Field(max_length=60)
    email: str = Field(max_length=120)
    telefono: str | None = None
    distrito: str | None = None
    fecha_nacimiento: date | None = None


class UsuarioCreate(UsuarioBase):
    pass


class UsuarioUpdate(BaseModel):
    # PUT = actualización completa; activo controla disponibilidad.
    nombre: str = Field(max_length=60)
    apellido: str = Field(max_length=60)
    email: str = Field(max_length=120)
    telefono: str | None = None
    distrito: str | None = None
    fecha_nacimiento: date | None = None
    activo: bool = True


class UsuarioOut(UsuarioBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fecha_registro: datetime
    activo: bool

    @field_serializer("fecha_registro")
    def _ser_fecha_registro(self, valor: datetime) -> str:
        return _formatear_utc_z(valor)


# ---------------------------------------------------------------------------
# Vehiculos
# ---------------------------------------------------------------------------
class VehiculoBase(BaseModel):
    placa: str = Field(max_length=10)
    marca: str = Field(max_length=40)
    modelo: str = Field(max_length=40)
    anio: int = Field(ge=1980, le=2100)
    color: str | None = None
    capacidad: int = Field(default=4, ge=1, le=20)
    tipo_servicio: str = Field(default="estandar", max_length=20)


class VehiculoCreate(VehiculoBase):
    pass


class VehiculoOut(VehiculoBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conductor_id: int


# ---------------------------------------------------------------------------
# Conductores
# ---------------------------------------------------------------------------
class ConductorBase(BaseModel):
    nombre: str = Field(max_length=60)
    apellido: str = Field(max_length=60)
    email: str = Field(max_length=120)
    telefono: str | None = None
    nro_licencia: str = Field(max_length=20)
    distrito_base: str | None = None
    fecha_ingreso: date
    calificacion_promedio: float | None = Field(default=0, ge=0, le=5)


class ConductorCreate(ConductorBase):
    pass


class ConductorUpdate(BaseModel):
    # PUT = actualización completa.
    nombre: str = Field(max_length=60)
    apellido: str = Field(max_length=60)
    email: str = Field(max_length=120)
    telefono: str | None = None
    nro_licencia: str = Field(max_length=20)
    distrito_base: str | None = None
    fecha_ingreso: date
    calificacion_promedio: float | None = Field(default=0, ge=0, le=5)
    activo: bool = True


class ConductorOut(ConductorBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    activo: bool


class ConductorConVehiculos(ConductorOut):
    """GET /ms1/conductores/{id} devuelve el conductor con su vehículo embebido."""

    vehiculos: list[VehiculoOut] = []
