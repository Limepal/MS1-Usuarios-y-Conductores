# transporte-infra

Infraestructura del proyecto Transporte Urbano. **La guía paso a paso para desplegar todo está en el
[README principal](../README.md).** Aquí solo se describe qué contiene esta carpeta.

```
terraform/
├── main.tf              # provider AWS (us-east-1)
├── vpc.tf               # VPC 10.0.0.0/16 · 2 subredes públicas (a/b) · 1 privada · IGW · NAT · rutas
├── security_groups.tf   # transporte-alb-sg · transporte-prod-sg · transporte-bd-sg
├── ec2.tf               # mv-prod-a, mv-prod-b, mv-ingesta, mv-bd (Docker + Compose por user_data, rol LabInstanceProfile)
├── variables.tf         # AMI, tipos de instancia, IPs del equipo, NAT, perfil de instancia
└── outputs.tf           # vpc_id, subredes, IPs, security groups (los usan los scripts del ALB)
init/
├── postgres/01-schema.sql   # usuarios, conductores, vehiculos (MS1)
├── mysql/01-schema.sql      # tarifas, viajes, paradas (MS2)
└── mongo/01-usuario.js      # usuario app_ms3, colecciones e índices (MS3)
docker-compose.bd.yml    # PostgreSQL 16 + MySQL 8 + MongoDB 7 (corre en mv-bd)
docker-compose.prod.yml  # ms1…ms5 (corre en mv-prod-a y mv-prod-b)
desplegar-prod.sh        # clona los 5 repos, construye las imágenes y levanta docker-compose.prod.yml
.env.example             # contraseñas, BD_HOST, S3_BUCKET, API_GATEWAY_URL
```

## Topología

| MV | Subred | IP | Rol |
|---|---|---|---|
| mv-prod-a | pública A · 10.0.1.0/24 · us-east-1a | pública + privada | 5 microservicios (docker compose) |
| mv-prod-b | pública B · 10.0.3.0/24 · us-east-1b | pública + privada | 5 microservicios (réplica, 2.ª AZ) |
| mv-ingesta | pública A · 10.0.1.0/24 | pública + privada | 3 contenedores de ingesta → S3 |
| mv-bd | **privada** · 10.0.2.0/24 | **solo privada** | PostgreSQL, MySQL, MongoDB |

## Security groups

| SG | Entrada | Por qué |
|---|---|---|
| `transporte-alb-sg` | 80/tcp desde la VPC (10.0.0.0/16) | ALB **interno**, alimentado por el VPC Link del API Gateway |
| `transporte-prod-sg` | 8001–8005 desde el ALB y desde sí mismo · 22 desde `ip_equipo_cidr` | Microservicios; mv-ingesta también está aquí para leer las BD |
| `transporte-bd-sg` | 5432, 3306, 27017 y 22 **solo desde `transporte-prod-sg`** | Base privada: ninguna regla `0.0.0.0/0` |

## Decisiones

- **NAT Gateway** (`crear_nat_gateway = true`): permite que `mv-bd`, sin IP pública, instale Docker y
  descargue imágenes. Solo da salida; nadie desde internet puede conectarse a `mv-bd`. Se puede eliminar
  después para ahorrar créditos.
- **Rol `LabInstanceProfile` en las 4 MV**: administración por **SSM Session Manager** (sin abrir SSH a
  internet), y credenciales temporales para S3 (ingesta) y Athena (MS5) sin llaves en el código.
- **2 subredes públicas en AZ distintas**: requisito del ALB y alta disponibilidad de prod-a / prod-b.
- **Imágenes construidas en la MV** (`desplegar-prod.sh`): no depende de registries de terceros.
- **Estado de Terraform local** (AWS Academy); en producción real se usaría un backend S3.
- El **ALB**, el **API Gateway** y **Amplify** se crean con los pasos 5–7 del README principal
  (scripts del repo de MS2 y AWS CLI).
