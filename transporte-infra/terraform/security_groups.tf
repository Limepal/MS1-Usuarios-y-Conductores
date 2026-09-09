# =============================================================================
# Security Groups exactos (Contrato §9, actualizado al contexto)
#   - sg-alb  : 80/tcp solo desde la VPC (10.0.0.0/16)
#   - sg-prod : 8001-8005/tcp desde sg-alb y desde sg-prod ; 22/tcp desde IPs del equipo
#   - sg-bd   : 5432/3306/27017/tcp solo desde sg-prod (sin 0.0.0.0/0)
# =============================================================================

# --- sg-alb: tráfico del balanceador / API Gateway ----------------------------
resource "aws_security_group" "alb" {
  name        = "transporte-alb-sg"
  description = "Security group del ALB interno / API Gateway (VPC Link)."
  vpc_id      = aws_vpc.principal.id

  # ALB interno: solo tráfico originado dentro de la VPC (p. ej. VPC Link).
  ingress {
    description = "HTTP desde la VPC"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # AWS no permite que el 'name' empiece con "sg-"; el tag conserva el nombre lógico.
  tags = { Name = "sg-alb" }
}

# --- sg-prod: microservicios + SSH del equipo -----------------------------------
resource "aws_security_group" "prod" {
  name        = "transporte-prod-sg"
  description = "Acceso a microservicios (8001-8005) y SSH del equipo."
  vpc_id      = aws_vpc.principal.id

  # Puertos de los 5 microservicios desde el balanceador (sg-alb)
  ingress {
    description     = "Microservicios desde el ALB/API Gateway"
    from_port       = 8001
    to_port         = 8005
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  # Puertos de los 5 microservicios hacia otras instancias del grupo (inter-MS)
  ingress {
    description     = "Microservicios entre instancias prod"
    from_port       = 8001
    to_port         = 8005
    protocol        = "tcp"
    security_groups = [aws_security_group.prod.id]
  }

  # SSH solo desde las IPs del equipo (no 0.0.0.0/0)
  dynamic "ingress" {
    for_each = var.ip_equipo_cidr
    content {
      description = "SSH del equipo"
      from_port   = 22
      to_port     = 22
      protocol    = "tcp"
      cidr_blocks = [ingress.value]
    }
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # AWS no permite que el 'name' empiece con "sg-"; el tag conserva el nombre lógico.
  tags = { Name = "sg-prod" }
}

# --- sg-bd: solo puertos de BD desde sg-prod, sin 0.0.0.0/0 ---------------------
resource "aws_security_group" "bd" {
  name        = "transporte-bd-sg"
  description = "Acceso a PostgreSQL (5432), MySQL (3306) y MongoDB (27017), solo desde sg-prod."
  vpc_id      = aws_vpc.principal.id

  # PostgreSQL 16 -> MS1
  ingress {
    description     = "PostgreSQL"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.prod.id]
  }

  # Hueco MySQL (lo consumirá P2)
  ingress {
    description     = "MySQL"
    from_port       = 3306
    to_port         = 3306
    protocol        = "tcp"
    security_groups = [aws_security_group.prod.id]
  }

  # Hueco MongoDB (lo consumirá P3)
  ingress {
    description     = "MongoDB"
    from_port       = 27017
    to_port         = 27017
    protocol        = "tcp"
    security_groups = [aws_security_group.prod.id]
  }

  # NOTA: nada de 0.0.0.0/0. La mv-bd no es accesible desde internet.
  egress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.prod.id]
  }

  # AWS no permite que el 'name' empiece con "sg-"; el tag conserva el nombre lógico.
  tags = { Name = "sg-bd" }
}
