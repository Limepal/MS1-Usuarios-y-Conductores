"""Health check de MS1.

GET /ms1/health -> 200 {"status":"ok","servicio":"ms1"}
Regla 4: NO debe tocar la base de datos.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/ms1")


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "servicio": "ms1"}
