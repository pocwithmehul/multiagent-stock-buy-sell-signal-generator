# QA Environment Variables
# ========================

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

variable "allowed_cidr_blocks" {
  description = "CIDR blocks allowed to access EKS API"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

# Secrets
variable "openai_api_key" {
  description = "OpenAI API key"
  type        = string
  default     = ""
  sensitive   = true
}

variable "langfuse_public_key" {
  description = "Langfuse public key"
  type        = string
  default     = ""
  sensitive   = true
}

variable "langfuse_secret_key" {
  description = "Langfuse secret key"
  type        = string
  default     = ""
  sensitive   = true
}

variable "twilio_account_sid" {
  description = "Twilio account SID"
  type        = string
  default     = ""
  sensitive   = true
}

variable "twilio_auth_token" {
  description = "Twilio auth token"
  type        = string
  default     = ""
  sensitive   = true
}

# Frontend
variable "frontend_domain_name" {
  description = "Custom domain for frontend (leave empty for CloudFront default)"
  type        = string
  default     = ""
}

# Feature Flags
variable "enable_watchlist_analysis" {
  description = "Enable watchlist-based batch analysis"
  type        = bool
  default     = true  # Enable in QA for testing
}

variable "enable_premarket_analysis" {
  description = "Enable pre-market analysis (4:00 AM - 9:30 AM ET)"
  type        = bool
  default     = true  # Enable in QA for testing
}

variable "enable_aftermarket_analysis" {
  description = "Enable after-market analysis (4:00 PM - 8:00 PM ET)"
  type        = bool
  default     = true  # Enable in QA for testing
}
