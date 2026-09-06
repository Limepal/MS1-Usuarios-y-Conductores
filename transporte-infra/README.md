# transporte-infra

Infraestructura como código (IaC) compartida — **Fase 1 / Hito 1** (responsabilidad de P1).
Cubre exactamente el Contrato Cero v1.0 §9 y el Plan Maestro Fase 1.

## Contenido

```
terraform/
├── main.tf              # provider y bloques base
├── vpc.tf               # VPC 10.0.0.0/16 + subredes + IGW + NAT (opcional)
├── security_groups.tf   # sg-alb, sg-prod, sg-bd (reglas exactas del contrato)
├── ec2.tf               # mv-prod-a, mv-prod-b, mv-bd (+ user_data Docker)
├── variables.tf         # tipos de instancia, CIDR, IPs del equipo, etc.
└── outputs.tf           # IPs y SG resultantes
docker-compose.bd.yml    # PostgreSQL 16 que corre en mv-bd
.env.example
```

## Topología (Fase 1)

| Recurso | Subred | IP | Rol |
|---------|--------|----|-----|
| mv-prod-a | pública 10.0.1.0/24 | IP pública | correrá los 5 MS vía Docker Compose |
| mv-prod-b | pública 10.0.1.0/24 | IP pública | ídem (alta disponibilidad) |
| mv-bd | privada 10.0.2.0/24 | solo IP privada (10.0.2.x) | PostgreSQL 16 (hueco MySQL/Mongo P2/P3) |

Security Groups:
- **sg-alb**: 80/tcp entrante (se ajustará cuando exista el VPC Link del API Gateway).
- **sg-prod**: 8001–8005/tcp solo desde `sg-alb`; 22/tcp solo desde las IPs del equipo (`var.ip_equipo_cidr`).
- **sg-bd**: 5432/tcp, 3306/tcp, 27017/tcp solo desde `sg-prod`. **Ninguna** regla `0.0.0.0/0`.

## Aplicar con Terraform (cuenta de AWS Academy)

```bash
cd terraform
# 1) Configurar credenciales de AWS (variables de entorno o AWS CLI)
#    aws configure   (o export AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN)

# 2) Personalizar IP del equipo en variables.tf (ip_equipo_cidr) y par_de_claves
terraform init
# 3) Revisar el plan (no aplica nada)
terraform plan
# 4) Aplicar
terraform apply -auto-approve
# 5) Ver los IPs / SG
terraform output
```

> Con `crear_nat_gateway = true` (default) mv-bd puede instalar Docker y descargar
> imágenes vía NAT sin IP pública. Si no se quiere incurrir en el costo del NAT,
> se puede poner en `false` y proveer el paquete Docker por otro medio.

Nota: el estado queda local por simplicidad (ver comentario de backend S3 en `main.tf`).

## Despliegue paso a paso en AWS

Guía de ejecución completa del API de MS1 sobre la infraestructura de este repo.
Sigue el orden; cada fase tiene sus comandos de verificación.

### Fase 0 — Prerrequisitos

1. **Credenciales AWS activas** (AWS Academy o IAM). Verificar:
   ```bash
   aws sts get-caller-identity
   ```
2. **Herramientas locales**: Terraform ≥ 1.5, AWS CLI.
3. **Tu IP pública actual** (para el SG de SSH):
   ```bash
   curl ifconfig.me
   ```
4. **Par de claves EC2** (crear una vez en la región):
   ```bash
   aws ec2 create-key-pair --key-name transporte-key --query 'KeyMaterial' --output text > ~/.ssh/transporte-key.pem
   chmod 400 ~/.ssh/transporte-key.pem
   ```

### Fase 1 — Ajustar variables y aplicar Terraform

Editar `terraform/variables.tf`:
- `par_de_claves = "transporte-key"`
- `ip_equipo_cidr = ["<tu-ip-publica>/32"]`  (quitar el `0.0.0.0/0`)
- `ami_id` = AMI Amazon Linux 2023 de tu región (consultar vía SSM):
  ```bash
  aws ssm get-parameters --names /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 --query 'Parameters[0].Value' --output text
  ```

Aplicar:
```bash
cd terraform
terraform init
terraform plan             # revisar lo que se va a crear
terraform apply -auto-approve
terraform output           # IP pública mv-prod-a/b y IP privada mv-bd (10.0.2.x)
```

**Verificación Fase 1 (compuerta):**
- `mv-bd` no tiene IP pública ni reglas `0.0.0.0/0`; desde internet **no** responde.
- Desde tu PC, el puerto 5432 de cualquier IP pública de la VPC **debe fallar**.

### Fase 2 — Acceso SSH a mv-bd (privada)

`mv-bd` está en la subred privada y por defecto no acepta SSH desde internet.
Para configurarla se habilita temporalmente el puerto 22 desde la IP del equipo:

1. En `terraform/security_groups.tf`, dentro de `aws_security_group.bd`, añadir:
   ```hcl
   ingress {
     description = "SSH temporal del equipo para configuración"
     from_port   = 22
     to_port     = 22
     protocol    = "tcp"
     cidr_blocks = var.ip_equipo_cidr
   }
   ```
2. `terraform apply` (agrega la regla), configurar, y luego **retirar la regla** y
   aplicar de nuevo. Dejar el SG con solo 5432/3306/27017 desde `sg-prod` al final.

> Alternativa productiva (no usada por ahora): bastion en la subred pública + SSH
> Agent Forwarding.

### Fase 3 — PostgreSQL en mv-bd

