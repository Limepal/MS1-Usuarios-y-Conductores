# Transporte Urbano · Contexto completo del proyecto (CS2032 Cloud Computing)

> Documento de contexto para el equipo y para cualquier IA que ayude con el proyecto.
> Describe **qué hay, dónde está, cómo funciona y cómo se opera**.
> Última actualización: **2026-09-24**. Estado: **desplegado y funcional de punta a punta**.

---

## 1. Resumen

Plataforma de **transporte urbano** (estilo Uber/DiDi, vista de backoffice) formada por
**5 microservicios + 1 frontend + un data lake analítico**, desplegada en **AWS Academy Learner Lab**.

| Componente | Qué hace | Stack | Base de datos |
|---|---|---|---|
| **MS1** · Usuarios y Conductores | Consultas y **reglas de negocio** (elegibilidad, categoría, ranking) | FastAPI (Python) | PostgreSQL 16 |
| **MS2** · Viajes y Pagos | Viajes, paradas, tarifas; valida pasajero/conductor contra MS1 | Spring Boot (Java) | MySQL 8 |
| **MS3** · Calificaciones | Calificaciones, reportes, reputación del conductor | Express (Node.js) | MongoDB 7 |
| **MS4** · Historial de Usuario | Orquestador: une MS1 + MS2 + MS3 | FastAPI (Python) | *(ninguna)* |
| **MS5** · Analítica | Consultas SQL en Athena sobre el data lake | FastAPI + boto3 | Athena / Glue / S3 |
| **Frontend** · VÍA | Backoffice web que consume los 5 MS | HTML/CSS/JS (sin framework) | — |
| **Ingesta** | 3 contenedores que copian el 100 % de las BD a S3 | Python + Docker | — |

**URLs públicas**

| Recurso | URL |
|---|---|
| API Gateway (única entrada pública, HTTPS) | `https://h4sh35u9ac.execute-api.us-east-1.amazonaws.com` |
| Swagger de cada MS | `https://h4sh35u9ac.execute-api.us-east-1.amazonaws.com/msN/docs` (N = 1…5) |
| Frontend (Amplify) | `https://main.d3ca05v1u9gljs.amplifyapp.com` |

---

## 2. Requisitos de la guía y cómo se cumplen

Guía: *Proyecto Parcial (Semana 3 a 6) V3.22*. Rúbrica: Backend 7 · Frontend 3 · Data Science 5 ·
Diagrama de arquitectura 1 · Exposición presencial 1 · Exposición virtual con ACL 3.

| Requisito | Cumplimiento |
|---|---|
| 5 microservicios en Docker | ✅ MS1–MS5, todos con `docker compose` en las 2 MV de producción |
| 3 MS con BD propia, 3 lenguajes, 3 BD (2 SQL + 1 NoSQL) | ✅ Python/PostgreSQL · Java/MySQL · Node/MongoDB |
| Cada BD SQL con ≥ 2 tablas relacionadas | ✅ MS1: conductores → vehiculos · MS2: tarifas → viajes → paradas |
| ≥ 1 MS con BD que consuma a otro MS | ✅ **MS1 → MS3** (rating) y **MS2 → MS1** (validación) |
| 1 MS sin BD que solo consuma otros | ✅ MS4 |
| 1 MS analítico con Athena | ✅ MS5 |
| ≥ 20 000 registros fake en al menos 1 tabla de cada BD | ✅ usuarios 20 000 · viajes 25 000 · calificaciones 22 000 |
| Docker compose en 2 MV de producción + balanceador **privado** | ✅ mv-prod-a / mv-prod-b + `transporte-alb` (Internal) |
| APIs públicas por HTTPS con API Gateway | ✅ `transporte-gw` (HTTP API) + VPC Link |
| BD en una 3.ª MV privada | ✅ `mv-bd` en subred privada, sin IP pública |
| Swagger UI de las 5 APIs | ✅ `/msN/docs` |
| Repos públicos | ✅ (sección 12) |
| Frontend en Amplify que consume los 5 MS con ≥ 2 métodos REST cada uno | ✅ (sección 6) |
| MV de ingesta + bucket S3 + 3 contenedores de ingesta (pull 100 %) | ✅ `mv-ingesta` + `transporte-datalake-et` |
| Catálogo Glue por cada archivo + diagrama E/R del catálogo | ✅ 8 tablas · diagrama en `diagramas/diagrama-er.drawio` (pág. 2) |
| ≥ 4 consultas SQL con JOIN en Athena + ≥ 2 vistas | ✅ `athena/consultas.sql` (verificadas) |
| Diagrama de arquitectura en draw.io | ⏳ a cargo del equipo |
| Informe (Word/PDF) + resumen PPT | ⏳ a cargo del equipo · capturas listas en `cloud122-con-titulos.docx` |

**Pedido del profe:** MS1 no debía ser un CRUD de "crear usuarios" sino **pura lógica de negocio**.
Se reimplementó así (sección 4.1).

---

## 3. Arquitectura

```
                    Navegador ── Frontend VÍA (AWS Amplify)
                                   │ HTTPS + CORS
                                   ▼
                API Gateway HTTP API "transporte-gw" (h4sh35u9ac)
                ruta única  ANY /{proxy+}   · CORS resuelto aquí
                                   │ VPC Link "ixtm1r"
                                   ▼
            ALB INTERNO "transporte-alb" · listener HTTP:80
            reglas por path: /ms2/* /ms3/* /ms4/* /ms5/*  · default → tg-ms1
                    ┌──────────────┴──────────────┐
                    ▼                             ▼
          mv-prod-a (us-east-1a)        mv-prod-b (us-east-1b)      ← réplicas idénticas
          ms1 ms2 ms3 ms4 ms5           ms1 ms2 ms3 ms4 ms5            (docker compose)
          MS1→MS3 · MS2→MS1 · MS4→MS1,2,3 (red interna de Docker / localhost)
                    └──────────────┬──────────────┘
                                   ▼
                  mv-bd (subred PRIVADA, sin IP pública)
                  PostgreSQL :5432 · MySQL :3306 · MongoDB :27017
                                   ▲  pull 100 %
                  mv-ingesta ──► S3 transporte-datalake-et/catalogo/<tabla>/
                                   ──► Glue crawler ──► base transporte_urbano
                                   ──► Athena ◄── MS5 (/ms5/…)
```

