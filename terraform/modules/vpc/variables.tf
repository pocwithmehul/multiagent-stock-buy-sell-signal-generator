# VPC Module Variables
# ====================

variable "name" {
  description = "Name prefix for all resources"
  type        = string
}

variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "cluster_name" {
  description = "Name of the EKS cluster (for subnet tagging)"
  type        = string
}

variable "single_nat_gateway" {
  description = "Use a single NAT gateway (cost saving for non-prod)"
  type        = bool
  default     = false
}

variable "enable_ecr_endpoint" {
  description = "Enable VPC endpoint for ECR"
  type        = bool
  default     = true
}

variable "enable_bedrock_endpoint" {
  description = "Enable VPC endpoint for Bedrock Runtime"
  type        = bool
  default     = true
}

variable "enable_secrets_endpoint" {
  description = "Enable VPC endpoint for Secrets Manager"
  type        = bool
  default     = true
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
