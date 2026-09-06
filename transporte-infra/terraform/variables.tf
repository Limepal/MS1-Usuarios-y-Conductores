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
  description = "Subred pública para mv-prod-a, mv-prod-b y mv-ingesta."
  type        = string
  default     = "10.0.1.0/24"
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
  default     = "ami-0e86e20dae9224db8"
}

variable "par_de_claves" {
  description = "Nombre del par de claves (key pair) EC2 existente."
  type        = string
  default     = ""
}

variable "ip_equipo_cidr" {
  description = "Lista de CIDR desde donde el equipo accede por SSH (22/tcp) a las instancias prod."
  type        = list(string)
  default     = ["0.0.0.0/0"] # CAMBIAR por la IP pública del equipo: ["X.X.X.X/32"]
}

variable "crear_nat_gateway" {
  description = "Crea NAT Gateway para que mv-bd (subred privada) pueda instalar Docker y descargar imágenes, sin IP pública."
  type        = bool
  default     = true
}