- **El único punto público es el API Gateway.** El ALB es interno; los puertos 8001–8005 solo aceptan tráfico del ALB.
  Las IP públicas de las MV **no sirven** para probar la API (y cambian en cada reinicio del lab).
- **El reparto por microservicio lo hace el ALB**, no el API Gateway (el gateway tiene una sola ruta comodín).
- **prod-a y prod-b son réplicas**: el ALB reparte; si una cae, la otra atiende. El consumo entre MS ocurre
  **dentro de la misma MV**.
- **CORS solo en el API Gateway** (Allow-Origin/Headers/Methods = `*`). Los MS no ponen CORS.

---

## 4. Microservicios

Convenciones comunes (**Contrato Cero**): prefijo `/msN`, `GET /msN/health → {"status":"ok","servicio":"msN"}`,
Swagger en `/msN/docs` y `/msN/openapi.json`, listados `{total, page, limit, items}` con `?page=&limit=`,
errores `{error, detalle}`, JSON en snake_case, fechas ISO 8601 UTC con `Z`, sin CORS en el MS.

### 4.1 MS1 · Usuarios y Conductores — lógica de negocio

- **Repo:** `Limepal/MS1-Usuarios-y-Conductores` → carpeta `transporte-ms1-usuarios/`
- **Stack:** FastAPI + SQLAlchemy 2 + PostgreSQL (`usuarios_db`, usuario `app_ms1`). Puerto 8001. Swagger v2.0.0.
- **No crea ni borra registros** (datos del seed). Sin cambios de esquema (la ingesta hace `SELECT *`).
- **Reglas puras** en `app/reglas.py` (sin BD ni HTTP); cliente a MS3 en `app/clientes.py`.
- **Consume MS3** (`MS3_URL=http://ms3:8003/ms3`): rating real del conductor desde `/ms3/conductores/{id}/resumen`
  (la columna local `calificacion_promedio` está en 0). Timeout 5 s + 1 reintento; si MS3 cae → `advertencias`, nunca 500.

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/ms1/usuarios` · `/ms1/usuarios/{id}` | Consultas (MS2 valida existencia con la 2.ª) |
| GET | `/ms1/conductores` · `/ms1/conductores/{id}` | Consultas (con vehículos embebidos) |
| GET | `/ms1/conductores/{id}/vehiculos` | **Lista** (no paginada; MS4 depende de esa forma) |
| GET | `/ms1/usuarios/{id}/validacion` | ¿Puede viajar? (activo, 18+, con teléfono) |
| POST | `/ms1/usuarios/{id}/suspender` · `/reactivar` | Transición de estado (409 si no aplica) |
| GET | `/ms1/conductores/disponibles?distrito_base=&tipo_servicio=&limit=` | Ranking de aptos (máx. 50 evaluados) |
| GET | `/ms1/conductores/{id}/elegibilidad` | ¿Puede operar? servicios habilitados + motivos |
| GET | `/ms1/conductores/{id}/categoria` | Nivel y comisión |
| POST | `/ms1/conductores/{id}/activar` · `/suspender` | Ciclo de vida (activar exige vehículo apto) |
| POST | `/ms1/vehiculos/validar` | Valida un vehículo sin guardarlo |

**Reglas**

| Regla | Detalle |
|---|---|
| Pasajero puede viajar | activo, ≥ 18 años, con teléfono |
| Vehículo válido | placa `ABC-123`, ≤ 15 años, `tipo_servicio` existente |
| Requisitos por servicio | economico ≤15 años · estandar ≤12 y rating ≥4.0 · confort ≤6 y ≥4.5 · xl ≤10, 6+ asientos y ≥4.0 |
| Conductor elegible | activo + ≥1 vehículo apto + rating ≥3.5 (solo con ≥5 reseñas) |
| Categoría / comisión | nuevo 25 % · regular (1+ año) 20 % · senior (3+ años, ≥4.3) 15 % · elite (5+ años, ≥4.7) 10 % |
| Puntaje de asignación | 80 % rating + 20 % antigüedad (saturada a 5 años), 0–100 |

**Tests:** 36 (13 de reglas sin BD + 23 de integración con Postgres en Docker). Ver README del MS.

### 4.2 MS2 · Viajes y Pagos

- **Repo:** `S1nk0-0/transporte-ms2-viajes` (del compañero P2). Spring Boot 3.3 + MySQL (`viajes_db`, usuario `app_ms2`). Puerto 8002, context-path `/ms2`.
- **Tablas:** `tarifas` (4) · `viajes` (25 000) · `paradas`. Esquema en `docs/01-schema.sql` (usa `multiplicador_hora_pico`).
- **Consume MS1:** `POST /ms2/viajes` llama a `GET /ms1/usuarios/{id}` y `/ms1/conductores/{id}`.
  404 → **422** "no existe en MS1"; MS1 caído → crea igual con advertencia. En prod: `VALIDAR_CON_MS1=true`, `MS1_URL=http://ms1:8001`.
- **Filtros en camelCase** (`?pasajeroId=&conductorId=&estado=&distritoOrigen=&distritoDestino=&desde=&hasta=`).
  Con snake_case los ignora (ese fue un bug de MS4, ya corregido).
- Endpoints: `GET /viajes`, `GET /viajes/{id}`, `POST /viajes`, `PATCH /viajes/{id}/estado`, `GET /tarifas`, `GET /health`.
- Imagen en prod: `enrique231/transporte-ms2:1.0.0` (Docker Hub).

