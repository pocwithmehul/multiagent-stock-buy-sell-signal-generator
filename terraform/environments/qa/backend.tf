# QA Environment Backend Configuration
# =====================================
# S3 backend for state storage with DynamoDB locking

terraform {
  backend "s3" {
    bucket         = "stock-signal-terraform-state"
    key            = "qa/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "stock-signal-terraform-locks"
  }
}
