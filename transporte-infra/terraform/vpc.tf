# =============================================================================
# VPC 10.0.0.0/16 con 2 subredes públicas + 1 privada + Internet Gateway.
#   - 10.0.1.0/24 pública (AZ a)  -> mv-prod-a, mv-ingesta
#   - 10.0.3.0/24 pública (AZ b)  -> mv-prod-b  (2da AZ: la exige el balanceador)
#   - 10.0.2.0/24 PRIVADA (AZ a)  -> mv-bd (sin IP pública)
# =============================================================================

resource "aws_vpc" "principal" {
  cidr_block           = var.cidr_vpc
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "${var.proyecto}-${var.ambiente}-vpc"
  }
}

# Subred pública A (mv-prod-a, mv-ingesta)
resource "aws_subnet" "publica" {
  vpc_id                  = aws_vpc.principal.id
  cidr_block              = var.cidr_subred_publica
  availability_zone       = "${var.aws_region}a"
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.proyecto}-${var.ambiente}-subred-publica-a"
  }
}

# Subred pública B (mv-prod-b, 2da AZ exigida por el balanceador)
resource "aws_subnet" "publica_b" {
  vpc_id                  = aws_vpc.principal.id
  cidr_block              = var.cidr_subred_publica_b
  availability_zone       = "${var.aws_region}${var.az_publica_b}"
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.proyecto}-${var.ambiente}-subred-publica-b"
  }
}

# Subred privada (mv-bd, sin IP pública). Misma AZ que el NAT (eficiencia).
resource "aws_subnet" "privada" {
  vpc_id                  = aws_vpc.principal.id
  cidr_block              = var.cidr_subred_privada
  availability_zone       = "${var.aws_region}a"
  map_public_ip_on_launch = false

  tags = {
    Name = "${var.proyecto}-${var.ambiente}-subred-privada"
  }
}

# Internet Gateway: entrada/salida de las subredes públicas
resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.principal.id

  tags = {
    Name = "${var.proyecto}-${var.ambiente}-igw"
  }
}

# Tabla de rutas para las subredes públicas -> Internet Gateway
resource "aws_route_table" "publica" {
  vpc_id = aws_vpc.principal.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }

  tags = {
    Name = "${var.proyecto}-${var.ambiente}-rt-publica"
  }
}

resource "aws_route_table_association" "publica" {
  subnet_id      = aws_subnet.publica.id
  route_table_id = aws_route_table.publica.id
}

resource "aws_route_table_association" "publica_b" {
  subnet_id      = aws_subnet.publica_b.id
  route_table_id = aws_route_table.publica.id
}

# --- NAT Gateway (opcional): da salida a internet a la subred privada ---------
# Necesario para que mv-bd instale Docker y descargue imágenes, SIN IP pública.
resource "aws_eip" "nat" {
  count  = var.crear_nat_gateway ? 1 : 0
  domain = "vpc"

  tags = { Name = "${var.proyecto}-${var.ambiente}-nat-eip" }
}

resource "aws_nat_gateway" "nat" {
  count         = var.crear_nat_gateway ? 1 : 0
  allocation_id = aws_eip.nat[0].id
  subnet_id     = aws_subnet.publica.id

  tags = { Name = "${var.proyecto}-${var.ambiente}-nat" }
}

# Tabla de rutas de la subred privada: salida 0.0.0.0/0 -> NAT (si se crea)
resource "aws_route_table" "privada" {
  vpc_id = aws_vpc.principal.id

  dynamic "route" {
    for_each = var.crear_nat_gateway ? [1] : []
    content {
      cidr_block     = "0.0.0.0/0"
      nat_gateway_id = aws_nat_gateway.nat[0].id
    }
  }

  tags = { Name = "${var.proyecto}-${var.ambiente}-rt-privada" }
}

resource "aws_route_table_association" "privada" {
  subnet_id      = aws_subnet.privada.id
  route_table_id = aws_route_table.privada.id
}