### 4.3 MS3 · Calificaciones

- **Repo:** `enriquetorres-cell/transporte-ms3-calificaciones`. Express + Mongoose + MongoDB (`calificaciones_db`, usuario `app_ms3`). Puerto 8003, prefijo `/ms3`.
- **Colecciones:** `calificaciones` (22 000; índice único `viaje_id`, índice de texto en `comentario` en español,
  subdocumentos `moderacion` y `respuesta_conductor`) y `reportes` (300).
- Endpoints: `GET/POST /calificaciones` (filtros `viaje_id`, `conductor_id`, `pasajero_id`, `min_rating`, `tag`, `q`),
  `GET/PATCH/DELETE /calificaciones/{_id}`, `GET /conductores/{id}/resumen` (agregación `$facet`),
  `GET/POST /reportes`, `GET /health`, `GET /openapi.json`.
- Swagger estático en `docs/openapi.yaml` (v1.1.0, servers al API Gateway). Imagen en prod: `transporte-ms3:1.2` (construida en la MV).

### 4.4 MS4 · Historial de Usuario (orquestador, sin BD)

- **Repo:** `enriquetorres-cell/transporte-ms4`. FastAPI + httpx. Puerto 8004. Red `host` en la MV.
- Variables: `MS1_URL`, `MS2_URL`, `MS3_URL` (`http://localhost:800N/msN`). Timeout 5 s + 1 reintento; bloque faltante → `null` + advertencia.

| Endpoint | Une |
|---|---|
| `GET /ms4/usuarios/{id}/perfil` | usuario (MS1) + últimos viajes (MS2, `pasajeroId`) + calificaciones (MS3) |
| `GET /ms4/conductores/{id}/hoja-de-vida` | conductor y vehículos (MS1) + viajes (MS2, `conductorId`) + resumen (MS3) |
| `GET /ms4/viajes/{id}/detalle-completo` | viaje (MS2) + pasajero y conductor (MS1) + calificación (MS3, `?viaje_id=`) |

### 4.5 MS5 · Analítica (Athena)

- **Repos:** `DnCuadros23/transporte-ms5-analitica` (original) y `enriquetorres-cell/transporte-ms5-analitica`
  (copia sincronizada, **la que está desplegada**, con la inyección SQL corregida).
- FastAPI + boto3 → Athena, base `transporte_urbano`. Puerto 8005, red `host`.
- Variables: `GLUE_DATABASE=transporte_urbano`, `ATHENA_OUTPUT=s3://transporte-datalake-et/athena-results/`, `AWS_REGION=us-east-1`.
- **Credenciales:** usa el **rol `LabInstanceProfile`** de la MV (IMDS). **No** se pegan llaves ni se monta `~/.aws`.

| Endpoint | Consulta |
|---|---|
| `GET /ms5/ingresos/por-hora-distrito?distrito=` | Consulta estrella (viajes finalizados) |
| `GET /ms5/conductores/rating-por-distrito` | conductores ⋈ calificaciones |
| `GET /ms5/conductores/rating-por-antiguedad` | conductores ⋈ viajes ⋈ calificaciones |
| `GET /ms5/rutas/top-distritos?minimo=50` | viajes ⋈ calificaciones |
| `GET /ms5/vistas/rating-conductor?limit=` | lee la **vista** `v_rating_conductor` |
| `GET /ms5/vistas/ingreso-hora-distrito?limit=` | lee la **vista** `v_ingreso_hora_distrito` |

---

## 5. Consumo entre microservicios

| Quién | Consume a | Para qué |
|---|---|---|
| MS1 (Postgres) | MS3 | Rating del conductor (elegibilidad, categoría, ranking) |
| MS2 (MySQL) | MS1 | Validar pasajero y conductor al crear un viaje (404 → 422) |
| MS4 (sin BD) | MS1 + MS2 + MS3 | Perfil, hoja de vida, detalle completo |
| MS5 | Athena | Consultas sobre el data lake |
| MS3 | MS2 | *(opcional, apagado en prod: `VALIDAR_VIAJE=false`)* |

---

## 6. Frontend · VÍA (backoffice)

- **Repo:** `enriquetorres-cell/transporte-frontend`. Archivos: `index.html`, `styles.css`, `app.js`, `config.js`, `amplify.yml`.
- **Despliegue:** AWS Amplify (app `d3ca05v1u9gljs`, rama `main`). Cada `git push` publica solo (~2 min).
- **Diseño VÍA:** sidebar Asfalto `#13171C`, contenido Concreto `#EFF1EB`, texto Grafito `#1B2128`;
  Lima `#C8F542` solo sobre oscuro (en ruta / SÍ / CTA), Turquesa `#00A8B5` (rutas, links, gráfico),
  Rojo Freno `#FF3D5A` solo para cancelado y rating < 3 (con icono). Tipografías Space Grotesk / IBM Plex Sans / IBM Plex Mono.
- **Shell:** sidebar con **red en vivo** (health de los 5 MS cada 30 s), navegación y turno · topbar con buscador
  (`695` usuario, `C101` conductor, `V2044` viaje) · **carril de detalle** con fichas enlazadas (viaje → conductor → calificación → perfil).
- **Login:** Demo / Administrador / cuenta local (localStorage). **Analítica solo para Administrador.**

| Pestaña | MS | Métodos REST consumidos |
|---|---|---|
| Usuarios | MS1 | `GET /usuarios` · `/usuarios/{id}` · `/usuarios/{id}/validacion` |
| Conductores | MS1 | `GET /conductores/{id}/elegibilidad` · `/categoria` · `/conductores/disponibles` |
| Viajes | MS2 | `GET /viajes` (filtros) · `/viajes/{id}` |
| Calificaciones | MS3 | `GET /calificaciones` (búsqueda texto, rating, tag, conductor) |
| Reputación | MS3 | `GET /conductores/{id}/resumen` |
| Perfil | MS4 | `GET /usuarios/{id}/perfil` · `/conductores/{id}/hoja-de-vida` · `/viajes/{id}/detalle-completo` |
| Analítica | MS5 | `GET /ingresos/por-hora-distrito` · `/conductores/rating-por-distrito` · `/vistas/…` |

