# Secrets Module for Stock Signal API
# ====================================
# Creates AWS Secrets Manager secrets for the application.

locals {
  tags = merge(var.tags, {
    Module = "secrets"
  })

  secret_prefix = "stock-signal/${var.environment}"
}

# ─────────────────────────────────────────────────────────────────────────────
# API Keys Secret
# ─────────────────────────────────────────────────────────────────────────────

resource "aws_secretsmanager_secret" "api_keys" {
  name        = "${local.secret_prefix}/api-keys"
  description = "API keys for Stock Signal API"

  recovery_window_in_days = var.recovery_window_in_days
  kms_key_id              = var.kms_key_arn

  tags = merge(local.tags, {
    SecretType = "api-keys"
  })
}

resource "aws_secretsmanager_secret_version" "api_keys" {
  secret_id = aws_secretsmanager_secret.api_keys.id

  secret_string = jsonencode({
    openai_api_key = var.openai_api_key
    # Additional API keys can be added here
  })
}

# ─────────────────────────────────────────────────────────────────────────────
# Observability Secret (Langfuse)
# ─────────────────────────────────────────────────────────────────────────────

resource "aws_secretsmanager_secret" "observability" {
  name        = "${local.secret_prefix}/observability"
  description = "Observability credentials for Stock Signal API"

  recovery_window_in_days = var.recovery_window_in_days
  kms_key_id              = var.kms_key_arn

  tags = merge(local.tags, {
    SecretType = "observability"
  })
}

resource "aws_secretsmanager_secret_version" "observability" {
  secret_id = aws_secretsmanager_secret.observability.id

  secret_string = jsonencode({
    langfuse_public_key = var.langfuse_public_key
    langfuse_secret_key = var.langfuse_secret_key
  })
}

# ─────────────────────────────────────────────────────────────────────────────
# Messaging Secret (Twilio, SMTP)
# ─────────────────────────────────────────────────────────────────────────────

resource "aws_secretsmanager_secret" "messaging" {
  name        = "${local.secret_prefix}/messaging"
  description = "Messaging credentials for Stock Signal API"

  recovery_window_in_days = var.recovery_window_in_days
  kms_key_id              = var.kms_key_arn

  tags = merge(local.tags, {
    SecretType = "messaging"
  })
}

resource "aws_secretsmanager_secret_version" "messaging" {
  secret_id = aws_secretsmanager_secret.messaging.id

  secret_string = jsonencode({
    twilio_account_sid = var.twilio_account_sid
    twilio_auth_token  = var.twilio_auth_token
    twilio_from_number = var.twilio_from_number
    smtp_host          = var.smtp_host
    smtp_port          = var.smtp_port
    smtp_username      = var.smtp_username
    smtp_password      = var.smtp_password
    smtp_from_email    = var.smtp_from_email
  })
}

# ─────────────────────────────────────────────────────────────────────────────
# Database Secret (for future use)
# ─────────────────────────────────────────────────────────────────────────────

resource "aws_secretsmanager_secret" "database" {
  count = var.create_database_secret ? 1 : 0

  name        = "${local.secret_prefix}/database"
  description = "Database credentials for Stock Signal API"

  recovery_window_in_days = var.recovery_window_in_days
  kms_key_id              = var.kms_key_arn

  tags = merge(local.tags, {
    SecretType = "database"
  })
}

# ─────────────────────────────────────────────────────────────────────────────
# Secret Rotation (optional)
# ─────────────────────────────────────────────────────────────────────────────

# Lambda for automatic rotation can be added here if needed