```bash
# subir los repos a mv-bd
scp -i ~/.ssh/transporte-key.pem -r transporte-infra ec2-user@<ip-mv-bd>:~
scp -i ~/.ssh/transporte-key.pem -r transporte-ms1-usuarios ec2-user@<ip-mv-bd>:~
ssh -i ~/.ssh/transporte-key.pem ec2-user@<ip-mv-bd>

# dentro de mv-bd
cd ~/transporte-infra
cp .env.example .env
# editar .env y poner POSTGRES_PASS=<clave fuerte>
docker compose -f docker-compose.bd.yml up -d
docker compose -f docker-compose.bd.yml ps

# verificar las 3 tablas cargadas desde sql/schema.sql
docker exec bd_postgres psql -U app_ms1 -d usuarios_db -c '\dt'
```

> El compose monta `../transporte-ms1-usuarios/sql/schema.sql` en
> `docker-entrypoint-initdb.d`; ambos repos deben quedar adyacentes en `~/`.

### Fase 4 — Desplegar MS1 en las instancias prod

Repetir en **mv-prod-a** y **mv-prod-b** (SSH 22 habilitado desde la IP del equipo):

```bash
scp -i ~/.ssh/transporte-key.pem -r transporte-ms1-usuarios ec2-user@<ip-mv-prod-a>:~
ssh -i ~/.ssh/transporte-key.pem ec2-user@<ip-mv-prod-a>
cd ~/transporte-ms1-usuarios

# crear .env apuntando a la BD privada
cat > .env <<'EOF'
BD_HOST=10.0.2.10
POSTGRES_PASS=<la misma de mv-bd>
API_GATEWAY_URL=http://<ip-mv-prod-a>:8001
PORT=8001
EOF

# construir y lanzar
docker build -t ms1 .
docker run -d --name ms1 --env-file .env -p 8001:8001 ms1
```

> Deploy simple con `docker run` (decisión del equipo). No se suben los 5
> microservicios en esta fase; solo se deja MS1 corriendo. La imagen usa uvicorn
> en el puerto 8001 (`0.0.0.0`).

### Fase 5 — Validación final (compuerta Hito 1)

```bash
# health check (no toca BD)
curl http://<ip-mv-prod-a>:8001/ms1/health
# → {"status":"ok","servicio":"ms1"}

# Swagger / OpenAPI
curl http://<ip-mv-prod-a>:8001/ms1/docs

# prueba de conexión real a PostgreSQL (debe devolver listado)
curl "http://<ip-mv-prod-a>:8001/ms1/usuarios?page=1&limit=20"
# → {"total":0,"page":1,"limit":20,"items":[]}  (BD conectada y vacía)

# desde mv-prod-a, confirmar puerto de BD abierto
nc -zv 10.0.2.10 5432
```

### Fase 6 — (Futuro) API Gateway / ALB

El `sg-alb` ya acepta 80/tcp y `sg-prod` ya permite 8001–8005 solo desde `sg-alb`.
Cuando exista el VPC Link / ALB del API Gateway, solo se actualiza la variable
`API_GATEWAY_URL` en el `.env` de cada instancia prod y se reinicia el contenedor.

## Verificación de la compuerta de Fase 1

Desde **mv-prod-a** (tiene acceso por sg-bd), verificar que PostgreSQL responde
sobre la IP privada de mv-bd:

```bash
# 1) Puerto abierto/respondiendo: Base de datos 10.0.2.x:5432
nc -zv 10.0.2.10 5432
# Salida esperada: "Connection to 10.0.2.10 port 5432 [tcp/*] succeeded!"

# 2) Confirmar que mv-bd NO responde desde Internet (desde tu PC, el puerto
#    no debe ser accesible; el sg-bd no permite 0.0.0.0/0 y mv-bd no tiene IP pública)
nc -zv <ip_publica_mv_bd_inexistente_o_rango> 5432   # debe FALLAR
# o, contra la IP pública de mv-prod-a en el puerto 5432 (sg-prod tampoco lo abre):
nc -zv <ip-publica-mv-prod-a> 5432                    # debe FALLAR
```

```bash
# prueba desde la propia máquina del equipo contra una IP PÚBLICA: nada debe escuchar 5432
nc -zv <ip-publica-mv-prod-a> 5432
```

Miramos que **no** haya reglas `0.0.0.0/0` hacia 5432 (solo `sg-prod`):
```bash
# (en AWS Console) EC2 > Security Groups > sg-bd : Inbound -> 5432 desde sg-prod
```

## Decisiones no cubiertas por el contrato

- **NAT Gateway**: se añade (opcional, default `true`) para que mv-bd, estando en
  subred privada sin IP pública, pueda instalar Docker y descargar imágenes. El
  contrato solo mencionaba IGW para la subred pública; el NAT no le da IP pública
  a mv-bd y mantiene la regla de que no sea accesible desde internet.
- **Región/AMI**: `us-east-1` y AMI Amazon Linux 2023 por defecto; ajustar por región.
- **Estado Terraform local**: se usa local por simplicidad (AWS Academy); se
  documenta backend S3 para producción.
- **sg-bd egress**: solo permite salir hacia `sg-prod` en 5432 (mínimo necesario).
- **Acceso a mv-bd**: como está en subred privada sin IP pública, se habilita
  temporalmente `22/tcp` a `sg-bd` desde la IP del equipo solo para la config
  inicial, y se retira al terminar. No se deja permanente; alternativa productiva
  es un bastion (ver Fase 2).
