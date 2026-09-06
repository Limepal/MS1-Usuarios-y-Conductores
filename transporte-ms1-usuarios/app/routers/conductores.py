"""Rutas de conductores (y sus vehículos) de MS1.

Todas montadas bajo /ms1 vía APIRouter(prefix="/ms1").
DELETE de conductor cascada a sus vehículos (FK ON DELETE CASCADE).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
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
