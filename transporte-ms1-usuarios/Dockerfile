# Dockerfile multi-stage para MS1 (Python + FastAPI + uvicorn en puerto 8001)

# ---- Etapa 1: construir e instalar dependencias ----
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Solo requirements primero para aprovechar la caché de capas.
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- Etapa 2: imagen final mínima ----
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=builder /install /usr/local

COPY . .

EXPOSE 8001

# Regla: uvicorn escucha en 0.0.0.0:8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
