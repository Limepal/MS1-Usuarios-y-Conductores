# Proyecto Parcial CS2032 — Plataforma de transporte urbano

**Estado al 7 de setiembre de 2026**
Documento de contexto para todo el equipo. Si algo aquí contradice al código, el que está mal es el código.

---

## 1. Qué estamos construyendo

Una plataforma de transporte urbano tipo Uber/taxi, desplegada en AWS con 5 microservicios en Docker, frontend en Amplify y un pipeline analítico con S3 / Glue / Athena.

| MS | Rol | Lenguaje | Puerto | Prefijo | Base de datos |
|----|-----|----------|--------|---------|---------------|
| MS1 | Usuarios y Conductores | Python · FastAPI | 8001 | `/ms1` | PostgreSQL 16 · `usuarios_db` |
| MS2 | Viajes | Java 17 · Spring Boot 3 | 8002 | `/ms2` | MySQL 8 · `viajes_db` |
| MS3 | Calificaciones y Comentarios | Node 20 · Express 4 | 8003 | `/ms3` | MongoDB 7 · `calificaciones_db` |
| MS4 | Historial de Usuario | Python · FastAPI | 8004 | `/ms4` | — (orquesta MS1+MS2+MS3) |
| MS5 | Analítico | Python · boto3 | 8005 | `/ms5` | Athena sobre catálogo Glue |

**Consulta estrella del frontend:** *ingreso promedio por hora del día y por distrito.*

---

## 2. Reparto

| Parte | Responsable de |
|-------|----------------|
| **P1** | MS1 · infraestructura base (VPC, 3 MVs, security groups, Terraform) · diagrama de arquitectura en draw.io |
| **P2** | MS2 · balanceador de carga privado · la llamada MS2 → MS1 |
| **P3** | MS3 · AWS API Gateway con HTTPS · scripts de fake data de las 3 bases |
| **P4** | Frontend en Amplify · MS4 (sin base de datos) |
| **P5** | MV de ingesta · bucket S3 · 3 contenedores pull · catálogo Glue · MS5 con Athena |

---

## 3. Arquitectura desplegada

```
                    Frontend (AWS Amplify)  ← P4
                              │ HTTPS
                    API Gateway (HTTP API)  ← P3
                              │ VPC Link
                  ALB interno (privado)     ← P2
                    ┌─────────┴─────────┐
              mv-prod-a            mv-prod-b       (subred pública)
              ms1 ms2 ms3 ms4 ms5  ms1 ms2 ms3 ms4 ms5
                    └─────────┬─────────┘
                          mv-bd                    (subred PRIVADA)
                  postgres 5432 · mysql 3306 · mongo 27017

              mv-ingesta ──► S3 ──► Glue ──► Athena ──► MS5   ← P5
```

Las 2 MVs de producción son **idénticas**: cada una corre los 5 contenedores. El balanceador reparte entre ellas.

---

## 4. Convenciones obligatorias (Contrato Cero)

### Rutas
Cada API monta **todas** sus rutas bajo su prefijo:
- FastAPI: `app.include_router(router, prefix="/ms1")`, `docs_url="/ms1/docs"`
- Spring: `server.servlet.context-path=/ms2`
- Express: `app.use("/ms3", router)`

Los cinco exponen:
- `GET /msN/health` → `{"status":"ok","servicio":"msN"}` — sin tocar la BD. Lo consulta el balanceador cada 30 s.
- `GET /msN/docs` → Swagger UI, con `servers:` apuntando al API Gateway.

### Formato de respuesta
```
Fechas       ISO 8601 UTC con Z        "2026-08-14T21:58:40Z"
Dinero       number, 2 decimales, soles, sin símbolo
Nulos        null (nunca "" ni "N/A")
Listado      { "total": n, "page": 1, "limit": 20, "items": [...] }
Paginación   ?page=1&limit=20   (limit máximo 100)
Error        { "error": "mensaje corto", "detalle": "opcional" }
Códigos      200 · 201 · 204 · 400 · 404 · 409 · 422 · 500
CORS         SOLO en el API Gateway. Nunca en los microservicios.
```

Nombres en `snake_case` y en español, iguales en columna, ORM y JSON.
En Spring hace falta `spring.jackson.property-naming-strategy=SNAKE_CASE`.

