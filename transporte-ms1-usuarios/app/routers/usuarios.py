"""Rutas de usuarios de MS1.

Todas montadas bajo /ms1 vía APIRouter(prefix="/ms1").
Listado paginado con filtro opcional ?distrito=.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Usuario
from ..schemas import UsuarioCreate, UsuarioOut, UsuarioUpdate
from ..utils.pagination import construir_listado, normalizar_paginacion

router = APIRouter(prefix="/ms1", tags=["usuarios"])


@router.get("/usuarios", response_model=dict)
def listar_usuarios(
    distrito: str | None = Query(default=None, description="Filtro por distrito"),
    page: int | None = Query(default=None, ge=1),
    limit: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
) -> dict:
    page, limit = normalizar_paginacion(page, limit)

    filtro = None
    if distrito is not None:
        filtro = Usuario.distrito == distrito

    total = db.scalar(
        select(func.count(Usuario.id)).where(filtro)
        if filtro is not None
        else select(func.count(Usuario.id))
    )

    stmt = select(Usuario).order_by(Usuario.id)
    if filtro is not None:
        stmt = stmt.where(filtro)
    stmt = stmt.offset((page - 1) * limit).limit(limit)

    items = [
        UsuarioOut.model_validate(u).model_dump(mode="json")
        for u in db.scalars(stmt).all()
    ]
    return construir_listado(items, total, page, limit)


@router.get("/usuarios/{usuario_id}", response_model=UsuarioOut)
def obtener_usuario(usuario_id: int, db: Session = Depends(get_db)) -> UsuarioOut:
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=404, detail="usuario no existe")
    return UsuarioOut.model_validate(usuario)


@router.post("/usuarios", response_model=UsuarioOut, status_code=201)
def crear_usuario(payload: UsuarioCreate, db: Session = Depends(get_db)) -> UsuarioOut:
    usuario = Usuario(**payload.model_dump(), activo=True)
    db.add(usuario)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="email ya registrado",
        ) from exc
    db.refresh(usuario)
    return UsuarioOut.model_validate(usuario)


@router.put("/usuarios/{usuario_id}", response_model=UsuarioOut)
def actualizar_usuario(
    usuario_id: int, payload: UsuarioUpdate, db: Session = Depends(get_db)
) -> UsuarioOut:
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=404, detail="usuario no existe")
    for campo, valor in payload.model_dump().items():
        setattr(usuario, campo, valor)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="email ya registrado") from exc
    db.refresh(usuario)
    return UsuarioOut.model_validate(usuario)


@router.delete("/usuarios/{usuario_id}", status_code=204, response_model=None)
def eliminar_usuario(usuario_id: int, db: Session = Depends(get_db)) -> None:
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=404, detail="usuario no existe")
    db.delete(usuario)
    db.commit()
