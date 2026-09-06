# =============================================================================
# transporte-infra · Terraform — Infraestructura base Fase 1 (Contrato §9)
# Responsabilidad de P1: VPC + 3 instancias + 3 security groups.
# =============================================================================

terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # NOTA: el estado local se usa por simplicidad en la cuenta de AWS Academy.
  # Para un equipo real se recomienda backend S3 + DynamoDB (lock).
  # backend "s3" {
  #   bucket = "transporte-infra-tfstate"
  #   key    = "prod/terraform.tfstate"
  #   region = "us-east-1"
  # }
}

provider "aws" {
  region = var.aws_region
}