---

## 7. Data Science

### 7.1 Ingesta
- Código en `transporte-ms5-analitica/ingesta/`: `ingesta_ms1.py` (Postgres → CSV), `ingesta_ms2.py` (MySQL → CSV),
  `ingesta_ms3.py` (Mongo → JSON), `comun.py`, `Dockerfile`, `docker-compose.yml` (3 servicios).
- Estrategia **pull del 100 %**. Suben a `s3://transporte-datalake-et/catalogo/<tabla>/`.
- Variables: `S3_BUCKET`, `BD_HOST` (10.0.2.85), **`BD_PASS` obligatoria** (no se guarda en el repo).
- Corre en `mv-ingesta` (en `sg-prod`, por eso alcanza a `mv-bd`).

### 7.2 S3
Bucket `transporte-datalake-et`: `catalogo/` (8 carpetas, una por tabla — lo que lee Glue), `ingesta/` (histórico), `athena-results/`.

### 7.3 Glue
Crawler **`transporte-crawler`** (rol LabRole) sobre `s3://transporte-datalake-et/catalogo/` → base **`transporte_urbano`**:
`usuarios`, `conductores`, `vehiculos`, `viajes`, `tarifas`, `paradas`, `calificaciones`, `reportes` + 2 vistas.

### 7.4 Athena (`athena/consultas.sql`, todas verificadas)
1. viajes ⋈ vehiculos ⋈ tarifas — ingreso por tipo de servicio y marca
2. calificaciones ⋈ viajes — rating por distrito de origen
3. viajes ⋈ conductores — top 20 conductores por ingreso
4. usuarios ⋈ viajes ⋈ calificaciones — satisfacción por distrito del pasajero
- **Vistas:** `v_ingreso_hora_distrito` (viajes finalizados por distrito y hora) y `v_rating_conductor` (conductores ⋈ calificaciones).
- Athena ejecuta **una sentencia a la vez** (pegar dos da "Only one sql statement is allowed").

---

## 8. Infraestructura AWS

**Cuenta:** Learner Lab `161661297601`, región `us-east-1`, rol `voclabs`. Credenciales rotan cada sesión.

### 8.1 Red
| Recurso | Valor |
|---|---|
| VPC | `transporte-prod-vpc` (`vpc-0ee81c3dc45b747ac`), 10.0.0.0/16 |
| Subred pública A | `transporte-prod-subred-publica-a` 10.0.1.0/24 (us-east-1a) |
| Subred pública B | `transporte-prod-subred-publica-b` 10.0.3.0/24 (us-east-1b) |
| Subred privada | `transporte-prod-subred-privada` 10.0.2.0/24 (sin IP pública automática) |
| NAT Gateway | Solo para que `mv-bd` salga a internet (instalar Docker, bajar imágenes). **Se borra para ahorrar** (~US$1/día) |

### 8.2 Máquinas (EC2, t3.small, Amazon Linux 2023)
| Nombre | ID | IP privada | Rol |
|---|---|---|---|
| mv-prod-a | `i-0283efbd9a2b36b14` | 10.0.1.232 | 5 MS · `LabInstanceProfile` · SSM |
| mv-prod-b | `i-0a226e504a89499e7` | 10.0.3.87 | 5 MS · `LabInstanceProfile` · SSM |
| mv-bd | `i-0a90d24395bdbf3af` | 10.0.2.85 | Postgres + MySQL + Mongo (Docker) |
| mv-ingesta | `i-024fc0064af9d9492` | 10.0.1.37 | Contenedores de ingesta |

Las IP públicas cambian en cada reinicio; las privadas y los datos (EBS) persisten.

### 8.3 Seguridad
- `transporte-prod-sg`: 8001–8005 desde el SG del ALB y de sí mismo; 22 desde las IP del equipo (`ip_equipo_cidr`).
- `transporte-bd-sg`: 5432, 3306, 27017 y 22 **solo desde `transporte-prod-sg`** (prod e ingesta).
- `transporte-alb-sg`: SG del ALB interno y del VPC Link.

### 8.4 Balanceador interno
`transporte-alb` (application, **Internal**), listener HTTP:80:

| Prioridad | Condición | Destino |
|---|---|---|
| 20 | `/ms2/*` | tg-ms2 (8002) |
| 30 | `/ms3/*` | tg-ms3 (8003) |
| 40 | `/ms4/*` | tg-ms4 (8004) |
| 50 | `/ms5/*` | tg-ms5 (8005) |
| default | resto (incluye `/ms1/*`) | tg-ms1 (8001) |

Cada target group tiene mv-prod-a y mv-prod-b (healthy).
*(Existe otro ALB `lb-prod` internet-facing en otra VPC: **no es de este proyecto**.)*

### 8.5 API Gateway
HTTP API **`transporte-gw`** (`h4sh35u9ac`), ruta única `ANY /{proxy+}`, integración `xt5o6bh` (VPC Load Balancer →
listener HTTP:80 de `transporte-alb`), **VPC Link `ixtm1r`** (`test-vpclink`), timeout 30 s, CORS `*`.

### 8.6 Terraform
`MS1-Usuarios-y-Conductores/transporte-infra/terraform/` (`vpc.tf`, `security_groups.tf`, `ec2.tf`, `variables.tf`, …).
Administra VPC, subredes, rutas, NAT, EIP, SG e instancias. **El ALB, el API Gateway y Amplify se crearon aparte.**
El rol `LabInstanceProfile` de prod-a/b ya está en el código (`var.perfil_instancia`).

