variable "aws_region" {
  description = "Región AWS donde se despliega la infraestructura."
  type        = string
  default     = "us-east-1"
}

variable "proyecto" {
  description = "Prefijo de nombres de los recursos."
  type        = string
  default     = "transporte"
}

variable "ambiente" {
  description = "Ambiente (dev/prod)."
  type        = string
  default     = "prod"
}

variable "cidr_vpc" {
  description = "Bloque CIDR base de la VPC (Contrato: 10.0.0.0/16)."
  type        = string
  default     = "10.0.0.0/16"
}

variable "cidr_subred_publica" {
  description = "Subred pública A para mv-prod-a y mv-ingesta (10.0.1.0/24)."
  type        = string
  default     = "10.0.1.0/24"
}

variable "cidr_subred_publica_b" {
  description = "Subred pública B para mv-prod-b en la 2da AZ (10.0.3.0/24)."
  type        = string
  default     = "10.0.3.0/24"
}

variable "az_publica_b" {
  description = "Segunda AZ para la subred pública B (la exige el balanceador)."
  type        = string
  default     = "b"
}

variable "cidr_subred_privada" {
  description = "Subred privada para mv-bd (sin IP pública)."
  type        = string
  default     = "10.0.2.0/24"
}

variable "tipo_instancia" {
  description = "Tipo de instancia EC2 común (parametrizable, ej. t3.small)."
  type        = string
  default     = "t3.small"
}

variable "tipo_instancia_bd" {
  description = "Tipo de instancia EC2 para mv-bd."
  type        = string
  default     = "t3.small"
}

variable "ami_id" {
  description = "AMI de Amazon Linux 2023 (Recomendado: AL2023 x86_64). Se debe ajustar por región."
  type        = string
  default     = "ami-081b0a6eac00b4f53"
}

variable "par_de_claves" {
  description = "Nombre del par de claves (key pair) EC2 existente."
  type        = string
  default     = "transporte-key"
}

variable "ip_equipo_cidr" {
  description = "Lista de CIDR desde donde el equipo accede por SSH (22/tcp) a las instancias prod."
  type        = list(string)
  # OBLIGATORIO antes del apply: reemplazar por las IPs públicas reales del equipo,
  # ej. ["X.X.X.X/32","Y.Y.Y.Y/32"]. No aplicar con 0.0.0.0/0.
  default = ["38.224.230.64/32", "45.236.45.63/32"]
}

variable "crear_nat_gateway" {
  description = "Crea NAT Gateway para que mv-bd (subred privada) pueda instalar Docker y descargar imágenes, sin IP pública."
  type        = bool
  default     = true
}
