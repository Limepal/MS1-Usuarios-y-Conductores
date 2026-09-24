# Transporte Urbano · Guía de despliegue completo en AWS

Proyecto Parcial · **CS2032 Cloud Computing** (2026-2).
Plataforma de transporte urbano con **5 microservicios + frontend + data lake analítico**, desplegada en
**AWS Academy Learner Lab**. Esta guía permite **reproducir todo el proyecto desde cero** en una cuenta
nueva, paso a paso.

> Tiempo estimado: 60–90 minutos (la mayor parte es esperar a que AWS cree recursos y a que se construyan imágenes).

---

## Arquitectura

```
Navegador ── Frontend (AWS Amplify)
                 │ HTTPS
                 ▼
     API Gateway (HTTP API)  ruta ANY /{proxy+}  · CORS
                 │ VPC Link
                 ▼
     ALB INTERNO (listener :80, reglas /ms1/* … /ms5/*)
          ┌──────┴──────┐
     mv-prod-a      mv-prod-b          ← subredes públicas A/B · 5 MS en docker compose
          └──────┬──────┘
               mv-bd                   ← subred PRIVADA · PostgreSQL + MySQL + MongoDB
                 ▲ pull 100 %
            mv-ingesta ──► S3 ──► Glue (crawler) ──► Athena ◄── MS5
```

