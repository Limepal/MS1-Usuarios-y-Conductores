"""Health check de MS1.

GET /ms1/health -> 200 {"status":"ok","servicio":"ms1"}
Regla 4: NO debe tocar la base de datos.
"""

from fastapi import APIRouter

from ..schemas import HealthOut

router = APIRouter(prefix="/ms1", tags=["Salud"])


@router.get("/health", response_model=HealthOut, summary="Health check (no toca la BD)")
def health() -> dict:
    return {"status": "ok", "servicio": "ms1"}
