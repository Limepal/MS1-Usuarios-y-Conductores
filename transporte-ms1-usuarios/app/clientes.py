"""Cliente HTTP hacia MS3 (calificaciones), fuente de verdad del rating.

La columna local `conductores.calificacion_promedio` no se sincroniza con MS3,
así que las reglas de rating consultan GET /ms3/conductores/{id}/resumen.

Tolerancia (Contrato Cero §6): timeout 5 s + 1 reintento. Si MS3 no responde,
se devuelve None y el llamador agrega una advertencia; nunca un 500.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

import httpx

from . import config
from .reglas import Rating

logger = logging.getLogger("ms1.clientes")

TIMEOUT_S = 5.0
REINTENTOS = 1


def rating_de_conductor(conductor_id: int, http: httpx.Client | None = None) -> Rating | None:
    """Rating según MS3. Rating(None, 0) si no tiene reseñas; None si MS3 no responde."""
    if not config.MS3_URL:
        return None
    url = f"{config.MS3_URL}/conductores/{conductor_id}/resumen"
    cliente = http or httpx.Client(timeout=TIMEOUT_S)
    try:
        for intento in range(REINTENTOS + 1):
            try:
                r = cliente.get(url)
                if r.status_code == 404:  # MS3: "El conductor no tiene calificaciones"
                    return Rating(promedio=None, total=0)
                r.raise_for_status()
                datos = r.json()
                return Rating(promedio=float(datos["promedio"]), total=int(datos["total"]))
            except (httpx.HTTPError, KeyError, ValueError) as exc:
                logger.warning("MS3 %s intento %d: %s", url, intento + 1, exc)
        return None
    finally:
        if http is None:
            cliente.close()


def ratings_de_conductores(ids: list[int]) -> dict[int, Rating | None]:
    """Consulta varios ratings en paralelo (para /conductores/disponibles)."""
    if not ids:
        return {}
    with httpx.Client(timeout=TIMEOUT_S) as http, ThreadPoolExecutor(max_workers=10) as pool:
        resultados = pool.map(lambda i: rating_de_conductor(i, http), ids)
        return dict(zip(ids, resultados))
