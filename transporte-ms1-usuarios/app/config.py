"""Configuración de MS1. Lee las variables de entorno definidas en .env.example.

Nombres de variables NO modificables (Contrato Cero v1.0):
BD_HOST, POSTGRES_URL, POSTGRES_PASS, API_GATEWAY_URL, PORT
"""

import os
import logging
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:
    pass

logger = logging.getLogger("ms1.config")


def _get_env(
    nombre: str, default: str | None = None, warn: bool = True
) -> str | None:
    """Lee una variable de entorno y registra advertencias si falta."""
    valor = os.getenv(nombre)
    if valor is None or valor == "":
        if default is not None:
            return default
        if warn:
            logger.warning("Variable de entorno %s no definida.", nombre)
        return None
    return valor


# --- PostgreSQL (servidor privado mv-bd: 10.0.2.x) -----------------------------
BD_HOST = _get_env("BD_HOST", default="localhost", warn=False) or "localhost"

# POSTGRES_URL suele venir predefinida en el contrato con interpolación de
# ${POSTGRES_PASS}. Si la variable viene completa se usa tal cual; si no, se
# arma a mano con los mismos nombres de variable (sin inventar nombres).
POSTGRES_URL = _get_env("POSTGRES_URL", warn=False) or (
    f"postgresql://app_ms1:{_get_env('POSTGRES_PASS') or ''}@{BD_HOST}:5432/usuarios_db"
)

# --- Swagger (servers[] apuntando al futuro API Gateway) ------------------------
API_GATEWAY_URL = _get_env("API_GATEWAY_URL") or "http://localhost:8001"

# --- Puerto de escucha ----------------------------------------------------------
PORT = int(_get_env("PORT", default="8001", warn=False) or "8001")
