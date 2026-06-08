# QA Environment Variables
# ========================

region   = "us-east-1"
vpc_cidr = "10.0.0.0/16"

# Restrict EKS API access (update with your IP ranges)
allowed_cidr_blocks = ["0.0.0.0/0"]

# Secrets are set via environment variables or CI/CD:
# TF_VAR_openai_api_key
# TF_VAR_langfuse_public_key
# TF_VAR_langfuse_secret_key
# TF_VAR_twilio_account_sid
# TF_VAR_twilio_auth_token
