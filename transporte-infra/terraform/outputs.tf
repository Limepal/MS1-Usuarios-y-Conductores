# =============================================================================
# Outputs de la infraestructura Fase 1.
# =============================================================================

output "vpc_id" {
  description = "Id de la VPC."
  value       = aws_vpc.principal.id
}

output "subred_publica_id" {
  description = "Id de la subred pública A."
  value       = aws_subnet.publica.id
}

output "subred_publica_b_id" {
  description = "Id de la subred pública B (2da AZ)."
  value       = aws_subnet.publica_b.id
}

output "subred_privada_id" {
  description = "Id de la subred privada."
  value       = aws_subnet.privada.id
}

output "ip_publica_mv_prod_a" {
  description = "IP pública de mv-prod-a."
  value       = aws_instance.mv_prod_a.public_ip
}

output "ip_publica_mv_prod_b" {
  description = "IP pública de mv-prod-b."
  value       = aws_instance.mv_prod_b.public_ip
}

output "ip_publica_mv_ingesta" {
  description = "IP pública de mv-ingesta."
  value       = aws_instance.mv_ingesta.public_ip
}

output "ip_privada_mv_ingesta" {
  description = "IP privada de mv-ingesta."
  value       = aws_instance.mv_ingesta.private_ip
}

output "ip_privada_mv_bd" {
  description = "IP privada de mv-bd (10.0.2.x)."
  value       = aws_instance.mv_bd.private_ip
}

output "sg_alb" {
  description = "Id del security group sg-alb."
  value       = aws_security_group.alb.id
}

output "sg_prod" {
  description = "Id del security group sg-prod."
  value       = aws_security_group.prod.id
}

output "sg_bd" {
  description = "Id del security group sg-bd."
  value       = aws_security_group.bd.id
}