⚠️ **No correr `terraform apply` sin revisar el plan:** hay drift de `user_data` (reiniciaría las 4 MV) y recrearía el NAT.

---

## 9. Despliegue en producción (dentro de mv-prod-a y mv-prod-b)

Archivo en la MV: `/home/ec2-user/docker-compose.prod.yml` (los 5 servicios; respaldos `docker-compose.prod.yml.bak-*`).

| Servicio | Imagen | Red | Origen |
|---|---|---|---|
| ms1 | `transporte-ms1-usuarios:2.0` | bridge (compose) | construida en la MV desde `~/MS1-Usuarios-y-Conductores` |
| ms2 | `enrique231/transporte-ms2:1.0.0` | bridge | Docker Hub |
| ms3 | `transporte-ms3:1.2` | bridge | construida en la MV desde `~/transporte-ms3-calificaciones` |
| ms4 | `ms4img` | host | construida desde `~/transporte-ms4` (carpeta de ec2-user) |
| ms5 | `ms5img` | host | construida desde `~/ms5-src` (copia enriquetorres-cell) |

La versión de referencia del compose y un script completo están en el repo de MS1:
`transporte-infra/docker-compose.prod.yml` y `transporte-infra/desplegar-prod.sh`.

**Acceso a las MV:** **SSM (Session Manager)**, no SSH (el SSH da timeout aunque la IP esté autorizada;
EC2 Instance Connect también falla porque usa el puerto 22). En consola: EC2 → instancia → Conectar → **Administrador de sesiones**.

**Redesplegar un MS desde la laptop (PowerShell, vía SSM):**
```powershell
$script = @'
cd /home/ec2-user
git -C MS1-Usuarios-y-Conductores pull -q
docker build -q -t transporte-ms1-usuarios:2.0 MS1-Usuarios-y-Conductores/transporte-ms1-usuarios
docker compose -f docker-compose.prod.yml up -d ms1
'@
$json = @{ commands = @($script -split "`r?`n" | Where-Object { $_ }); executionTimeout = @("600") } | ConvertTo-Json
[IO.File]::WriteAllText("$env:TEMP\ssm.json", $json)
aws ssm send-command --region us-east-1 --instance-ids i-0283efbd9a2b36b14 i-0a226e504a89499e7 --document-name AWS-RunShellScript --parameters "file://$env:TEMP\ssm.json" --query Command.CommandId --output text
```
- SSM corre como **root**: para `git pull` en carpetas de ec2-user usar `sudo -u ec2-user git -C <carpeta> pull`.
- MS3: `git -C transporte-ms3-calificaciones pull` → `docker build -t transporte-ms3:1.2 …` → `up -d ms3`.
- MS4 / MS5: `docker build -t ms4img transporte-ms4` (o `ms5img ms5-src/ms5`) → `docker compose … up -d ms4` (o `ms5`).

---

## 10. Operación del lab

**Encender (cada sesión):**
1. Learner Lab → **Start Lab** (círculo verde).
2. Credenciales: AWS Details → AWS CLI → pegar en `notepad "$HOME\.aws\credentials"` (si aparece `voc-cancel-cred`, son las de la sesión anterior).
3. Prender las MV:
```powershell
$ids = aws ec2 describe-instances --filters "Name=tag:Name,Values=mv-prod-a,mv-prod-b,mv-bd,mv-ingesta" "Name=instance-state-name,Values=stopped" --query "Reservations[].Instances[].InstanceId" --output text; if ($ids) { aws ec2 start-instances --instance-ids $ids.Split(); aws ec2 wait instance-running --instance-ids $ids.Split() }
```
4. Esperar ~2 min (arrancan contenedores y el ALB marca los destinos sanos). Mientras tanto, lo normal es **503**.
5. Verificar: `1..5 | % { curl.exe -s "https://h4sh35u9ac.execute-api.us-east-1.amazonaws.com/ms$_/health" }`.

**Apagar (al terminar):**
```powershell
$ids = aws ec2 describe-instances --filters "Name=tag:Name,Values=mv-prod-a,mv-prod-b,mv-bd,mv-ingesta" "Name=instance-state-name,Values=running" --query "Reservations[].Instances[].InstanceId" --output text; aws ec2 stop-instances --instance-ids $ids.Split()
```
Se dejan el ALB (~US$0.5/día) y el API Gateway para no reconstruirlos. MS5 ya no necesita credenciales nuevas.

---

## 11. Datos

| BD | Tabla / colección | Registros |
|---|---|---|
| PostgreSQL `usuarios_db` | usuarios · conductores · vehiculos | 20 000 · 600 · 600 |
| MySQL `viajes_db` | viajes · tarifas · paradas | 25 000 · 4 · (paradas de viajes) |
| MongoDB `calificaciones_db` | calificaciones · reportes | 22 000 · 300 |

IDs útiles para demos: usuario **695** (tiene viajes), conductor **101**, viaje **18000** (tiene calificación).

---

## 12. Repositorios

| Componente | Repositorio |
|---|---|
| MS1 + Infra (Terraform) + Postman | https://github.com/Limepal/MS1-Usuarios-y-Conductores |
| MS2 | https://github.com/S1nk0-0/transporte-ms2-viajes |
| MS3 | https://github.com/enriquetorres-cell/transporte-ms3-calificaciones |
| MS4 | https://github.com/enriquetorres-cell/transporte-ms4 |
| MS5 (original) | https://github.com/DnCuadros23/transporte-ms5-analitica |
| MS5 (copia desplegada) | https://github.com/enriquetorres-cell/transporte-ms5-analitica |
| Frontend | https://github.com/enriquetorres-cell/transporte-frontend |

**Postman:** `MS1-Usuarios-y-Conductores/postman/transporte.postman_collection.json` (variable `{{base}}` = API Gateway).
Incluye reglas de MS1, el POST de MS2 que da 422, MS4 y las vistas de MS5.

---

## 14. Cambios de esta etapa

