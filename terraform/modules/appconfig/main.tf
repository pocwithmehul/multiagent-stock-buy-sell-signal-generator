# AppConfig Module for Stock Signal API Feature Flags
# ====================================================
# Creates AWS AppConfig resources for feature flag management.

locals {
  tags = merge(var.tags, {
    Module = "appconfig"
  })

  # Feature flags configuration in AWS AppConfig Feature Flags format
  feature_flags_config = jsonencode({
    version = "1"
    flags = {
      single_stock_analysis = {
        name        = "Single Stock Analysis"
        description = "Core feature - single stock analysis capability"
      }
      watchlist_analysis = {
        name        = "Watchlist Analysis"
        description = "Enable watchlist-based batch analysis"
      }
      premarket_analysis = {
        name        = "Pre-Market Analysis"
        description = "Enable pre-market analysis (4:00 AM - 9:30 AM ET)"
      }
      aftermarket_analysis = {
        name        = "After-Market Analysis"
        description = "Enable after-market analysis (4:00 PM - 8:00 PM ET)"
      }
    }
    values = {
      single_stock_analysis = {
        enabled = var.flag_single_stock_analysis
      }
      watchlist_analysis = {
        enabled = var.flag_watchlist_analysis
      }
      premarket_analysis = {
        enabled = var.flag_premarket_analysis
      }
      aftermarket_analysis = {
        enabled = var.flag_aftermarket_analysis
      }
    }
  })
}

# ─────────────────────────────────────────────────────────────────────────────
# AppConfig Application
# ─────────────────────────────────────────────────────────────────────────────

resource "aws_appconfig_application" "main" {
  name        = "stock-signal-${var.environment}"
  description = "Stock Signal API feature flags for ${var.environment} environment"

  tags = local.tags
}

# ─────────────────────────────────────────────────────────────────────────────
# AppConfig Environment
# ─────────────────────────────────────────────────────────────────────────────

resource "aws_appconfig_environment" "main" {
  name           = var.environment
  description    = "Stock Signal API ${var.environment} environment"
  application_id = aws_appconfig_application.main.id

  tags = local.tags
}

# ─────────────────────────────────────────────────────────────────────────────
# AppConfig Configuration Profile (Feature Flags type)
# ─────────────────────────────────────────────────────────────────────────────

resource "aws_appconfig_configuration_profile" "feature_flags" {
  application_id = aws_appconfig_application.main.id
  name           = "feature-flags"
  description    = "Feature flags for Stock Signal API"
  location_uri   = "hosted"
  type           = "AWS.AppConfig.FeatureFlags"

  tags = local.tags
}

# ─────────────────────────────────────────────────────────────────────────────
# Hosted Configuration Version
# ─────────────────────────────────────────────────────────────────────────────

resource "aws_appconfig_hosted_configuration_version" "feature_flags" {
  application_id           = aws_appconfig_application.main.id
  configuration_profile_id = aws_appconfig_configuration_profile.feature_flags.configuration_profile_id
  content_type             = "application/json"
  content                  = local.feature_flags_config
  description              = "Feature flags configuration v${var.config_version}"
}

# ─────────────────────────────────────────────────────────────────────────────
# Deployment Strategy
# ─────────────────────────────────────────────────────────────────────────────

resource "aws_appconfig_deployment_strategy" "main" {
  name                           = "stock-signal-${var.environment}-strategy"
  description                    = "Deployment strategy for ${var.environment}"
  deployment_duration_in_minutes = var.environment == "prod" ? 10 : 0
  final_bake_time_in_minutes     = var.environment == "prod" ? 5 : 0
  growth_factor                  = var.environment == "prod" ? 20 : 100
  growth_type                    = "LINEAR"
  replicate_to                   = "NONE"

  tags = local.tags
}

# ─────────────────────────────────────────────────────────────────────────────
# Deployment
# ─────────────────────────────────────────────────────────────────────────────

resource "aws_appconfig_deployment" "feature_flags" {
  application_id           = aws_appconfig_application.main.id
  configuration_profile_id = aws_appconfig_configuration_profile.feature_flags.configuration_profile_id
  configuration_version    = aws_appconfig_hosted_configuration_version.feature_flags.version_number
  deployment_strategy_id   = aws_appconfig_deployment_strategy.main.id
  environment_id           = aws_appconfig_environment.main.environment_id
  description              = "Deploy feature flags v${var.config_version}"

  tags = local.tags
}

# ─────────────────────────────────────────────────────────────────────────────
# IAM Policy for EKS Pod Access
# ─────────────────────────────────────────────────────────────────────────────

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

resource "aws_iam_policy" "appconfig_access" {
  name        = "stock-signal-${var.environment}-appconfig-access"
  description = "Allow EKS pods to read AppConfig feature flags"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AppConfigGetConfiguration"
        Effect = "Allow"
        Action = [
          "appconfig:GetLatestConfiguration",
          "appconfig:StartConfigurationSession"
        ]
        Resource = [
          "arn:aws:appconfig:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:application/${aws_appconfig_application.main.id}/environment/${aws_appconfig_environment.main.environment_id}/configuration/${aws_appconfig_configuration_profile.feature_flags.configuration_profile_id}"
        ]
      },
      {
        Sid    = "AppConfigListApplications"
        Effect = "Allow"
        Action = [
          "appconfig:GetApplication",
          "appconfig:GetEnvironment",
          "appconfig:GetConfigurationProfile"
        ]
        Resource = [
          aws_appconfig_application.main.arn,
          "arn:aws:appconfig:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:application/${aws_appconfig_application.main.id}/environment/${aws_appconfig_environment.main.environment_id}",
          "arn:aws:appconfig:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:application/${aws_appconfig_application.main.id}/configurationprofile/${aws_appconfig_configuration_profile.feature_flags.configuration_profile_id}"
        ]
      }
    ]
  })

  tags = local.tags
}
