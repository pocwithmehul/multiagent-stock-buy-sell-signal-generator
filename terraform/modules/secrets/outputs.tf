# Secrets Module Outputs
# ======================

output "api_keys_secret_arn" {
  description = "ARN of the API keys secret"
  value       = aws_secretsmanager_secret.api_keys.arn
}

output "api_keys_secret_name" {
  description = "Name of the API keys secret"
  value       = aws_secretsmanager_secret.api_keys.name
}

output "observability_secret_arn" {
  description = "ARN of the observability secret"
  value       = aws_secretsmanager_secret.observability.arn
}

output "observability_secret_name" {
  description = "Name of the observability secret"
  value       = aws_secretsmanager_secret.observability.name
}

output "messaging_secret_arn" {
  description = "ARN of the messaging secret"
  value       = aws_secretsmanager_secret.messaging.arn
}

output "messaging_secret_name" {
  description = "Name of the messaging secret"
  value       = aws_secretsmanager_secret.messaging.name
}

output "database_secret_arn" {
  description = "ARN of the database secret (if created)"
  value       = var.create_database_secret ? aws_secretsmanager_secret.database[0].arn : null
}