- **MS1 reimplementado como lógica de negocio** (sin CRUD), con consumo a MS3, tests y Swagger documentado (v2.0.0).
- **MS2 → MS1 activado en producción** (`VALIDAR_CON_MS1=true` + `MS1_URL`).
- **Bug MS4 filtros:** mandaba `pasajero_id`/`conductor_id` y MS2 los ignoraba → ahora camelCase.
- **Bug MS4 detalle completo:** nunca traía la calificación → MS3 ganó el filtro `?viaje_id=` y MS4 lo usa.
- **MS3:** `/ms3/openapi.json` y Swagger completo (servers reales, esquemas, errores).
- **MS5:** rol de la MV en vez de credenciales; copia sincronizada con prod; **inyección SQL corregida** en `?distrito=`;
  endpoints sobre las 2 vistas; `consultas.sql` corregido (base `transporte_urbano`, 4 JOIN reales).
- **Ingesta:** sube directo a `catalogo/<tabla>/`; contraseña fuera del código.
- **Producción:** MS4 y MS5 pasaron a `docker compose` (los 5 MS bajo compose).
- **Guía de despliegue reproducible** en el README principal del repo de MS1.
- **Frontend:** rediseño VÍA, búsquedas en MS2/MS3, pestaña de reglas MS1, vistas de Athena en Analítica.
- **Infra:** `LabInstanceProfile` en prod-a/b (SSM + credenciales de MS5); Terraform actualizado.

---

## 15. Profundización técnica

### 15.1 Recorrido de una petición (ejemplo real: detalle completo de un viaje)

`GET https://h4sh35u9ac.execute-api.us-east-1.amazonaws.com/ms4/viajes/18000/detalle-completo`

| # | Salto | Qué pasa técnicamente |
|---|---|---|
| 1 | Navegador → API Gateway | TLS termina en el gateway (HTTPS). Petición *cross-origin* desde `*.amplifyapp.com`: el gateway responde el *preflight* `OPTIONS` y agrega `Access-Control-Allow-Origin: *`. |
| 2 | API Gateway → VPC Link | La ruta `ANY /{proxy+}` casa cualquier path; la integración `xt5o6bh` (tipo *private*, `HTTP_PROXY`) reenvía método, path y query **sin transformar**. El VPC Link `ixtm1r` tiene ENIs en las subredes públicas A/B con `transporte-alb-sg`. Timeout del gateway: 30 s. |
| 3 | VPC Link → ALB interno | Llega al listener HTTP:80 de `transporte-alb` (sin TLS dentro de la VPC). Regla prioridad 40 `/ms4/*` → `tg-ms4`. |
| 4 | ALB → MV | Balanceo *round robin* entre mv-prod-a y mv-prod-b, puerto 8004. Solo destinos *healthy* (health check `GET /ms4/health` cada 30 s, timeout 5 s). |
| 5 | MS4 (FastAPI) | `httpx.AsyncClient`, llamadas **secuenciales** con timeout 5 s y 1 reintento cada una: `GET localhost:8002/ms2/viajes/18000` → `GET localhost:8001/ms1/usuarios/{pasajero_id}` → `GET localhost:8001/ms1/conductores/{conductor_id}` → `GET localhost:8003/ms3/calificaciones?viaje_id=18000&limit=1`. |
| 6 | MS1 / MS2 / MS3 → mv-bd | Cada MS consulta **su propia** BD en `10.0.2.85` (5432 / 3306 / 27017), permitido solo porque el origen es `transporte-prod-sg`. |
| 7 | Respuesta | MS4 compone `{viaje, pasajero, conductor, calificacion, advertencias}`; si un MS falla, su bloque va en `null` y se agrega `"msN no disponible"`. Vuelve por ALB → VPC Link → gateway → navegador. |

### 15.2 Matriz de puertos, redes y variables

| Servicio | Puerto | Red Docker | Health (ALB) | Variables de entorno clave |
|---|---|---|---|---|
| ms1 | 8001 | bridge `ec2-user_default` | `/ms1/health` | `POSTGRES_URL`, `BD_HOST`, `PORT`, `MS3_URL=http://ms3:8003/ms3`, `API_GATEWAY_URL` |
| ms2 | 8002 | bridge | `/ms2/health` | `BD_HOST`, `BD_PORT`, `BD_NOMBRE`, `BD_USUARIO`, `BD_CLAVE`, `VALIDAR_CON_MS1=true`, `MS1_URL=http://ms1:8001`, `PUBLIC_URL` |
| ms3 | 8003 | bridge | `/ms3/health` (+ healthcheck Docker) | `MONGO_URI`, `PREFIX=/ms3`, `PORT`, `VALIDAR_VIAJE=false` |
| ms4 | 8004 | **host** | `/ms4/health` | `MS1_URL`, `MS2_URL`, `MS3_URL` (localhost:800N) |
| ms5 | 8005 | **host** | `/ms5/health` | `GLUE_DATABASE`, `ATHENA_OUTPUT`, `AWS_REGION` (credenciales por IMDS) |

- **Por qué dos redes:** ms1–ms3 comparten la red *bridge* del compose y se resuelven por nombre de servicio
  (`ms1`, `ms3`). ms4 usa `host` para llegar a los tres por `localhost:800N`; ms5 usa `host` para alcanzar el
  **IMDSv2** (`169.254.169.254`) sin el salto extra de red que impide el *hop limit* 1.
- Todos con `restart: unless-stopped`: vuelven solos al prender la MV.

### 15.3 Modelo de datos (resumen del DDL)

