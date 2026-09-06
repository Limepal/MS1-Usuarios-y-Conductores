"""Conexión a la base de datos.

Elección técnica (documentada en README): SQLAlchemy 2.x síncrono + psycopg2.
Se prioriza simplicidad de mantenimiento para el equipo sobre alto rendimiento
asíncrono, que no es crítico para MS1. Consistente en todo el microservicio.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from . import config

# pool_pre_ping evita conexiones muertas tras reinicios de PostgreSQL.
engine = create_engine(
    config.POSTGRES_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Base declarativa para los modelos ORM de MS1."""


def get_db():
    """Dependencia de FastAPI que entrega una sesión y la cierra al terminar."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
