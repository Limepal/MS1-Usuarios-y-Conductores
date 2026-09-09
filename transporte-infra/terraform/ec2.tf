# =============================================================================
# 4 instancias EC2 (Contrato §9 / Plan Maestro Fase 1, actualizado al contexto)
#   - mv-prod-a  : subred pública A (10.0.1.0/24), Docker + Docker Compose
#   - mv-prod-b  : subred pública B (10.0.3.0/24, 2da AZ), Docker + Docker Compose
#   - mv-ingesta : subred pública A (10.0.1.0/24), Docker (pull a S3, P5)
#   - mv-bd      : subred PRIVADA (10.0.2.0/24), sin IP pública, Docker + Docker Compose
# =============================================================================

# --- Script de bootstrap común: instala Docker + Docker Compose ---------------
locals {
  user_data_docker = <<-EOT
    #!/bin/bash
    set -eux
    dnf update -y
    dnf install -y docker
    systemctl enable --now docker
    usermod -aG docker ec2-user
    # Docker Compose v2 (plugin)
    mkdir -p /usr/local/lib/docker/cli-plugins
    curl -sSL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64" \
      -o /usr/local/lib/docker/cli-plugins/docker-compose
    chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
    docker compose version
    echo "== bootstrap docker OK =="
  EOT
}

# --- mv-prod-a -----------------------------------------------------------------
resource "aws_instance" "mv_prod_a" {
  ami                    = var.ami_id
  instance_type          = var.tipo_instancia
  subnet_id              = aws_subnet.publica.id
  vpc_security_group_ids = [aws_security_group.prod.id]
  key_name               = var.par_de_claves != "" ? var.par_de_claves : null
  user_data              = local.user_data_docker

  tags = { Name = "mv-prod-a" }
}

# --- mv-prod-b (2da AZ) ---------------------------------------------------------
resource "aws_instance" "mv_prod_b" {
  ami                    = var.ami_id
  instance_type          = var.tipo_instancia
  subnet_id              = aws_subnet.publica_b.id
  vpc_security_group_ids = [aws_security_group.prod.id]
  key_name               = var.par_de_claves != "" ? var.par_de_claves : null
  user_data              = local.user_data_docker

  tags = { Name = "mv-prod-b" }
}

# --- mv-ingesta (pull a S3, lo usa P5) ------------------------------------------
resource "aws_instance" "mv_ingesta" {
  ami                    = var.ami_id
  instance_type          = var.tipo_instancia
  subnet_id              = aws_subnet.publica.id
  vpc_security_group_ids = [aws_security_group.prod.id]
  key_name               = var.par_de_claves != "" ? var.par_de_claves : null
  user_data              = local.user_data_docker

  # En sg-prod para poder alcanzar sg-bd (pull de las 3 bases) y salir a S3.
  tags = { Name = "mv-ingesta" }
}

# --- mv-bd (base de datos privada, sin IP pública) ------------------------------
resource "aws_instance" "mv_bd" {
  ami                    = var.ami_id
  instance_type          = var.tipo_instancia_bd
  subnet_id              = aws_subnet.privada.id
  vpc_security_group_ids = [aws_security_group.bd.id]
  key_name               = var.par_de_claves != "" ? var.par_de_claves : null
  user_data              = local.user_data_docker

  tags = { Name = "mv-bd" }

  # mv-bd queda en la subred privada sin IP pública (map_public_ip_on_launch=false).
}