### Llamadas entre microservicios
Timeout 5 s, un reintento. Si el servicio llamado no responde, el llamador devuelve su parte con el bloque faltante en `null` y `"advertencias": ["ms3 no disponible"]`. **Nunca un 500.**

---

## 5. Modelo de datos

### PostgreSQL — MS1
`usuarios`, `conductores`, `vehiculos`. Relación: `conductores` 1—N `vehiculos`.

### MySQL — MS2
`tarifas`, `viajes`, `paradas`. Relaciones: `tarifas` 1—N `viajes`, `viajes` 1—N `paradas`.

Columnas de `tarifas` según el schema real de P2: `tipo_servicio`, `tarifa_base`, `costo_por_km`, `costo_por_minuto`, `recargo_hora_pico`, `activa`.
En `paradas` la marca de tiempo se llama `llegada_en`.

### MongoDB — MS3
Colecciones `calificaciones` y `reportes`. Estructuras JSON documentadas en `transporte-ms3-calificaciones/docs/esquemas.json`.

Índices: `viaje_id` único, `{conductor_id, creado_en}`, `tags`, y `comentario` de tipo texto con `default_language: "spanish"`.

### Puntos de contacto entre las bases

No hay claves foráneas entre motores. Lo único que las une son referencias lógicas:

| Dato | PostgreSQL | MySQL | MongoDB |
|------|-----------|-------|---------|
| Pasajero | `usuarios.id` | `viajes.pasajero_id` | `calificaciones.pasajero_id` |
| Conductor | `conductores.id` | `viajes.conductor_id` | `calificaciones.conductor_id` |
| Vehículo | `vehiculos.id` | `viajes.vehiculo_id` | — |
| Viaje | — | `viajes.id` | `calificaciones.viaje_id` |
| Distrito | `distrito`, `distrito_base` | `distrito_origen/destino` | `distrito_origen/destino` |

Reglas: mismo nombre y tipo en las tres · mismos rangos de ID · misma semilla (`Faker.seed(42)`) · todo en UTC · sembrar en orden Postgres → MySQL → Mongo.

### Rangos y catálogos
```
usuarios        id 1..20000       conductores  id 1..600
vehiculos       id 1..600         tarifas      id 1..4
viajes          id 1..25000       calificaciones  viaje_id 1..22000

Fechas del dataset: 2026-03-01 a 2026-08-31

Distritos (12, idénticos en las 3 bases, con tildes):
Miraflores, San Isidro, Surco, Barranco, La Molina, Lince, Jesús María,
San Borja, Magdalena, Pueblo Libre, Callao, San Juan de Lurigancho

estado_viaje       solicitado | en_curso | finalizado | cancelado
metodo_pago        efectivo | tarjeta | billetera
tipo_servicio      economico | estandar | confort | xl
tags_calificacion  puntual | auto_limpio | conduccion_segura | amable
                   musica_agradable | ruta_eficiente | tarde | brusco
```

---

## 6. Infraestructura

Región única: **us-east-1**.

```
VPC 10.0.0.0/16
  10.0.1.0/24  pública    → mv-prod-a, mv-ingesta
  10.0.3.0/24  pública    → mv-prod-b   (2da AZ: la exige el balanceador)
  10.0.2.0/24  PRIVADA    → mv-bd (sin IP pública)

sg-alb    entrada 80 desde 10.0.0.0/16
sg-prod   entrada 8001-8005 desde sg-alb y desde sg-prod
          entrada 22 desde las IPs del equipo
sg-bd     entrada 5432 3306 27017 SOLO desde sg-prod
          NINGUNA regla con 0.0.0.0/0
```

La MV de bases no lleva IP pública. Es requisito explícito del enunciado y se verifica mirando las reglas del security group.

---

## 7. Estado del avance

### Terminado

| Qué | Quién |
|-----|-------|
| Contrato Cero v1.0 y repos en GitHub | P3 |
| MS1: código, DDL, tests con pytest, Terraform de la infraestructura | P1 |
| MS1 publicado: `gbodiaz/transporte-ms1-usuarios:1.0.0` | P1 |
| MS2: código completo, cumple el contrato (revisado) | P2 |
| MS3: código, Swagger, esquemas JSON, índices | P3 |
| MS3 publicado: `enrique231/transporte-ms3:1.1` | P3 |
| Scripts de fake data de las 3 bases | P3 |
| MS3 probado de punta a punta con 22,000 documentos en local | P3 |
| `docker-compose.bd.yml` con las 3 bases y sus schemas en `init/` | P3 |

