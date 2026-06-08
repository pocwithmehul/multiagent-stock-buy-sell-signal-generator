# PROD Environment Variables
# ==========================

region   = "us-east-1"
vpc_cidr = "10.2.0.0/16"

# IMPORTANT: Restrict EKS API access in production
# Only allow access from VPN or specific corporate IPs
allowed_cidr_blocks  = []  # Set to your VPN/corporate CIDR blocks
enable_public_access = false
