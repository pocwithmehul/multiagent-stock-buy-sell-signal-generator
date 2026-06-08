# PROD Environment Backend Configuration
# =======================================

terraform {
  backend "s3" {
    bucket         = "stock-signal-terraform-state"
    key            = "prod/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "stock-signal-terraform-locks"
  }
}