| MS | Qué hace | Stack | BD | Repo |
|---|---|---|---|---|
| MS1 | Usuarios y conductores · reglas de negocio · consume MS3 | FastAPI | PostgreSQL | este repo (`transporte-ms1-usuarios/`) |
| MS2 | Viajes y pagos · consume MS1 | Spring Boot | MySQL | [transporte-ms2-viajes](https://github.com/S1nk0-0/transporte-ms2-viajes) |
| MS3 | Calificaciones y reportes | Express | MongoDB | [transporte-ms3-calificaciones](https://github.com/enriquetorres-cell/transporte-ms3-calificaciones) |
| MS4 | Orquestador (sin BD): une MS1+MS2+MS3 | FastAPI | — | [transporte-ms4](https://github.com/enriquetorres-cell/transporte-ms4) |
| MS5 | Analítica con Athena + ingesta | FastAPI + boto3 | Athena/S3 | [transporte-ms5-analitica](https://github.com/enriquetorres-cell/transporte-ms5-analitica) |
| Front | Backoffice web | HTML/CSS/JS | — | [transporte-frontend](https://github.com/enriquetorres-cell/transporte-frontend) |

**Contenido de este repo**

```
README.md                    ← esta guía
CONTEXTO-PROYECTO.md         ← documentación técnica completa del proyecto
transporte-ms1-usuarios/     ← código de MS1 (ver su README)
transporte-infra/
├── terraform/               ← VPC, subredes, NAT, security groups y las 4 MV
├── init/                    ← esquemas iniciales de PostgreSQL, MySQL y MongoDB
├── docker-compose.bd.yml    ← las 3 bases (corre en mv-bd)
├── docker-compose.prod.yml  ← los 5 microservicios (corre en mv-prod-a y mv-prod-b)
├── desplegar-prod.sh        ← clona los repos, construye las imágenes y levanta todo
└── .env.example             ← variables (contraseñas, IP de la BD, bucket, API Gateway)
postman/                     ← colección de Postman con todos los endpoints
```

---

## Paso 0 · Requisitos y variables

1. **AWS Academy Learner Lab** iniciado (círculo verde). Ya trae el rol `LabRole` y el perfil `LabInstanceProfile`.
2. En tu computadora: **AWS CLI v2**, **Terraform ≥ 1.5**, **Git** y una terminal **bash**
   (Linux, macOS o Git Bash en Windows).
3. Credenciales del lab: *AWS Details → AWS CLI → Show* → pegarlas en `~/.aws/credentials`. Verificar:

```bash
export AWS_DEFAULT_REGION=us-east-1
aws sts get-caller-identity
```

4. Elegir un **nombre único** para el bucket y una **clave** para las bases (se usan en varios pasos):

```bash
export BUCKET=transporte-datalake-$RANDOM     # anótalo
export CLAVE='CambiaEstaClave123'              # la misma para app_ms1, app_ms2 y app_ms3
```

> Las máquinas se administran con **AWS Systems Manager (Session Manager)**, no con SSH:
> consola → **EC2 → Instancias** → marcar la MV → **Conectar → Administrador de sesiones → Conectar**.
> En cada sesión, ejecutar primero `sudo su - ec2-user`.

---

## Paso 1 · Red y máquinas virtuales (Terraform)

```bash
git clone https://github.com/Limepal/MS1-Usuarios-y-Conductores.git
cd MS1-Usuarios-y-Conductores/transporte-infra/terraform

AMI=$(aws ssm get-parameters --names /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 \
      --query 'Parameters[0].Value' --output text)

terraform init
terraform apply -var "ami_id=$AMI" -var 'par_de_claves=' \
                -var "ip_equipo_cidr=[\"$(curl -s https://checkip.amazonaws.com)/32\"]"
terraform output
```

Crea: VPC `10.0.0.0/16`, 2 subredes públicas (us-east-1a / us-east-1b), 1 subred **privada**, Internet
Gateway, **NAT Gateway** (para que `mv-bd` descargue Docker e imágenes sin tener IP pública), 3 security
groups (`alb`, `prod`, `bd`) y las 4 MV `t3.small` con Docker, Docker Compose y el rol `LabInstanceProfile`.

**Anotar** `ip_privada_mv_bd` (la usan los pasos 2, 3 y 4).

**Verificar** (esperar ~3 min a que arranquen): las 4 MV deben aparecer en SSM.

```bash
aws ssm describe-instance-information --query "InstanceInformationList[].[InstanceId,PingStatus]" --output table
```

---

## Paso 2 · Bases de datos en `mv-bd` (subred privada)

Session Manager → **mv-bd** → `sudo su - ec2-user` y luego (reemplazar la clave):

```bash
sudo dnf install -y git
git clone https://github.com/Limepal/MS1-Usuarios-y-Conductores.git
cd MS1-Usuarios-y-Conductores/transporte-infra

cat > .env <<'EOF'
POSTGRES_PASS=CambiaEstaClave123
MYSQL_PASS=CambiaEstaClave123
MONGO_APP_PASS=CambiaEstaClave123
MYSQL_ROOT_PASS=RootClave123
MONGO_ROOT_PASS=RootClave123
EOF

docker compose -f docker-compose.bd.yml up -d
sleep 30 && docker compose -f docker-compose.bd.yml ps     # los 3 en "healthy"
```

Los esquemas se crean solos desde `init/` la primera vez:
PostgreSQL (`usuarios`, `conductores`, `vehiculos`), MySQL (`tarifas`, `viajes`, `paradas`) y MongoDB
(usuario `app_ms3`, colecciones e índices, incluido el índice de texto en español).

---

## Paso 3 · Cargar los datos de prueba (≥ 20 000 registros por base)

Las bases son privadas: los scripts se corren **desde una MV de producción**.
Session Manager → **mv-prod-a** → `sudo su - ec2-user` (reemplazar `10.0.2.x` y la clave):

```bash
sudo dnf install -y git python3-pip
git clone https://github.com/enriquetorres-cell/transporte-ms3-calificaciones.git
cd transporte-ms3-calificaciones/seed
pip3 install --user -r requirements.txt

export BD=10.0.2.x
export CLAVE='CambiaEstaClave123'
export PG_DSN="host=$BD dbname=usuarios_db user=app_ms1 password=$CLAVE"
export MYSQL_HOST=$BD MYSQL_USER=app_ms2 MYSQL_PASS=$CLAVE MYSQL_DB=viajes_db
export MONGO_URI="mongodb://app_ms3:$CLAVE@$BD:27017/calificaciones_db?authSource=calificaciones_db"

python3 seed_postgres.py   # 1.º  20 000 usuarios · 600 conductores · 600 vehículos
python3 seed_mysql.py      # 2.º  25 000 viajes (referencian los IDs de MS1)
python3 seed_mongo.py      # 3.º  22 000 calificaciones (una por viaje finalizado)
```

---

## Paso 4 · Microservicios en `mv-prod-a` y `mv-prod-b`

Repetir **en las dos** MV: Session Manager → `sudo su - ec2-user` (reemplazar `10.0.2.x`, la clave y el bucket):

```bash
sudo dnf install -y git
git clone https://github.com/Limepal/MS1-Usuarios-y-Conductores.git
cp MS1-Usuarios-y-Conductores/transporte-infra/{docker-compose.prod.yml,desplegar-prod.sh} ~/
cd ~

cat > .env <<'EOF'
POSTGRES_PASS=CambiaEstaClave123
MYSQL_PASS=CambiaEstaClave123
MONGO_APP_PASS=CambiaEstaClave123
BD_HOST=10.0.2.x
S3_BUCKET=transporte-datalake-xxxxx
EOF

chmod +x desplegar-prod.sh
./desplegar-prod.sh
```

`desplegar-prod.sh` clona los 5 repos, **construye las imágenes en la MV** y levanta todo con
`docker compose`. La primera vez tarda **10–15 min** (MS2 compila con Maven). Al final imprime:

```
ms1: {"status":"ok","servicio":"ms1"}   …   ms5: {"status":"ok","servicio":"ms5"}
```

| Servicio | Puerto | Red | Consume a |
|---|---|---|---|
| ms1 | 8001 | bridge | MS3 (`http://ms3:8003/ms3`) |
| ms2 | 8002 | bridge | MS1 (`http://ms1:8001`) |
| ms3 | 8003 | bridge | — |
| ms4 | 8004 | host | MS1, MS2, MS3 (`localhost`) |
| ms5 | 8005 | host | Athena (credenciales del rol de la MV) |

---

## Paso 5 · Balanceador interno (ALB)

Desde tu computadora, junto a este repo (usa los scripts del repo de MS2 y los outputs de Terraform):

```bash
cd ../../..                                   # carpeta que contiene MS1-Usuarios-y-Conductores
git clone https://github.com/S1nk0-0/transporte-ms2-viajes.git
cd transporte-ms2-viajes
./scripts/00-infra-env.sh ../MS1-Usuarios-y-Conductores/transporte-infra/terraform
./scripts/03-balanceador.sh
source infra.env && echo "$ALB_DNS  $LISTENER_ARN"
```

Crea el ALB **interno** `transporte-alb` en las 2 subredes públicas, los target groups `tg-ms1` … `tg-ms5`
(puertos 8001–8005, health check `GET /msN/health` cada 30 s) con mv-prod-a y mv-prod-b registradas, y el
listener `:80` con reglas por path `/msN/*` → `tg-msN`.

**Verificar** (≈ 2 min): todos los destinos en `healthy`.

```bash
for tg in $TG_MS1 $TG_MS2 $TG_MS3 $TG_MS4 $TG_MS5; do
  aws elbv2 describe-target-health --target-group-arn $tg --query "TargetHealthDescriptions[].TargetHealth.State" --output text
done
```

---

## Paso 6 · API Gateway (HTTPS) + VPC Link

En la misma terminal del paso 5 (usa `infra.env`):

```bash
source infra.env

VPC_LINK=$(aws apigatewayv2 create-vpc-link --name transporte-vpclink \
  --subnet-ids $SUBNET_PUB_A $SUBNET_PUB_B --security-group-ids $SG_ALB \
  --query VpcLinkId --output text)
until [ "$(aws apigatewayv2 get-vpc-link --vpc-link-id $VPC_LINK --query VpcLinkStatus --output text)" = AVAILABLE ]; do sleep 15; done

API=$(aws apigatewayv2 create-api --name transporte-gw --protocol-type HTTP \
  --cors-configuration 'AllowOrigins=*,AllowMethods=*,AllowHeaders=*' --query ApiId --output text)

INT=$(aws apigatewayv2 create-integration --api-id $API --integration-type HTTP_PROXY \
  --integration-method ANY --connection-type VPC_LINK --connection-id $VPC_LINK \
  --integration-uri $LISTENER_ARN --payload-format-version 1.0 --query IntegrationId --output text)

aws apigatewayv2 create-route --api-id $API --route-key 'ANY /{proxy+}' --target integrations/$INT
aws apigatewayv2 create-stage --api-id $API --stage-name '$default' --auto-deploy

export API_URL=https://$API.execute-api.us-east-1.amazonaws.com
echo $API_URL
for n in 1 2 3 4 5; do curl -s $API_URL/ms$n/health; echo; done
```

Una sola ruta comodín (`ANY /{proxy+}`) reenvía todo al ALB privado; **el reparto por microservicio lo hace
el ALB**. El **CORS** se configura únicamente aquí (los microservicios no lo configuran).

*(Opcional)* para que el botón **Try it out** de Swagger apunte a tu gateway, agrega
`API_GATEWAY_URL=<API_URL>` al `.env` de mv-prod-a y mv-prod-b y ejecuta
`docker compose -f docker-compose.prod.yml up -d` en cada una.

---

## Paso 7 · Frontend en AWS Amplify

1. Hacer **fork** de [transporte-frontend](https://github.com/enriquetorres-cell/transporte-frontend) y en
   `config.js` cambiar `API_BASE` por tu `API_URL` (commit).
2. Consola → **AWS Amplify → Create new app → GitHub** → autorizar → elegir el fork, rama `main`.
3. Amplify detecta `amplify.yml` (sitio estático, sin build) → **Save and deploy**.
4. Abrir `https://main.<id>.amplifyapp.com` → **Entrar como Administrador**.

Cada `git push` a `main` vuelve a desplegar automáticamente.

---

## Paso 8 · Data lake: ingesta → S3 → Glue → Athena

**8.1 Bucket**

```bash
aws s3 mb s3://$BUCKET
```

**8.2 Ingesta** (3 contenedores, pull del 100 % de las 3 bases). Session Manager → **mv-ingesta** →
`sudo su - ec2-user` (reemplazar bucket, IP y clave):

```bash
sudo dnf install -y git
git clone https://github.com/enriquetorres-cell/transporte-ms5-analitica.git
cd transporte-ms5-analitica/ingesta
export S3_BUCKET=transporte-datalake-xxxxx BD_HOST=10.0.2.x BD_PASS='CambiaEstaClave123'
docker compose up --build
aws s3 ls s3://$S3_BUCKET/catalogo/ --recursive     # 8 archivos: uno por tabla
```

Las credenciales de S3 las da el rol de la MV (no hace falta pegar llaves).

**8.3 Catálogo de datos (Glue)** — desde tu computadora:

```bash
aws glue create-database --database-input Name=transporte_urbano
aws glue create-crawler --name transporte-crawler --role LabRole --database-name transporte_urbano \
  --targets "{\"S3Targets\":[{\"Path\":\"s3://$BUCKET/catalogo/\"}]}"
aws glue start-crawler --name transporte-crawler
until [ "$(aws glue get-crawler --name transporte-crawler --query Crawler.State --output text)" = READY ]; do sleep 20; done
aws glue get-tables --database-name transporte_urbano --query "TableList[].Name"   # 8 tablas
```

**8.4 Athena** — consola → **Athena → Query editor**:

1. *Settings* → **Query result location** = `s3://<BUCKET>/athena-results/`.
2. **Database** = `transporte_urbano`.
3. Abrir [`athena/consultas.sql`](https://github.com/enriquetorres-cell/transporte-ms5-analitica/blob/main/athena/consultas.sql)
   y ejecutar **una sentencia a la vez**: las 4 consultas con JOIN y los 2 `CREATE OR REPLACE VIEW`.

Con las vistas creadas, MS5 ya responde `GET /ms5/vistas/…` y la pestaña **Analítica** del frontend se llena.

---

## Paso 9 · Verificación final

```bash
for n in 1 2 3 4 5; do curl -s $API_URL/ms$n/health; echo; done
curl -s "$API_URL/ms1/conductores/101/elegibilidad"                       # MS1 consume MS3 (rating)
curl -s -X POST $API_URL/ms2/viajes -H 'Content-Type: application/json' \
  -d '{"pasajero_id":999999,"conductor_id":101,"vehiculo_id":101,"tarifa_id":2,"metodo_pago":"efectivo","distrito_origen":"Lince","distrito_destino":"Surco"}'
                                                                          # MS2 consume MS1 → 422
curl -s "$API_URL/ms4/viajes/18000/detalle-completo"                      # MS4 une MS1+MS2+MS3
curl -s "$API_URL/ms5/vistas/rating-conductor?limit=3"                    # MS5 lee una vista de Athena
```

| Qué | Dónde |
|---|---|
| Swagger UI de cada MS | `$API_URL/ms1/docs` … `$API_URL/ms5/docs` |
| Postman | importar [`postman/transporte.postman_collection.json`](postman/transporte.postman_collection.json) y cambiar la variable `base` por `API_URL` |
| Frontend | URL de Amplify |

---

## Operación diaria (Learner Lab)

Al cerrar la sesión del lab, AWS **detiene las MV**; los datos (EBS) se conservan.

```bash
# Encender (esperar ~2 min: mientras tanto el API responde 503)
ids=$(aws ec2 describe-instances --filters "Name=tag:Name,Values=mv-prod-a,mv-prod-b,mv-bd,mv-ingesta" \
      "Name=instance-state-name,Values=stopped" --query "Reservations[].Instances[].InstanceId" --output text)
aws ec2 start-instances --instance-ids $ids

# Apagar
ids=$(aws ec2 describe-instances --filters "Name=tag:Name,Values=mv-prod-a,mv-prod-b,mv-bd,mv-ingesta" \
      "Name=instance-state-name,Values=running" --query "Reservations[].Instances[].InstanceId" --output text)
aws ec2 stop-instances --instance-ids $ids
```

Los contenedores vuelven solos (`restart: unless-stopped`). Para ahorrar créditos, el NAT Gateway
se puede eliminar cuando `mv-bd` ya tiene Docker y sus imágenes.

**Eliminar todo:** borrar la app de Amplify, el API (`aws apigatewayv2 delete-api --api-id $API`), el VPC Link,
el ALB y sus target groups, el crawler y la base de Glue, vaciar y borrar el bucket, y por último
`terraform destroy` en `transporte-infra/terraform`.

---

## Problemas comunes

| Síntoma | Causa y solución |
|---|---|
| `503` en el API Gateway | Las MV están apagadas o arrancando: esperar 2 min |
| Swagger: "Failed to load API definition" | MV apagadas o caché del navegador: Ctrl+F5 |
| No aparece la MV en Session Manager | Esperar 2–3 min tras encenderla; revisar que tenga el rol `LabInstanceProfile` |
| MS5 responde 500 | Faltan las tablas/vistas en Glue/Athena (paso 8) o `S3_BUCKET` mal en el `.env` |
| Error de autenticación de Mongo | Usar `authSource=calificaciones_db` (ahí se crea `app_ms3`) |
| La ingesta no conecta | Las 3 claves de aplicación deben ser **iguales** (la ingesta usa una sola `BD_PASS`) |
| Athena: "Only one sql statement is allowed" | Ejecutar las sentencias de `consultas.sql` de a una |
| `credentials expired` / `voc-cancel-cred` | Nueva sesión del lab: volver a pegar las credenciales |

Documentación técnica detallada (endpoints, reglas de negocio, modelo de datos, seguridad y decisiones
técnicas): [`CONTEXTO-PROYECTO.md`](CONTEXTO-PROYECTO.md).
