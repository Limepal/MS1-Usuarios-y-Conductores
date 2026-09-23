"""Esquemas Pydantic de MS1.

Regla 8.1 del contrato: mismo nombre en la respuesta que en la tabla
(snake_case en español). Nunca camelCase.
Regla 3: fechas en ISO 8601 UTC con 'Z' (nunca epoch, nunca formato local).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer

# Enum de tipo_servicio válido (Contrato Cero v1.0 §4); definido en reglas.
from .reglas import TIPOS_SERVICIO  # noqa: E402,F401


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



class ConductorOut(ConductorBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    activo: bool


class ConductorConVehiculos(ConductorOut):
    """GET /ms1/conductores/{id} devuelve el conductor con su vehículo embebido."""

    vehiculos: list[VehiculoOut] = []


# ---------------------------------------------------------------------------
# Respuestas comunes (documentan Swagger; la forma es la del Contrato Cero)
# ---------------------------------------------------------------------------
def _ejemplo(**datos) -> ConfigDict:
    return ConfigDict(json_schema_extra={"examples": [datos]})


class ErrorOut(BaseModel):
    """Formato de error del contrato: nunca {"detail": ...} de FastAPI."""

    model_config = _ejemplo(error="no existe", detalle="conductor no existe")
    error: str
    detalle: Any = None


_DESCRIPCION_ERROR = {
    400: "Parámetro inválido",
    404: "No existe",
    409: "Transición de estado no permitida",
    422: "Payload o parámetros mal formados",
}


def errores(*codigos: int) -> dict:
    """Bloque `responses=` de FastAPI para documentar errores con ErrorOut."""
    return {c: {"model": ErrorOut, "description": _DESCRIPCION_ERROR[c]} for c in codigos}


class HealthOut(BaseModel):
    model_config = _ejemplo(status="ok", servicio="ms1")
    status: str
    servicio: str


class ListadoUsuarios(BaseModel):
    total: int = Field(examples=[20000])
    page: int = Field(examples=[1])
    limit: int = Field(examples=[20])
    items: list[UsuarioOut]


class ListadoConductores(BaseModel):
    total: int = Field(examples=[600])
    page: int = Field(examples=[1])
    limit: int = Field(examples=[20])
    items: list[ConductorOut]


# ---------------------------------------------------------------------------
# Reglas de negocio
# ---------------------------------------------------------------------------
class ValidacionUsuario(BaseModel):
    model_config = _ejemplo(usuario_id=2, puede_solicitar_viaje=False, edad=15,
                            motivos=["menor de edad (15 años, mínimo 18)"])
    usuario_id: int
    puede_solicitar_viaje: bool
    edad: int | None = Field(description="Años cumplidos; null si no hay fecha de nacimiento")
    motivos: list[str] = Field(description="Por qué no puede viajar (vacío si puede)")


class VehiculoAValidar(VehiculoBase):
    """Vehículo a evaluar. No se guarda en la base de datos."""

    model_config = _ejemplo(placa="ABC-123", marca="Toyota", modelo="Hiace", anio=2023,
                            capacidad=7, tipo_servicio="xl")


class ValidacionVehiculo(BaseModel):
    model_config = _ejemplo(valido=False, antiguedad_anios=8,
                            servicios_habilitados=["economico", "estandar"],
                            problemas=["no cumple requisitos de 'xl' (habilitado para: economico, estandar)"])
    valido: bool
    antiguedad_anios: int
    servicios_habilitados: list[str] = Field(description="Servicios que cumple por antigüedad y capacidad")
    problemas: list[str]


class VehiculoEvaluado(ValidacionVehiculo):
    placa: str


class Elegibilidad(BaseModel):
    model_config = _ejemplo(
        conductor_id=101, elegible=True, servicios_habilitados=["economico", "estandar"], motivos=[],
        activo=True, rating_promedio=4.27, total_resenas=41,
        vehiculos=[{"placa": "C5G-866", "valido": False, "antiguedad_anios": 1,
                    "servicios_habilitados": ["economico", "estandar", "confort"],
                    "problemas": ["no cumple requisitos de 'xl' (habilitado para: economico, estandar, confort)"]}],
        advertencias=[])
    conductor_id: int
    elegible: bool = Field(description="Activo + ≥1 vehículo apto + rating ≥ 3.5 (con ≥5 reseñas)")
    servicios_habilitados: list[str] = Field(description="Servicios que puede ofrecer según vehículos y rating")
    motivos: list[str] = Field(description="Por qué no es elegible (vacío si lo es)")
    activo: bool
    rating_promedio: float | None = Field(description="Rating según MS3; null si no tiene reseñas o MS3 no respondió")
    total_resenas: int
    vehiculos: list[VehiculoEvaluado]
    advertencias: list[str] = Field(description="Ej. 'ms3 no disponible: rating no evaluado'")


class Categoria(BaseModel):
    model_config = _ejemplo(conductor_id=101, nivel="regular", antiguedad_anios=5, comision_plataforma=0.2,
                            rating_promedio=4.27, total_resenas=41, advertencias=[])
    conductor_id: int
    nivel: str = Field(description="nuevo | regular | senior | elite")
    antiguedad_anios: int
    comision_plataforma: float = Field(description="Fracción que cobra la plataforma (0.25 … 0.10)")
    rating_promedio: float | None
    total_resenas: int
    advertencias: list[str]


class ConductorDisponible(BaseModel):
    conductor_id: int
    nombre: str
    distrito_base: str | None
    rating_promedio: float | None
    total_resenas: int
    servicios_habilitados: list[str]
    puntaje: float = Field(description="80% rating + 20% antigüedad, de 0 a 100")


class Disponibles(BaseModel):
    model_config = _ejemplo(
        total=1, limit=10, evaluados=22, advertencias=[],
        items=[{"conductor_id": 509, "nombre": "Cruz Ballesteros", "distrito_base": "Miraflores",
                "rating_promedio": 4.56, "total_resenas": 39,
                "servicios_habilitados": ["confort", "economico", "estandar"], "puntaje": 76.96}])
    total: int = Field(description="Conductores aptos encontrados")
    limit: int
    items: list[ConductorDisponible] = Field(description="Ordenados por puntaje, de mayor a menor")
    evaluados: int = Field(description="Candidatos revisados (máximo 50 por búsqueda)")
    advertencias: list[str]

