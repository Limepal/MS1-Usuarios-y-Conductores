# =============================================================================
# 3 instancias EC2 (Contrato §9 / Plan Maestro Fase 1)
#   - mv-prod-a, mv-prod-b : subred pública, Docker + Docker Compose
#   - mv-bd                : subred privada, sin IP pública, Docker + Docker Compose
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

# --- mv-prod-b -----------------------------------------------------------------
resource "aws_instance" "mv_prod_b" {
  ami                    = var.ami_id
  instance_type          = var.tipo_instancia
  subnet_id              = aws_subnet.publica.id
  vpc_security_group_ids = [aws_security_group.prod.id]
  key_name               = var.par_de_claves != "" ? var.par_de_claves : null
  user_data              = local.user_data_docker

  tags = { Name = "mv-prod-b" }
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
