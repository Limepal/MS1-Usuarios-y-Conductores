"""Rutas de conductores (y sus vehículos) de MS1.

Todas montadas bajo /ms1 vía APIRouter(prefix="/ms1").
MS1 no crea ni borra conductores/vehículos (los datos se cargan por seed);
expone consultas y la lógica de negocio del conductor. Las reglas viven en
app/reglas.py; aquí solo se lee la BD, se consulta el rating en MS3 y se
arma la respuesta.

Consumidores: MS2 (GET /conductores/{id}), MS4 (GET /conductores/{id} y
/conductores/{id}/vehiculos, que devuelve una LISTA). No cambian de forma.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .. import clientes, reglas
from ..database import get_db
from ..models import Conductor, Vehiculo
from ..reglas import Rating
from ..schemas import ConductorConVehiculos, ConductorOut, VehiculoBase, VehiculoOut
from ..utils.pagination import construir_listado, normalizar_paginacion

router = APIRouter(prefix="/ms1", tags=["conductores"])

AVISO_MS3 = "ms3 no disponible: rating no evaluado"
MAX_CANDIDATOS = 50  # tope de consultas a MS3 por búsqueda de disponibles


def _conductor_o_404(db: Session, conductor_id: int, con_vehiculos: bool = False) -> Conductor:
    stmt = select(Conductor).where(Conductor.id == conductor_id)
    if con_vehiculos:
        stmt = stmt.options(selectinload(Conductor.vehiculos))
    conductor = db.scalars(stmt).first()
    if conductor is None:
        raise HTTPException(status_code=404, detail="conductor no existe")
    return conductor


def _rating(conductor_id: int, advertencias: list[str]) -> Rating:
    rating = clientes.rating_de_conductor(conductor_id)
    if rating is None:
        advertencias.append(AVISO_MS3)
        return Rating(promedio=None, total=0)
    return rating


# ---------------------------------------------------------------------------
# Consultas (contrato con MS2 / MS4 / frontend)
# ---------------------------------------------------------------------------
@router.get("/conductores", response_model=dict)
def listar_conductores(
    distrito_base: str | None = Query(default=None, description="Filtro por distrito base"),
    page: int | None = Query(default=None, ge=1),
    limit: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
) -> dict:
    page, limit = normalizar_paginacion(page, limit)

    filtro = None
    if distrito_base is not None:
        filtro = Conductor.distrito_base == distrito_base

    total = db.scalar(
        select(func.count(Conductor.id)).where(filtro)
        if filtro is not None
        else select(func.count(Conductor.id))
    )

    stmt = select(Conductor).order_by(Conductor.id)
    if filtro is not None:
        stmt = stmt.where(filtro)
    stmt = stmt.offset((page - 1) * limit).limit(limit)

    items = [
        ConductorOut.model_validate(c).model_dump(mode="json")
        for c in db.scalars(stmt).all()
    ]
    return construir_listado(items, total, page, limit)


# Declarada antes de /conductores/{conductor_id} para que "disponibles" no
# se interprete como un id.
@router.get("/conductores/disponibles", response_model=dict)
def conductores_disponibles(
    distrito_base: str | None = Query(default=None),
    tipo_servicio: str | None = Query(default=None, description="economico|estandar|confort|xl"),
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
) -> dict:
    """Conductores que pueden tomar un viaje ahora, ordenados por puntaje.

    Filtra activos (y distrito), descarta los que no tienen un vehículo apto
    para el servicio pedido, consulta su rating en MS3 y ordena por
    puntaje_asignacion (80% rating + 20% antigüedad).
    """
    if tipo_servicio is not None and tipo_servicio not in reglas.TIPOS_SERVICIO:
        raise HTTPException(
            status_code=400,
            detail=f"tipo_servicio inválido. Válidos: {', '.join(sorted(reglas.TIPOS_SERVICIO))}",
        )
    hoy = date.today()

    stmt = (
        select(Conductor)
        .options(selectinload(Conductor.vehiculos))
        .where(Conductor.activo.is_(True))
        .order_by(Conductor.fecha_ingreso, Conductor.id)
    )
    if distrito_base is not None:
        stmt = stmt.where(Conductor.distrito_base == distrito_base)

    candidatos = []
    for c in db.scalars(stmt):
        servicios = {s for v in c.vehiculos for s in reglas.servicios_del_vehiculo(v, hoy)}
        if servicios and (tipo_servicio is None or tipo_servicio in servicios):
            candidatos.append(c)
        if len(candidatos) >= MAX_CANDIDATOS:
            break

    advertencias: list[str] = []
    ratings = clientes.ratings_de_conductores([c.id for c in candidatos])
    if any(r is None for r in ratings.values()):
        advertencias.append(AVISO_MS3)

    items = []
    for c in candidatos:
        rating = ratings.get(c.id) or Rating(promedio=None, total=0)
        evaluacion = reglas.evaluar_conductor(c.activo, c.vehiculos, rating, hoy)
        if not evaluacion["elegible"]:
            continue
        if tipo_servicio is not None and tipo_servicio not in evaluacion["servicios_habilitados"]:
            continue
        items.append({
            "conductor_id": c.id,
            "nombre": f"{c.nombre} {c.apellido}",
            "distrito_base": c.distrito_base,
            "rating_promedio": rating.promedio,
            "total_resenas": rating.total,
            "servicios_habilitados": evaluacion["servicios_habilitados"],
            "puntaje": reglas.puntaje_asignacion(c.fecha_ingreso, rating, hoy),
        })

    items.sort(key=lambda x: x["puntaje"], reverse=True)
    return {
        "total": len(items),
        "limit": limit,
        "items": items[:limit],
        "evaluados": len(candidatos),
        "advertencias": advertencias,
    }


@router.get("/conductores/{conductor_id}", response_model=ConductorConVehiculos)
def obtener_conductor(conductor_id: int, db: Session = Depends(get_db)) -> ConductorConVehiculos:
    return ConductorConVehiculos.model_validate(_conductor_o_404(db, conductor_id, True))


@router.get("/conductores/{conductor_id}/vehiculos", response_model=list[VehiculoOut])
def listar_vehiculos(conductor_id: int, db: Session = Depends(get_db)) -> list[VehiculoOut]:
    _conductor_o_404(db, conductor_id)
    stmt = select(Vehiculo).where(Vehiculo.conductor_id == conductor_id).order_by(Vehiculo.id)
    return [VehiculoOut.model_validate(v) for v in db.scalars(stmt).all()]


# ---------------------------------------------------------------------------
# Lógica de negocio: evaluación del conductor
# ---------------------------------------------------------------------------
@router.get("/conductores/{conductor_id}/elegibilidad", response_model=dict)
def elegibilidad_conductor(conductor_id: int, db: Session = Depends(get_db)) -> dict:
    """¿Puede operar el conductor y en qué servicios? Explica los motivos.

    Elegible = activo AND >=1 vehículo apto AND rating (MS3) >= mínimo.
    Con menos de 5 reseñas el rating aún no se exige.
    """
    c = _conductor_o_404(db, conductor_id, True)
    hoy = date.today()
    advertencias: list[str] = []
    rating = _rating(conductor_id, advertencias)
    evaluacion = reglas.evaluar_conductor(c.activo, c.vehiculos, rating, hoy)
    return {
        "conductor_id": conductor_id,
        **evaluacion,
        "activo": c.activo,
        "rating_promedio": rating.promedio,
        "total_resenas": rating.total,
        "vehiculos": [
            {"placa": v.placa, **reglas.validar_vehiculo(v, hoy)} for v in c.vehiculos
        ],
        "advertencias": advertencias,
    }


@router.get("/conductores/{conductor_id}/categoria", response_model=dict)
def categoria_conductor(conductor_id: int, db: Session = Depends(get_db)) -> dict:
    """Nivel (nuevo/regular/senior/elite) por antigüedad + rating, y su comisión."""
    c = _conductor_o_404(db, conductor_id)
    advertencias: list[str] = []
    rating = _rating(conductor_id, advertencias)
    return {
        "conductor_id": conductor_id,
        **reglas.categoria_conductor(c.fecha_ingreso, rating, date.today()),
        "rating_promedio": rating.promedio,
        "total_resenas": rating.total,
        "advertencias": advertencias,
    }


@router.post("/conductores/{conductor_id}/activar", response_model=ConductorOut)
def activar_conductor(conductor_id: int, db: Session = Depends(get_db)) -> ConductorOut:
    """Reactiva un conductor suspendido si tiene al menos un vehículo apto."""
    c = _conductor_o_404(db, conductor_id, True)
    if c.activo:
        raise HTTPException(status_code=409, detail="el conductor ya está activo")
    hoy = date.today()
    if not any(reglas.servicios_del_vehiculo(v, hoy) for v in c.vehiculos):
        raise HTTPException(
            status_code=409,
            detail="no puede activarse: no tiene ningún vehículo que cumpla los requisitos",
        )
    c.activo = True
    db.commit()
    db.refresh(c)
    return ConductorOut.model_validate(c)


@router.post("/conductores/{conductor_id}/suspender", response_model=ConductorOut)
def suspender_conductor(conductor_id: int, db: Session = Depends(get_db)) -> ConductorOut:
    """Suspende un conductor activo. Transición inversa de activar."""
    c = _conductor_o_404(db, conductor_id)
    if not c.activo:
        raise HTTPException(status_code=409, detail="el conductor ya está suspendido")
    c.activo = False
    db.commit()
    db.refresh(c)
    return ConductorOut.model_validate(c)


# ---------------------------------------------------------------------------
# Lógica de negocio: validación de vehículos (no persiste nada)
# ---------------------------------------------------------------------------
@router.post("/vehiculos/validar", response_model=dict, tags=["vehiculos"])
def validar_vehiculo(payload: VehiculoBase) -> dict:
    """Valida placa, antigüedad y capacidad contra el tipo de servicio pedido."""
    return reglas.validar_vehiculo(payload, date.today())
