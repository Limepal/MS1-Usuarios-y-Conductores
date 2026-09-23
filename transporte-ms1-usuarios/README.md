# transporte-ms1-usuarios

Microservicio **MS1 — Usuarios y Conductores** (responsabilidad de P1, CS2032 Cloud Computing).
Python + FastAPI + PostgreSQL 16. Cumple el Contrato Cero v1.0.

## Stack y decisiones técnicas

- **Python 3.11**, **FastAPI**, **SQLAlchemy 2.x (síncrono)** + **psycopg2-binary**.
- Se eligió SQLAlchemy síncrono por simplicidad de mantenimiento del equipo; el rendimiento
  asíncrono no es crítico para MS1. Está documentado aquí para que sea consistente en todo el repo.
- Las fechas se serializan en **ISO 8601 UTC con `Z`** (regla 3). Nunca epoch, nunca local.
- Los listados usan el formato `{total, page, limit, items}` con paginación real `LIMIT/OFFSET`.

## Enfoque: lógica de negocio, no CRUD

MS1 **no crea, edita ni borra** usuarios/conductores/vehículos: los datos se cargan
por seed (20 000 usuarios, 600 conductores, 600 vehículos). Expone las consultas que
consumen MS2, MS4 y el frontend, y **reglas de negocio** sobre esos datos.

Las reglas viven en `app/reglas.py` como funciones puras (sin FastAPI ni BD), así se
prueban de forma aislada; los routers solo leen la BD, aplican la regla y responden.

El rating del conductor se lee de **MS3** (`GET /ms3/conductores/{id}/resumen`), que
es la fuente de verdad (la columna local `calificacion_promedio` no se sincroniza).
Tolerancia: timeout 5 s + 1 reintento; si MS3 no responde se devuelve
`advertencias: ["ms3 no disponible: rating no evaluado"]`, nunca 500.

### Reglas

| Regla | Detalle |
|-------|---------|
| Pasajero puede viajar | activo, 18+ años (por `fecha_nacimiento`) y con teléfono |
| Vehículo válido | placa `ABC-123`, máx. 15 años, `tipo_servicio` existente |
| Requisitos por servicio | economico: ≤15 años · estandar: ≤12, rating ≥4.0 · confort: ≤6, rating ≥4.5 · xl: ≤10, 6+ asientos, rating ≥4.0 |
| Conductor elegible | activo + ≥1 vehículo apto + rating ≥3.5 (solo se exige con ≥5 reseñas) |
| Categoría / comisión | nuevo 25% · regular (1+ año) 20% · senior (3+ años, ≥4.3) 15% · elite (5+ años, ≥4.7) 10% |
| Puntaje de asignación | 80% rating + 20% antigüedad (saturada a 5 años), 0..100 |
| Activar conductor | solo si está suspendido y tiene un vehículo apto |

## Estructura

```
app/
├── main.py          # FastAPI, include_router(prefix="/ms1"), docs en /ms1/docs
├── config.py        # variables de entorno (contrato + MS3_URL)
├── database.py      # engine + session (SQLAlchemy + psycopg2)
├── models.py        # ORM: Usuario, Conductor, Vehiculo
├── schemas.py       # Pydantic: respuestas en snake_case
├── reglas.py        # reglas de negocio puras (sin BD ni HTTP)
├── clientes.py      # cliente HTTP a MS3 (rating), timeout + reintento
├── routers/
│   ├── usuarios.py
│   ├── conductores.py
│   └── health.py
└── utils/
    └── pagination.py
sql/schema.sql       # DDL exacto del contrato (sin cambios)
tests/               # test_reglas.py (sin BD) + integración (con Postgres)
```

## Variables de entorno

