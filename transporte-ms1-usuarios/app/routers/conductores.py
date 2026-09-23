"""Rutas de conductores (y sus vehículos) de MS1.

Todas montadas bajo /ms1 vía APIRouter(prefix="/ms1").
DELETE de conductor cascada a sus vehículos (FK ON DELETE CASCADE).
"""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..models import Conductor, Vehiculo
from ..schemas import (
    TIPOS_SERVICIO,
    ConductorConVehiculos,
    ConductorCreate,
    ConductorOut,
    ConductorUpdate,
    VehiculoCreate,
    VehiculoOut,
)
from ..utils.pagination import construir_listado, normalizar_paginacion

router = APIRouter(prefix="/ms1", tags=["conductores"])


def _cargar_conductor_con_vehiculos(conductor: Conductor) -> ConductorConVehiculos:
    return ConductorConVehiculos.model_validate(conductor)


# ---------------------------------------------------------------------------
# Conductores
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


@router.get("/conductores/{conductor_id}", response_model=ConductorConVehiculos)
def obtener_conductor(conductor_id: int, db: Session = Depends(get_db)) -> ConductorConVehiculos:
    stmt = (
        select(Conductor)
        .options(selectinload(Conductor.vehiculos))
        .where(Conductor.id == conductor_id)
    )
    conductor = db.scalars(stmt).first()
    if conductor is None:
        raise HTTPException(status_code=404, detail="conductor no existe")
    return _cargar_conductor_con_vehiculos(conductor)


@router.post("/conductores", response_model=ConductorOut, status_code=201)
def crear_conductor(payload: ConductorCreate, db: Session = Depends(get_db)) -> ConductorOut:
    datos = payload.model_dump()
    datos["activo"] = True
    conductor = Conductor(**datos)
    db.add(conductor)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="email o licencia ya registrados"
        ) from exc
    db.refresh(conductor)
    return ConductorOut.model_validate(conductor)


@router.put("/conductores/{conductor_id}", response_model=ConductorOut)
def actualizar_conductor(
    conductor_id: int, payload: ConductorUpdate, db: Session = Depends(get_db)
) -> ConductorOut:
    conductor = db.get(Conductor, conductor_id)
    if conductor is None:
        raise HTTPException(status_code=404, detail="conductor no existe")
    for campo, valor in payload.model_dump().items():
        setattr(conductor, campo, valor)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="email o licencia ya registrados")
    db.refresh(conductor)
    return ConductorOut.model_validate(conductor)


@router.delete("/conductores/{conductor_id}", status_code=204, response_model=None)
def eliminar_conductor(conductor_id: int, db: Session = Depends(get_db)) -> None:
    conductor = db.get(Conductor, conductor_id)
    if conductor is None:
        raise HTTPException(status_code=404, detail="conductor no existe")
    # La cascada de vehículos la maneja la FK ON DELETE CASCADE de la BD.
    db.delete(conductor)
    db.commit()


# ---------------------------------------------------------------------------
# Vehículos de un conductor (extensión permitida para poblar datos vía API)
# ---------------------------------------------------------------------------
@router.get("/conductores/{conductor_id}/vehiculos", response_model=list[VehiculoOut])
def listar_vehiculos(conductor_id: int, db: Session = Depends(get_db)) -> list[VehiculoOut]:
    if db.get(Conductor, conductor_id) is None:
        raise HTTPException(status_code=404, detail="conductor no existe")
    stmt = select(Vehiculo).where(Vehiculo.conductor_id == conductor_id).order_by(Vehiculo.id)
    return [VehiculoOut.model_validate(v) for v in db.scalars(stmt).all()]


@router.post(
    "/conductores/{conductor_id}/vehiculos",
    response_model=VehiculoOut,
    status_code=201,
)
def crear_vehiculo(
    conductor_id: int, payload: VehiculoCreate, db: Session = Depends(get_db)
) -> VehiculoOut:
    if db.get(Conductor, conductor_id) is None:
        raise HTTPException(status_code=404, detail="conductor no existe")

    # Regla: tipo_servicio debe validarse contra el enum; se devuelve 400.
    if payload.tipo_servicio not in TIPOS_SERVICIO:
        raise HTTPException(
            status_code=400,
            detail=f"tipo_servicio inválido: '{payload.tipo_servicio}'. "
            f"Válidos: {', '.join(sorted(TIPOS_SERVICIO))}",
        )

    vehiculo = Vehiculo(**payload.model_dump(), conductor_id=conductor_id)
    db.add(vehiculo)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="placa ya registrada") from exc
    db.refresh(vehiculo)
    return VehiculoOut.model_validate(vehiculo)


