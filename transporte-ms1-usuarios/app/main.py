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
        "Microservicio de usuarios (pasajeros) y conductores con sus vehículos. "
        "Formato ISO 8601 UTC con 'Z'. Listados {total,page,limit,items}."
    ),
    version="1.0.0",
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
