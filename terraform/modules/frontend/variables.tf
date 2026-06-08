# Frontend Module Variables
# =========================

variable "name" {
  description = "Name prefix for resources"
  type        = string
}

variable "bucket_name" {
  description = "S3 bucket name for frontend assets"
  type        = string
}

variable "domain_name" {
  description = "Custom domain name (leave empty for CloudFront default)"
  type        = string
  default     = ""
}

variable "price_class" {
  description = "CloudFront price class"
  type        = string
  default     = "PriceClass_100"  # US, Canada, Europe only (cheapest)
  # Options: PriceClass_All, PriceClass_200, PriceClass_100
}

variable "geo_restriction_type" {
  description = "Geo restriction type (none, whitelist, blacklist)"
  type        = string
  default     = "none"
}

variable "geo_restriction_locations" {
  description = "List of country codes for geo restriction"
  type        = list(string)
  default     = []
}

variable "waf_acl_arn" {
  description = "WAF Web ACL ARN (optional)"
  type        = string
  default     = null
}

variable "create_deploy_user" {
  description = "Create IAM user for CI/CD deployments"
  type        = bool
  default     = true
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