**PostgreSQL · `usuarios_db` (MS1)**
```sql
usuarios    (id SERIAL PK, nombre, apellido, email UNIQUE, telefono, distrito, fecha_nacimiento DATE,
             fecha_registro TIMESTAMP DEFAULT NOW(), activo BOOLEAN DEFAULT TRUE)
conductores (id SERIAL PK, nombre, apellido, email UNIQUE, telefono, nro_licencia UNIQUE, distrito_base,
             fecha_ingreso DATE, calificacion_promedio NUMERIC(3,2) DEFAULT 0, activo BOOLEAN)
vehiculos   (id SERIAL PK, conductor_id INT REFERENCES conductores(id) ON DELETE CASCADE, placa UNIQUE,
             marca, modelo, anio SMALLINT, color, capacidad SMALLINT DEFAULT 4, tipo_servicio DEFAULT 'estandar')
-- índices: vehiculos(conductor_id), usuarios(distrito), conductores(fecha_ingreso)
```

**MySQL · `viajes_db` (MS2)**
```sql
tarifas (id PK, tipo_servicio CHECK IN ('economico','estandar','confort','xl'), tarifa_base, costo_por_km,
         costo_por_minuto, multiplicador_hora_pico DECIMAL(10,2), activa)
viajes  (id AUTO_INCREMENT PK, pasajero_id, conductor_id, vehiculo_id,           -- referencias lógicas a MS1
         tarifa_id FK → tarifas, estado CHECK (solicitado|en_curso|finalizado|cancelado),
         metodo_pago CHECK (efectivo|tarjeta|billetera), distrito_origen, distrito_destino, direcciones,
         distancia_km DECIMAL(6,2), duracion_min, monto_total DECIMAL(10,2), solicitado_en, iniciado_en, finalizado_en)
paradas (id BIGINT PK, viaje_id FK → viajes ON DELETE CASCADE, orden, distrito, direccion, latitud, longitud,
         llegada_en, UNIQUE(viaje_id, orden))
-- monto = (base + km*costo_km + min*costo_min) * multiplicador_hora_pico  (se calcula al finalizar)
```

**MongoDB · `calificaciones_db` (MS3)**
```js
calificaciones { _id, viaje_id (unique), pasajero_id, conductor_id, rating 1..5, tags[enum], comentario ≤500,
                 idioma, distrito_origen, distrito_destino, anonimo,
                 respuesta_conductor { texto, fecha }, moderacion { estado, reportes }, creado_en, actualizado_en }
reportes       { _id, calificacion_id → calificaciones._id, reportado_por, motivo[enum], detalle, estado }
// índices: viaje_id único · pasajero_id · conductor_id · texto(comentario, default_language: "spanish")
```

**Referencias entre bases:** `viajes.pasajero_id/conductor_id/vehiculo_id → MS1` y
`calificaciones.viaje_id → MS2` son **lógicas** (no hay FK física porque cada MS tiene su BD); se validan por API.

### 15.4 Patrones de resiliencia

| Patrón | Dónde | Implementación |
|---|---|---|
| Timeout + 1 reintento | MS1→MS3, MS2→MS1, MS4→todos | 5 s por llamada (`httpx` / `RestClient`) |
| Degradación elegante | MS1, MS2, MS4 | Si el MS remoto cae: se sigue sin ese dato y se agrega `advertencias`; **nunca 500 por culpa de otro MS** |
| Corte temprano | MS2 | Si la validación del pasajero agota timeout, no intenta la del conductor (peor caso ~10 s, no ~20 s) |
| Validación defensiva | MS4 | Verifica que la calificación devuelta sea del mismo `viaje_id` antes de usarla |
| Alta disponibilidad | ALB | 2 réplicas en 2 AZ; health checks sacan del pool a la MV caída |
| Auto-recuperación | Docker | `restart: unless-stopped` |
| Tope de fan-out | MS1 `/disponibles` | Máximo 50 candidatos → máximo 50 consultas a MS3, en paralelo con `ThreadPoolExecutor(10)` |

### 15.5 Seguridad

- **Superficie pública mínima:** solo API Gateway (HTTPS) y Amplify. ALB interno, BD en subred privada, SG encadenados por **ID de grupo** (no por CIDR).
- **Principio de menor privilegio en red:** `transporte-bd-sg` solo acepta de `transporte-prod-sg`; puertos 8001–8005 solo del ALB.
- **Credenciales:** MS5 usa el rol de la instancia (IMDSv2, credenciales temporales rotadas por AWS); nada de llaves en variables ni en `~/.aws`. Contraseñas de BD por variables de entorno (`.env`, no versionado).
- **Validación de entrada:** Pydantic (MS1, MS4), Bean Validation (MS2), Mongoose (MS3); MS5 valida `distrito` con regex (corrige una **inyección SQL** en Athena) y `minimo` como entero.
- **Administración sin SSH:** SSM Session Manager / Run Command (auditable, sin abrir el puerto 22 a internet).

### 15.6 Estructura de código de MS1 (referencia de diseño)

```
app/
├── main.py        # FastAPI, openapi_tags, handlers de error → {error, detalle}
├── config.py      # variables de entorno (Contrato Cero + MS3_URL)
├── database.py    # engine + sesión SQLAlchemy
├── models.py      # ORM Usuario / Conductor / Vehiculo
├── schemas.py     # Pydantic de respuesta (con ejemplos para Swagger) + errores(…)
├── reglas.py      # ★ reglas de negocio puras: sin BD ni HTTP → testeables en aislamiento
├── clientes.py    # cliente HTTP a MS3 (timeout, reintento, paralelo)
└── routers/       # capa delgada: leer BD → aplicar regla → responder
tests/             # test_reglas.py (sin BD) + integración (Postgres en Docker, MS3 con monkeypatch)
```
Separación **dominio (reglas) / infraestructura (BD, HTTP) / transporte (routers)**: la lógica no depende de FastAPI
ni de SQLAlchemy.

### 15.7 SQL de Athena (tal como está en `athena/consultas.sql`)

