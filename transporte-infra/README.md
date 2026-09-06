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

## Levantar PostgreSQL en mv-bd

```bash
# conectar por SSH: ssh -i <key> ec2-user@<ip-mv-bd>  (desde una instancia prod o vía bastión)
git clone <repos>
cp .env.example .env        # completar POSTGRES_PASS
docker compose -f docker-compose.bd.yml up -d
docker compose -f docker-compose.bd.yml ps
```

El esquema de MS1 (`sql/schema.sql`) se monta en `docker-entrypoint-initdb.d` y se
aplica automáticamente en el primer arranque (crea las 3 tablas + 3 índices).
> Nota: requiere tener el repo `transporte-ms1-usuarios` junto a este (ruta
> `../transporte-ms1-usuarios/sql/schema.sql`) o ajustar el volumen.

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
