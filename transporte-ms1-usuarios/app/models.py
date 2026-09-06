"""Modelos ORM de MS1. Los nombres de columna coinciden EXACTO con el DDL
de sql/schema.sql (Contrato Cero v1.0 §4/§8.1: mismo nombre que en la tabla).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(60), nullable=False)
    apellido: Mapped[str] = mapped_column(String(60), nullable=False)
    email: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    telefono: Mapped[str | None] = mapped_column(String(20), nullable=True)
    distrito: Mapped[str | None] = mapped_column(String(60), nullable=True)
    fecha_nacimiento: Mapped[date | None] = mapped_column(Date, nullable=True)
    fecha_registro: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("NOW()")
    )
    activo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("TRUE")
    )

    # TODO: lo consume MS2 vía HTTP en fase 3 (entidad pasajero), sin FK física
    # porque reside en otra base. Esta frontera de responsabilidad queda en P1.


class Conductor(Base):
    __tablename__ = "conductores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(60), nullable=False)
    apellido: Mapped[str] = mapped_column(String(60), nullable=False)
    email: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    telefono: Mapped[str | None] = mapped_column(String(20), nullable=True)
    nro_licencia: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    distrito_base: Mapped[str | None] = mapped_column(String(60), nullable=True)
    fecha_ingreso: Mapped[date] = mapped_column(Date, nullable=False)
    calificacion_promedio: Mapped[Decimal | None] = mapped_column(
        Numeric(3, 2), nullable=True, server_default=text("0")
    )
    activo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("TRUE")
    )

    vehiculos: Mapped[list["Vehiculo"]] = relationship(
        back_populates="conductor",
        cascade="all, delete-orphan",
        order_by="Vehiculo.id",
    )


class Vehiculo(Base):
    __tablename__ = "vehiculos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conductor_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("conductores.id", ondelete="CASCADE"),
        nullable=False,
    )
    placa: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    marca: Mapped[str] = mapped_column(String(40), nullable=False)
    modelo: Mapped[str] = mapped_column(String(40), nullable=False)
    anio: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    color: Mapped[str | None] = mapped_column(String(25), nullable=True)
    capacidad: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("4")
    )
    tipo_servicio: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'estandar'")
    )

    conductor: Mapped["Conductor"] = relationship(back_populates="vehiculos")