| Variable | Ejemplo | Notas |
|----------|---------|-------|
| `POSTGRES_URL` / `POSTGRES_PASS` / `BD_HOST` | `10.0.2.85` | nombres del contrato |
| `MS3_URL` | `http://ms3:8003/ms3` | opcional; sin ella el rating no se evalúa (con advertencia) |
| `API_GATEWAY_URL`, `PORT` | | Swagger / puerto |

## Levantar todo (local, con Docker Compose)

```bash
cp .env.example .env
docker compose -f docker-compose.local.yml up --build
```

- Swagger: **http://localhost:8001/ms1/docs**
- Health: **http://localhost:8001/ms1/health** → `{"status":"ok","servicio":"ms1"}`

## Tests

```bash
pip install -r requirements.txt
# Reglas de negocio (no necesitan BD)
python -m pytest tests/test_reglas.py -v
# Todo, con un Postgres de prueba en Docker
docker run -d --rm --name ms1_test_pg -e POSTGRES_USER=app_ms1 -e POSTGRES_PASSWORD=app_ms1_test   -e POSTGRES_DB=usuarios_db_test -p 5433:5432 postgres:16
TEST_POSTGRES_URL=postgresql://app_ms1:app_ms1_test@127.0.0.1:5433/usuarios_db_test python -m pytest -v
```

Las llamadas a MS3 se simulan con `monkeypatch` en los tests.

## Endpoints (todos bajo `/ms1`)

**Consultas** (contrato con MS2, MS4 y frontend; la forma de respuesta no cambia):

| Método | Ruta | Notas |
|--------|------|-------|
| GET | `/ms1/health` | no toca BD |
| GET | `/ms1/usuarios?distrito=&page=&limit=` | paginado |
| GET | `/ms1/usuarios/{id}` | MS2 lo usa para validar existencia |
| GET | `/ms1/conductores?distrito_base=&page=&limit=` | paginado |
| GET | `/ms1/conductores/{id}` | con vehículos embebidos |
| GET | `/ms1/conductores/{id}/vehiculos` | **lista** (no paginada), la consume MS4 |

**Lógica de negocio:**

| Método | Ruta | Qué decide |
|--------|------|-----------|
| GET | `/ms1/usuarios/{id}/validacion` | ¿puede solicitar un viaje? + motivos |
| POST | `/ms1/usuarios/{id}/suspender` · `/reactivar` | transición de estado (409 si no aplica) |
| GET | `/ms1/conductores/disponibles?distrito_base=&tipo_servicio=&limit=` | ranking de conductores aptos |
| GET | `/ms1/conductores/{id}/elegibilidad` | ¿puede operar? servicios habilitados + motivos |
| GET | `/ms1/conductores/{id}/categoria` | nivel, antigüedad y comisión |
| POST | `/ms1/conductores/{id}/activar` · `/suspender` | ciclo de vida (409 si no aplica) |
| POST | `/ms1/vehiculos/validar` | valida un vehículo sin guardarlo |

## Frontera de responsabilidad (P1)

MS1 solo implementa usuarios, conductores y vehículos. Los otros microservicios
(MS2–MS5) **no** se construyen ni simulan aquí, salvo el health check mínimo.
Donde corresponde se dejaron comentarios `# TODO: lo consume MS2 vía HTTP en fase 3`
para marcar la frontera.

## Decisiones no cubiertas por el contrato

- **Motor de BD (SQLAlchemy síncrono + psycopg2)**: ver *Stack*.
- **Filtro `distrito_base` en conductores**: se agregó por consistencia con usuarios.
- **Default de `API_GATEWAY_URL`** en local: `http://localhost:8001` (en producción se setea la URL real del gateway).
- **`tipo_servicio` inválido** en `/conductores/disponibles` devuelve **400**.
- **Sin cambios de esquema**: la ingesta de MS5 hace `SELECT *` de las 3 tablas, así que
  agregar columnas desalinearía las tablas de Glue/Athena. Todo se deriva de columnas existentes.
- El usuario de aplicación nunca es `postgres`/`admin`; siempre `app_ms1`.
