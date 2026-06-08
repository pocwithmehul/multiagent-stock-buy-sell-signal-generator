# IAM Module Variables
# ====================

variable "name" {
  description = "Name prefix for IAM resources"
  type        = string
}

variable "region" {
  description = "AWS region"
  type        = string
}

variable "environment" {
  description = "Environment name (qa, stg, prod)"
  type        = string
}

variable "msk_cluster_arn" {
  description = "MSK cluster ARN (optional, uses default pattern if empty)"
  type        = string
  default     = ""
}

variable "opensearch_domain_arn" {
  description = "OpenSearch domain ARN (optional, uses default pattern if empty)"
  type        = string
  default     = ""
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
