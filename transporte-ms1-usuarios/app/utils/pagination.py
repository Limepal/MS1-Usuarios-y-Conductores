"""Helpers de paginación.

Formato obligatorio de listados (Contrato Cero v1.0 §5):
    { "total": N, "page": 1, "limit": 20, "items": [...] }
Parametros: ?page= (default 1) y ?limit= (default 20, maximo 100).
"""

from typing import Any

LIMITE_MAXIMO = 100
LIMITE_DEFAULT = 20


def normalizar_paginacion(page: int | None, limit: int | None) -> tuple[int, int]:
    """Devuelve (page, limit) saneados. page >= 1, 1 <= limit <= LIMITE_MAXIMO."""
    if limit is None or limit <= 0:
        limit = LIMITE_DEFAULT
    limit = min(limit, LIMITE_MAXIMO)

    if page is None or page <= 0:
        page = 1
    return page, limit


def construir_listado(items: list[Any], total: int, page: int, limit: int) -> dict:
    """Arma el envoltorio de listado respetando el formato del contrato."""
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "items": items,
    }
