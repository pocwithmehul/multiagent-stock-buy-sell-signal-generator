# OpenSearch Module Variables
# ===========================

variable "name" {
  description = "Name of the OpenSearch domain"
  type        = string
}

variable "region" {
  description = "AWS region"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs"
  type        = list(string)
}

variable "engine_version" {
  description = "OpenSearch engine version"
  type        = string
  default     = "OpenSearch_2.11"
}

variable "instance_type" {
  description = "Instance type for data nodes"
  type        = string
  default     = "r6g.large.search"
}

variable "instance_count" {
  description = "Number of data node instances"
  type        = number
  default     = 2
}

variable "master_instance_type" {
  description = "Instance type for dedicated master nodes"
  type        = string
  default     = "r6g.large.search"
}

variable "volume_size" {
  description = "EBS volume size in GB per node"
  type        = number
  default     = 100
}

variable "volume_iops" {
  description = "EBS volume IOPS (gp3)"
  type        = number
  default     = 3000
}

variable "volume_throughput" {
  description = "EBS volume throughput MB/s (gp3)"
  type        = number
  default     = 125
}

variable "kms_key_arn" {
  description = "KMS key ARN for encryption at rest"
  type        = string
  default     = null
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 7
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