# ---------------------------------------------------------------------------
# Lógica de negocio: ciclo de vida y elegibilidad del conductor
# El estado se representa con la columna `activo` (no requiere migración).
# Reglas de dominio: un conductor sólo opera si está activo, tiene licencia,
# al menos un vehículo y una calificación promedio aceptable.
# ---------------------------------------------------------------------------
RATING_MINIMO = 3.5  # umbral de negocio para poder operar


def _contar_vehiculos(db: Session, conductor_id: int) -> int:
    return db.scalar(
        select(func.count(Vehiculo.id)).where(Vehiculo.conductor_id == conductor_id)
    ) or 0


@router.post("/conductores/{conductor_id}/activar", response_model=ConductorOut)
def activar_conductor(conductor_id: int, db: Session = Depends(get_db)) -> ConductorOut:
    """Activa un conductor sólo si cumple las reglas de negocio.

    Regla: no se puede activar sin licencia registrada ni sin al menos un
    vehículo. Si ya está activo, la transición es inválida (409).
    """
    conductor = db.get(Conductor, conductor_id)
    if conductor is None:
        raise HTTPException(status_code=404, detail="conductor no existe")
    if conductor.activo:
        raise HTTPException(status_code=409, detail="el conductor ya está activo")
    if not conductor.nro_licencia:
        raise HTTPException(status_code=409, detail="no puede activarse sin licencia")
    if _contar_vehiculos(db, conductor_id) == 0:
        raise HTTPException(
            status_code=409,
            detail="no puede activarse: el conductor no tiene vehículos registrados",
        )
    conductor.activo = True
    db.commit()
    db.refresh(conductor)
    return ConductorOut.model_validate(conductor)


@router.post("/conductores/{conductor_id}/suspender", response_model=ConductorOut)
def suspender_conductor(
    conductor_id: int,
    motivo: str | None = Body(default=None, embed=True),
    db: Session = Depends(get_db),
) -> ConductorOut:
    """Suspende (desactiva) un conductor activo. Transición inversa de activar."""
    conductor = db.get(Conductor, conductor_id)
    if conductor is None:
        raise HTTPException(status_code=404, detail="conductor no existe")
    if not conductor.activo:
        raise HTTPException(status_code=409, detail="el conductor ya está inactivo")
    conductor.activo = False
    db.commit()
    db.refresh(conductor)
    return ConductorOut.model_validate(conductor)


@router.get("/conductores/{conductor_id}/elegibilidad", response_model=dict)
def elegibilidad_conductor(conductor_id: int, db: Session = Depends(get_db)) -> dict:
    """Evalúa si un conductor puede operar y explica por qué (regla de negocio).

    Elegible = activo AND tiene licencia AND tiene >=1 vehículo AND rating >= umbral.
    Devuelve la decisión y la lista de motivos que la sustentan.
    """
    conductor = db.get(Conductor, conductor_id)
    if conductor is None:
        raise HTTPException(status_code=404, detail="conductor no existe")

    n_vehiculos = _contar_vehiculos(db, conductor_id)
    rating = float(conductor.calificacion_promedio or 0)

    motivos: list[str] = []
    if not conductor.activo:
        motivos.append("conductor inactivo")
    if not conductor.nro_licencia:
        motivos.append("sin licencia registrada")
    if n_vehiculos == 0:
        motivos.append("sin vehículos registrados")
    if rating < RATING_MINIMO:
        motivos.append(f"rating {rating} por debajo del mínimo {RATING_MINIMO}")

    return {
        "conductor_id": conductor_id,
        "elegible": len(motivos) == 0,
        "rating_promedio": rating,
        "vehiculos": n_vehiculos,
        "activo": conductor.activo,
        "motivos": motivos,
    }
