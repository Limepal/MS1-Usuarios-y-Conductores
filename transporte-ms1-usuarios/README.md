# transporte-ms1-usuarios

Microservicio **MS1 — Usuarios y Conductores** (responsabilidad de P1, CS2032 Cloud Computing).
Python + FastAPI + PostgreSQL 16. Cumple el Contrato Cero v1.0.

## Stack y decisiones técnicas

- **Python 3.11**, **FastAPI**, **SQLAlchemy 2.x (síncrono)** + **psycopg2-binary**.
- Se eligió SQLAlchemy síncrono por simplicidad de mantenimiento del equipo; el rendimiento
  asíncrono no es crítico para MS1. Está documentado aquí para que sea consistente en todo el repo.
- Las fechas se serializan en **ISO 8601 UTC con `Z`** (regla 3). Nunca epoch, nunca local.
- Los listados usan el formato `{total, page, limit, items}` con paginación real `LIMIT/OFFSET`.

## Estructura

```
app/
├── main.py          # FastAPI, include_router(prefix="/ms1"), docs en /ms1/docs
├── config.py        # lee variables de entorno (nombres exactos del contrato)
├── database.py      # engine + session (SQLAlchemy + psycopg2)
├── models.py        # ORM: Usuario, Conductor, Vehiculo
├── schemas.py       # Pydantic: request/response en snake_case
├── routers/
│   ├── usuarios.py
│   ├── conductores.py
│   └── health.py
└── utils/
    └── pagination.py
sql/schema.sql       # DDL exacto del contrato
tests/               # pytest
Dockerfile
docker-compose.local.yml
```

## Levantar todo (local, con Docker Compose)

```bash
# 1) Variables (opcional: definir POSTGRES_PASS)
cp .env.example .env

# 2) Levantar MS1 + PostgreSQL
docker compose -f docker-compose.local.yml up --build
```

- Swagger: **http://localhost:8001/ms1/docs**
- Health: **http://localhost:8001/ms1/health** → `{"status":"ok","servicio":"ms1"}`

## Correr los tests (requiere PostgreSQL de prueba)

Los tests usan la URL de `TEST_POSTGRES_URL` (por defecto
`postgresql://app_ms1:app_ms1_test@localhost:5432/usuarios_db_test`).

```bash
pip install -r requirements.txt
python -m pytest tests/ -v
```

> Nota: necesita una base `usuarios_db_test` creada previamente, o apuntar
> `TEST_POSTGRES_URL` a otra base de desarrollo.

## Endpoints (todos bajo `/ms1`)

| Método | Ruta                                        | Notas |
|--------|---------------------------------------------|-------|
| GET    | `/ms1/health`                               | 200, no toca BD |
| GET    | `/ms1/docs`                                 | Swagger |
| GET    | `/ms1/usuarios?distrito=&page=&limit=`      | listado paginado |
| GET    | `/ms1/usuarios/{id}`                        | 404 si no existe |
| POST   | `/ms1/usuarios`                             | 201 |
| PUT    | `/ms1/usuarios/{id}`                        | actualiza completo |
| DELETE | `/ms1/usuarios/{id}`                        | 204 |
| GET    | `/ms1/conductores?distrito_base=&page=&limit=` | listado paginado |
| GET    | `/ms1/conductores/{id}`                     | conductor con vehículo embebido |
| POST   | `/ms1/conductores`                          | 201 |
| PUT    | `/ms1/conductores/{id}`                     | actualiza completo |
| DELETE | `/ms1/conductores/{id}`                     | 204, cascada a vehículos |
| GET    | `/ms1/conductores/{id}/vehiculos`           | vehículos del conductor |
| POST   | `/ms1/conductores/{id}/vehiculos`           | 201 (extensión permitida) |

## Frontera de responsabilidad (P1)

MS1 solo implementa usuarios, conductores y vehículos. Los otros microservicios
(MS2–MS5) **no** se construyen ni simulan aquí, salvo el health check mínimo.
Donde corresponde se dejaron comentarios `# TODO: lo consume MS2 vía HTTP en fase 3`
para marcar la frontera.

## Decisiones no cubiertas por el contrato

- **Motor de BD (SQLAlchemy síncrono + psycopg2)**: ver *Stack*.
- **Filtro `distrito_base` en conductores**: se agregó por consistencia con usuarios.
- **`POST /ms1/conductores/{id}/vehiculos`**: extensión permitida para poblar datos vía API.
- **Default de `API_GATEWAY_URL`** en local: `http://localhost:8001` (en producción se setea la URL real del gateway).
- **Validación de `tipo_servicio`** devuelve **400** (payload inválido), no 422.
- El usuario de aplicación nunca es `postgres`/`admin`; siempre `app_ms1`.