```sql
-- 1) viajes ⋈ vehiculos ⋈ tarifas
SELECT ve.tipo_servicio, ve.marca, t.tarifa_base, count(*) AS viajes,
       round(avg(v.monto_total),2) AS ticket_promedio, round(sum(v.monto_total),2) AS ingreso_total
FROM transporte_urbano.viajes v
JOIN transporte_urbano.vehiculos ve ON v.vehiculo_id = ve.id
JOIN transporte_urbano.tarifas t    ON v.tarifa_id  = t.id
WHERE v.estado = 'finalizado'
GROUP BY ve.tipo_servicio, ve.marca, t.tarifa_base ORDER BY ingreso_total DESC;

-- 2) calificaciones ⋈ viajes
SELECT v.distrito_origen AS distrito, count(*) AS total_calificaciones, round(avg(c.rating),2) AS rating_promedio
FROM transporte_urbano.calificaciones c JOIN transporte_urbano.viajes v ON c.viaje_id = v.id
GROUP BY v.distrito_origen ORDER BY rating_promedio DESC;

-- 3) viajes ⋈ conductores
SELECT co.id AS conductor_id, co.nombre, co.apellido, co.distrito_base, count(*) AS viajes,
       round(sum(v.monto_total),2) AS ingreso_total
FROM transporte_urbano.viajes v JOIN transporte_urbano.conductores co ON v.conductor_id = co.id
WHERE v.estado = 'finalizado'
GROUP BY co.id, co.nombre, co.apellido, co.distrito_base ORDER BY ingreso_total DESC LIMIT 20;

-- 4) usuarios ⋈ viajes ⋈ calificaciones
SELECT u.distrito AS distrito_pasajero, count(DISTINCT v.id) AS viajes,
       round(avg(c.rating),2) AS rating_promedio, round(avg(v.monto_total),2) AS ticket_promedio
FROM transporte_urbano.usuarios u
JOIN transporte_urbano.viajes v         ON v.pasajero_id = u.id
JOIN transporte_urbano.calificaciones c ON c.viaje_id    = v.id
GROUP BY u.distrito ORDER BY rating_promedio DESC;

-- Vistas
CREATE OR REPLACE VIEW transporte_urbano.v_ingreso_hora_distrito AS
SELECT distrito_origen AS distrito, hour(CAST(iniciado_en AS timestamp)) AS hora, count(*) AS viajes,
       round(avg(monto_total), 2) AS ingreso_promedio
FROM transporte_urbano.viajes WHERE estado = 'finalizado'
GROUP BY distrito_origen, hour(CAST(iniciado_en AS timestamp));

CREATE OR REPLACE VIEW transporte_urbano.v_rating_conductor AS
SELECT co.id AS conductor_id, co.nombre, co.apellido, count(cal.viaje_id) AS calificaciones,
       round(avg(cal.rating), 2) AS rating_promedio
FROM transporte_urbano.conductores co
JOIN transporte_urbano.calificaciones cal ON cal.conductor_id = co.id
GROUP BY co.id, co.nombre, co.apellido;
```

### 15.8 Decisiones técnicas y trade-offs

| Decisión | Por qué | Costo / alternativa |
|---|---|---|
| Database-per-service | Aislamiento y 3 motores distintos (requisito) | Sin JOIN entre BD: se resuelve por API (MS4) o en el data lake (Athena) |
| Gateway con una ruta `{proxy+}` + ruteo en el ALB | Una sola integración; agregar un MS = una regla del ALB | El ruteo queda en dos capas (gateway y ALB) |
| ALB interno + VPC Link | Backend nunca expuesto; cumple "balanceador privado" | VPC Link y ALB cuestan aunque no haya tráfico |
| Rating leído de MS3 en vez de copiarlo a MS1 | Una sola fuente de verdad, sin sincronización | Latencia y dependencia de MS3 (mitigado con timeout + advertencias) |
| MS1 sin cambios de esquema | La ingesta hace `SELECT *` → el catálogo Glue no se desalinea | Estados como "suspendido" reutilizan la columna `activo` |
| Rol de instancia para MS5 | Credenciales temporales que AWS renueva; nada de llaves en el código | Depende de IMDS (por eso MS5 va en red `host`) |
| Imágenes construidas en la MV | No depende de cuentas de Docker Hub de terceros | Build más lento en t3.small (MS2 con Maven) |
| SSM en vez de SSH | Sin puerto 22 abierto a internet, auditable | Requiere el rol en la instancia |
| Frontend sin framework | Despliegue estático trivial en Amplify, sin build | Más código manual en `app.js` |
| Data lake en S3 + Glue + Athena | Analítica sin tocar las BD transaccionales; pago por consulta | Datos tan frescos como la última ingesta |

---

## 16. Pendientes, riesgos y gotchas

| Tema | Detalle |
|---|---|
| Entregables | Diagrama de arquitectura (draw.io), informe y PPT — a cargo del equipo |
| MS2 Swagger | Mejoras (snake_case, servers, errores) **solo locales**: requieren push al repo de S1nk0-0 y rebuild de la imagen |
| Contraseña de BD | Quedó en el historial de git de MS5 (commit `293094f`). Rotarla **después** de la exposición |
| Terraform drift | `apply` reiniciaría las 4 MV y recrearía el NAT |
| SSH | No funciona; usar SSM |
| IP públicas | Cambian al reiniciar; siempre usar el API Gateway |
| Swagger con error "Failed to load API definition" | MV apagadas o caché: prender y Ctrl+F5 |
| PowerShell 5.1 | Sin `&&`; `curl` es alias (usar `curl.exe`); `Invoke-RestMethod` rompe tildes si la respuesta no trae charset |
| Git Bash + AWS CLI | `export MSYS_NO_PATHCONV=1` antes de comandos con rutas `/` |
| Athena | Una sentencia por ejecución |
| MS1 `/vehiculos` | Devuelve **lista**, no `{items}` |
| CORS | Solo en el API Gateway; ponerlo también en un MS duplica cabeceras |

---

*Transporte Urbano · CS2032 Cloud Computing · Proyecto Parcial 2026-2*
