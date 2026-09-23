"""Rutas de usuarios (pasajeros) de MS1.

Todas montadas bajo /ms1 vía APIRouter(prefix="/ms1").
MS1 no crea ni borra usuarios (los datos se cargan por seed); expone
consultas y lógica de negocio: validación para viajar y suspensión.

Consumidores: MS2 (GET /usuarios/{id} para validar existencia), MS4 y el
frontend (listado + detalle). Esas respuestas no cambian de forma.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import reglas
from ..database import get_db
from ..models import Usuario
from ..schemas import ListadoUsuarios, UsuarioOut, ValidacionUsuario, errores
from ..utils.pagination import construir_listado, normalizar_paginacion

router = APIRouter(prefix="/ms1")
REGLAS = ["Reglas · Usuarios"]


def _usuario_o_404(db: Session, usuario_id: int) -> Usuario:
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=404, detail="usuario no existe")
    return usuario


@router.get(
    "/usuarios", response_model=None, tags=["Usuarios"], summary="Listar usuarios (paginado)",
    responses={200: {"model": ListadoUsuarios}},
)
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


@router.get(
    "/usuarios/{usuario_id}", response_model=UsuarioOut, tags=["Usuarios"],
    summary="Obtener usuario", description="MS2 lo usa para validar que el pasajero exista.",
    responses=errores(404),
)
def obtener_usuario(usuario_id: int, db: Session = Depends(get_db)) -> UsuarioOut:
    return UsuarioOut.model_validate(_usuario_o_404(db, usuario_id))


# ---------------------------------------------------------------------------
# Lógica de negocio
# ---------------------------------------------------------------------------
@router.get(
    "/usuarios/{usuario_id}/validacion", response_model=ValidacionUsuario, tags=REGLAS,
    summary="¿Puede el pasajero solicitar un viaje?", responses=errores(404),
)
def validar_usuario(usuario_id: int, db: Session = Depends(get_db)) -> dict:
    """Puede viajar si está **activo**, tiene **18 años o más** (según
    `fecha_nacimiento`) y tiene **teléfono**. Si no, `motivos` explica por qué."""
    u = _usuario_o_404(db, usuario_id)
    resultado = reglas.validar_pasajero(u.activo, u.fecha_nacimiento, u.telefono, date.today())
    return {"usuario_id": usuario_id, **resultado}


@router.post(
    "/usuarios/{usuario_id}/suspender", response_model=UsuarioOut, tags=REGLAS,
    summary="Suspender usuario", responses=errores(404, 409),
)
def suspender_usuario(usuario_id: int, db: Session = Depends(get_db)) -> UsuarioOut:
    """Pasa `activo` a false. 409 si ya estaba suspendido."""
    u = _usuario_o_404(db, usuario_id)
    if not u.activo:
        raise HTTPException(status_code=409, detail="el usuario ya está suspendido")
    u.activo = False
    db.commit()
    db.refresh(u)
    return UsuarioOut.model_validate(u)


@router.post(
    "/usuarios/{usuario_id}/reactivar", response_model=UsuarioOut, tags=REGLAS,
    summary="Reactivar usuario", responses=errores(404, 409),
)
def reactivar_usuario(usuario_id: int, db: Session = Depends(get_db)) -> UsuarioOut:
    """Pasa `activo` a true. 409 si ya estaba activo."""
    u = _usuario_o_404(db, usuario_id)
    if u.activo:
        raise HTTPException(status_code=409, detail="el usuario ya está activo")
    u.activo = True
    db.commit()
    db.refresh(u)
    return UsuarioOut.model_validate(u)
