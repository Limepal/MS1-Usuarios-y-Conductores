# Diagrama de arquitectura (draw.io)

Entregable de **P1** (`Diagrama de arquitectura en draw.io`, pendiente #6 del
`CONTEXTO-PROYECTO.md`). Este documento define qué dibujar y los insumos que
necesita cada parte del equipo.

## Qué incluir (según §3 del contexto)

```
                    Frontend (AWS Amplify)      <- P4
                              | HTTPS
                    API Gateway (HTTP API)      <- P3
                              | VPC Link
                  ALB interno (privado)         <- P2
                    +-----------------+
              mv-prod-a            mv-prod-b    (subred pública A / B)
              ms1 ms2 ms3 ms4 ms5  ms1 ms2 ms3 ms4 ms5
                    +-----------------+
                          mv-bd                 (subred PRIVADA)
                  postgres 5432 · mysql 3306 · mongo 27017

              mv-ingesta --> S3 --> Glue --> Athena --> MS5   <- P5
```

Elementos obligatorios:
- **VPC** `10.0.0.0/16` con 3 subredes visibles:
  - `10.0.1.0/24` pública (AZ a) → mv-prod-a, mv-ingesta
  - `10.0.3.0/24` pública (AZ b) → mv-prod-b
  - `10.0.2.0/24` PRIVADA (AZ a) → mv-bd (sin IP pública)
- Internet Gateway + NAT Gateway (salida de la subred privada).
- Security Groups: `sg-alb` (80 solo desde la VPC), `sg-prod` (8001–8005 desde
  sg-alb y sg-prod; 22 desde IPs del equipo), `sg-bd` (5432/3306/27017 solo
  desde sg-prod).
- 5 contenedores por MV prod (ms1–ms5, puertos 8001–8005).
- mv-bd con las 3 bases (PostgreSQL, MySQL, MongoDB).
- API Gateway + VPC Link + ALB interno (P2/P3).
- Amplify (P4) y pipeline analítico S3/Glue/Athena + MS5 (P5).

## Insumos por parte

| Parte | Debe aportar |
|-------|--------------|
| P2 | Forma y reglas del ALB interno (target groups por path, puertos) |
| P3 | API Gateway con VPC Link, CORS, dominio HTTPS |
| P4 | Frontend en Amplify, consumo de los 5 MS |
| P5 | MV de ingesta, bucket S3, catálogo Glue, consultas Athena |

## Diagramas E/R y JSON (requeridos además por el enunciado)

- E/R de **PostgreSQL (MS1)**: `usuarios`, `conductores`, `vehiculos` con la
  relación `conductores 1—N vehiculos`. DDL en `transporte-ms1-usuarios/sql/schema.sql`.
- E/R de **MySQL (MS2)**: `tarifas`, `viajes`, `paradas`
  (`tarifas 1—N viajes`, `viajes 1—N paradas`). Schema final de P2.
- Estructuras JSON de **MongoDB (MS3)**: colecciones `calificaciones` y
  `reportes` (ver `transporte-ms3-calificaciones/docs/esquemas.json`).

## Cómo completarlo

1. El equipo junta los insumos de la tabla de arriba.
2. En [draw.io](https://app.diagrams.net/) se dibuja la arquitectura completa y
   se guarda como `arquitectura.drawio` dentro de `transporte-infra/docs/`.
3. Confirmar con el ACL: deben apreciarse las 3 subredes, la MV de BD privada
   sin IP pública y los 5 microservicios en las 2 MVs de producción.