# AppConfig Module Outputs
# ========================

output "application_id" {
  description = "AppConfig Application ID"
  value       = aws_appconfig_application.main.id
}

output "application_arn" {
  description = "AppConfig Application ARN"
  value       = aws_appconfig_application.main.arn
}

output "environment_id" {
  description = "AppConfig Environment ID"
  value       = aws_appconfig_environment.main.environment_id
}

output "configuration_profile_id" {
  description = "AppConfig Configuration Profile ID"
  value       = aws_appconfig_configuration_profile.feature_flags.configuration_profile_id
}

output "deployment_strategy_id" {
  description = "AppConfig Deployment Strategy ID"
  value       = aws_appconfig_deployment_strategy.main.id
}

output "iam_policy_arn" {
  description = "IAM Policy ARN for AppConfig access"
  value       = aws_iam_policy.appconfig_access.arn
}

output "iam_policy_name" {
  description = "IAM Policy name for AppConfig access"
  value       = aws_iam_policy.appconfig_access.name
}

# Outputs for application configuration
output "config_env_vars" {
  description = "Environment variables to set for the application"
  value = {
    APPCONFIG_APPLICATION_ID = aws_appconfig_application.main.id
    APPCONFIG_ENVIRONMENT_ID = aws_appconfig_environment.main.environment_id
    APPCONFIG_PROFILE_ID     = aws_appconfig_configuration_profile.feature_flags.configuration_profile_id
  }
}
