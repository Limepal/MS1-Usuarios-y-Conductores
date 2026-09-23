"""Punto de entrada de MS1 - Usuarios y Conductores.

- Todos los routers se montan bajo /ms1 (APIRouter(prefix="/ms1")).
- Swagger se expone en /ms1/docs con el bloque servers apuntando al futuro
  API Gateway (configurable vía API_GATEWAY_URL).
- NO se configura CORS aquí: se hace UNA vez en el API Gateway (fase posterior).
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from . import config
from .routers import conductores, health, usuarios

app = FastAPI(
    title="MS1 - Usuarios y Conductores",
    description=(
        "Usuarios (pasajeros), conductores y vehículos de la plataforma de transporte urbano.\n\n"
        "MS1 **no crea ni borra registros** (los datos vienen del seed): expone las consultas que "
        "usan MS2, MS4 y el frontend, y **reglas de negocio** sobre esos datos. El rating de los "
        "conductores se consulta en **MS3** (timeout 5 s + 1 reintento; si no responde, "
        "`advertencias` en vez de error).\n\n"
        "Fechas en ISO 8601 UTC con `Z`. Listados `{total, page, limit, items}`. "
        "Errores `{error, detalle}`."
    ),
    openapi_tags=[
        {"name": "Usuarios", "description": "Consultas de pasajeros (las usan MS2, MS4 y el frontend)."},
        {"name": "Conductores", "description": "Consultas de conductores y sus vehículos (MS2, MS4)."},
        {"name": "Reglas · Usuarios", "description": "¿Puede viajar? · suspender / reactivar."},
        {"name": "Reglas · Conductores",
         "description": "Elegibilidad, categoría y comisión, ranking de disponibles, activar / suspender. "
                        "Consumen el rating de MS3."},
        {"name": "Reglas · Vehículos", "description": "Validación de vehículos contra requisitos de servicio."},
        {"name": "Salud", "description": "Health check del Contrato Cero."},
    ],
    version="2.0.0",
    docs_url="/ms1/docs",
    redoc_url=None,
    openapi_url="/ms1/openapi.json",
    servers=[{"url": config.API_GATEWAY_URL, "description": "API Gateway"}],
)


_ERROR_CORTO = {
    400: "payload inválido",
    404: "no existe",
    409: "conflicto",
    422: "payload inválido",
    500: "error interno",
}


@app.exception_handler(HTTPException)
async def _http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    # Regla de error: {"error": "mensaje corto", "detalle": "opcional, técnico"}
    # Nunca {"detail": ...} de FastAPI.
    detalle = exc.detail if isinstance(exc.detail, str) and exc.detail else None
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": _ERROR_CORTO.get(exc.status_code, "error"),
            "detalle": detalle,
        },
    )


@app.exception_handler(RequestValidationError)
async def _validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    # 422 = falla de validación cruzada / payload malformado (regla HTTP).
    return JSONResponse(
        status_code=422,
        content={"error": "payload inválido", "detalle": exc.errors()},
    )


app.include_router(health.router)
app.include_router(usuarios.router)
app.include_router(conductores.router)
