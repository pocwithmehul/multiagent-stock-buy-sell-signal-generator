# STG Environment Outputs
# =======================

output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "private_subnet_ids" {
  description = "Private subnet IDs"
  value       = module.vpc.private_subnet_ids
}

output "eks_cluster_name" {
  description = "EKS cluster name"
  value       = module.eks.cluster_name
}

output "eks_cluster_endpoint" {
  description = "EKS cluster endpoint"
  value       = module.eks.cluster_endpoint
}

output "eks_cluster_certificate_authority" {
  description = "EKS cluster CA certificate"
  value       = module.eks.cluster_certificate_authority_data
  sensitive   = true
}

output "stock_signal_api_role_arn" {
  description = "IAM role ARN for stock-signal-api (IRSA)"
  value       = module.eks.stock_signal_api_role_arn
}

output "msk_bootstrap_brokers" {
  description = "MSK bootstrap brokers (IAM auth)"
  value       = module.msk.bootstrap_brokers_iam
}

output "opensearch_endpoint" {
  description = "OpenSearch domain endpoint"
  value       = module.opensearch.domain_endpoint
}

output "api_keys_secret_arn" {
  description = "API keys secret ARN"
  value       = module.secrets.api_keys_secret_arn
}

output "kubeconfig_command" {
  description = "Command to update kubeconfig"
  value       = "aws eks update-kubeconfig --region ${var.region} --name ${module.eks.cluster_name}"
}

# Frontend
output "frontend_url" {
  description = "Frontend dashboard URL"
  value       = module.frontend.website_url
}

output "frontend_s3_bucket" {
  description = "Frontend S3 bucket name"
  value       = module.frontend.s3_bucket_name
}

output "frontend_cloudfront_id" {
  description = "CloudFront distribution ID"
  value       = module.frontend.cloudfront_distribution_id
}

# AppConfig (Feature Flags)
output "appconfig_application_id" {
  description = "AppConfig Application ID"
  value       = module.appconfig.application_id
}

output "appconfig_environment_id" {
  description = "AppConfig Environment ID"
  value       = module.appconfig.environment_id
}

output "appconfig_profile_id" {
  description = "AppConfig Configuration Profile ID"
  value       = module.appconfig.configuration_profile_id
}

output "appconfig_iam_policy_arn" {
  description = "IAM Policy ARN for AppConfig access"
  value       = module.appconfig.iam_policy_arn
}