### Pendiente

**P1 — es quien bloquea a todo el equipo**
1. Cerrar dos huecos antes de aplicar Terraform: `sg-alb` de `0.0.0.0/0` a `10.0.0.0/16`, y poner las IPs reales del equipo en `ip_equipo_cidr`.
2. `terraform apply` → crea mv-prod-a, mv-prod-b, mv-bd, mv-ingesta.
3. Pasar la hoja de IPs al grupo (privadas y públicas).
4. Levantar las 3 bases en mv-bd con el compose parcheado y la carpeta `init/`.
5. Poner las 5 imágenes en `docker-compose.prod.yml` y hacer `pull && up -d` en las dos MVs.
6. Diagrama de arquitectura en draw.io, con insumos de todos.

**P2**
1. Publicar su imagen en Docker Hub y avisar nombre y tag exactos.
2. Confirmar si `recargo_hora_pico` es fracción (0.35 = +35%) o multiplicador (1.35 = ×1.35). El script de fake data asume **fracción**; si su código Java asume otra cosa, los 25,000 montos quedan inconsistentes.
3. Subir su `01-schema.sql` a `transporte-infra/init/mysql/`.
4. Crear el ALB interno con los 5 target groups y las reglas por path (después de `terraform apply`).
5. Pasar a P3 el **ARN del listener** del ALB.

**P3**
1. Desplegar MS3 en las 2 MVs (espera a P1).
2. Sembrar las 3 bases en mv-bd — es el 50% exigido para la asesoría con el ACL (espera a P1).
3. API Gateway con VPC Link y CORS (espera el ALB de P2).
4. Verificar hoy si la cuenta permite crear VPC Links.

**P4** — ver `GUIA-P4.md`
**P5** — ver `GUIA-P5.md`

---

## 8. Fechas

| Hito | Fecha | Qué |
|------|-------|-----|
| Hito 1 | **Sáb 12-Set 23:59** | Exposición virtual con el ACL · 3 puntos |
| Hito 2 | **Dom 20-Set 23:59** | Informe y resumen en Canvas · 17 puntos |
| Exposición presencial | Semana 7 | El docente publica horarios |

**Condición eliminatoria:** no presentarse a la exposición presencial es desaprobatorio, con nota máxima 10.

**Avance mínimo del 50% para la asesoría con el ACL:** las 3 bases con datos cargados, al menos 1 microservicio conectado a su base y respondiendo, y el frontend consumiendo al menos 1 microservicio con 2 métodos REST.

---

## 9. Repositorios e imágenes

| Repo | Dueño |
|------|-------|
| `transporte-infra` (contrato, Terraform, compose, init/) | P1 y P3 |
| `MS1-Usuarios-y-Conductores` | P1 |
| `transporte-ms2-viajes` | P2 |
| `transporte-ms3-calificaciones` | P3 |
| MS4 y frontend | P4 |
| MS5 e ingesta | P5 |

| Imagen | Estado |
|--------|--------|
| `gbodiaz/transporte-ms1-usuarios:1.0.0` | publicada |
| MS2 | pendiente |
| `enrique231/transporte-ms3:1.1` | publicada |
| MS4 | pendiente |
| MS5 | pendiente |

---

## 10. Entregables que pide el enunciado

- 5 microservicios en Docker, 3 lenguajes, 3 bases (2 SQL + 1 NoSQL)
- Al menos 1 microservicio que consume otro (MS2 → MS1)
- 1 microservicio sin base de datos (MS4) y 1 analítico con Athena (MS5)
- Diagramas E/R de las 2 bases SQL + estructuras JSON de la NoSQL
- ≥20,000 registros en 1 tabla de cada base
- docker compose en 2 MVs de producción + balanceador privado
- Bases en una 3ra MV, privadas
- APIs expuestas con HTTPS por API Gateway
- Las 5 APIs en swagger-ui
- Web en Amplify consumiendo los 5 MS, ≥2 métodos REST de cada uno
- MV de ingesta + bucket S3 + 3 contenedores pull del 100% de los registros
- Catálogo Glue por cada archivo + E/R de todas las tablas del catálogo
- ≥4 consultas SQL en Athena que unan varias tablas + ≥2 vistas
- Diagrama de arquitectura de solución en draw.io
- Enlaces a los repositorios públicos de GitHub
- Informe en Word/PDF con evidencias + resumen en PowerPoint
