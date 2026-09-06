"""Muebles de test de MS1.

Los tests requieren un PostgreSQL de prueba accesible. La URL se toma de
TEST_POSTGRES_URL (por defecto, la misma POSTGRES_URL pero con base
usuarios_db_test). Se crean las tablas del esquema y se sobreescribe
la dependencia get_db para que las rutas usen el motor de prueba.
"""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app import models  # noqa: F401  (registra los modelos en Base.metadata)


TEST_DATABASE_URL = os.getenv(
    "TEST_POSTGRES_URL",
    "postgresql://app_ms1:app_ms1_test@localhost:5432/usuarios_db_test",
)


@pytest.fixture(scope="session")
def test_engine():
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def db_session(test_engine):
    TestingSession = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# Limpia las tablas entre tests para aislamiento.
@pytest.fixture(autouse=True)
def _limpiar_bd(db_session):
    yield
    from sqlalchemy import text

    db_session.execute(text("TRUNCATE vehiculos, conductores, usuarios RESTART IDENTITY CASCADE"))
    db_session.commit()
