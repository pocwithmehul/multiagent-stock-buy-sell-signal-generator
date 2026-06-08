# AppConfig Module Variables
# ==========================

variable "environment" {
  description = "Environment name (qa, stg, prod)"
  type        = string

  validation {
    condition     = contains(["qa", "stg", "prod"], var.environment)
    error_message = "Environment must be one of: qa, stg, prod"
  }
}

variable "config_version" {
  description = "Version identifier for the configuration"
  type        = string
  default     = "1"
}

# ─────────────────────────────────────────────────────────────────────────────
# Feature Flag Defaults
# ─────────────────────────────────────────────────────────────────────────────

variable "flag_single_stock_analysis" {
  description = "Enable single stock analysis (core feature)"
  type        = bool
  default     = true
}

variable "flag_watchlist_analysis" {
  description = "Enable watchlist-based batch analysis"
  type        = bool
  default     = false
}

variable "flag_premarket_analysis" {
  description = "Enable pre-market analysis (4:00 AM - 9:30 AM ET)"
  type        = bool
  default     = false
}

variable "flag_aftermarket_analysis" {
  description = "Enable after-market analysis (4:00 PM - 8:00 PM ET)"
  type        = bool
  default     = false
}

# ─────────────────────────────────────────────────────────────────────────────
# Tags
# ─────────────────────────────────────────────────────────────────────────────

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
