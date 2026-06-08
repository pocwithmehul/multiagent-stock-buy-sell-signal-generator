# PROD Environment Configuration
# ==============================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.30"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.24"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.12"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Environment = "prod"
      Project     = "stock-signal"
      ManagedBy   = "terraform"
    }
  }
}

locals {
  name        = "stock-signal-prod"
  environment = "prod"
  tags = {
    Environment = local.environment
    Project     = "stock-signal"
  }
}

# ─────────────────────────────────────────────────────────────────────────────
# VPC
# ─────────────────────────────────────────────────────────────────────────────

module "vpc" {
  source = "../../modules/vpc"

  name               = local.name
  region             = var.region
  vpc_cidr           = var.vpc_cidr
  cluster_name       = local.name
  single_nat_gateway = false  # Full HA with NAT per AZ

  enable_ecr_endpoint     = true
  enable_bedrock_endpoint = true
  enable_secrets_endpoint = true

  tags = local.tags
}

# ─────────────────────────────────────────────────────────────────────────────
# EKS
# ─────────────────────────────────────────────────────────────────────────────

module "eks" {
  source = "../../modules/eks"

  cluster_name       = local.name
  region             = var.region
  environment        = local.environment
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids

  # PROD-sized cluster (full HA)
  node_instance_types = ["m5.xlarge"]
  node_desired_size   = 6
  node_min_size       = 3
  node_max_size       = 12

  # Restrict public access in production
  enable_public_access = var.enable_public_access
  public_access_cidrs  = var.allowed_cidr_blocks

  tags = local.tags
}

# ─────────────────────────────────────────────────────────────────────────────
# MSK (Kafka)
# ─────────────────────────────────────────────────────────────────────────────

module "msk" {
  source = "../../modules/msk"

  name               = local.name
  vpc_id             = module.vpc.vpc_id
  vpc_cidr           = module.vpc.vpc_cidr
  private_subnet_ids = module.vpc.private_subnet_ids

  # PROD-sized Kafka cluster (6 brokers for HA)
  broker_count         = 6
  broker_instance_type = "kafka.m5.large"
  broker_volume_size   = 500
  kafka_version        = "3.5.1"

  enable_monitoring = true
  tags              = local.tags
}

# ─────────────────────────────────────────────────────────────────────────────
# OpenSearch
# ─────────────────────────────────────────────────────────────────────────────

module "opensearch" {
  source = "../../modules/opensearch"

  name               = local.name
  region             = var.region
  vpc_id             = module.vpc.vpc_id
  vpc_cidr           = module.vpc.vpc_cidr
  private_subnet_ids = module.vpc.private_subnet_ids

  # PROD-sized OpenSearch (6 nodes with dedicated masters)
  instance_type  = "r6g.xlarge.search"
  instance_count = 6
  volume_size    = 300

  tags = local.tags
}

# ─────────────────────────────────────────────────────────────────────────────
# IAM Policies
# ─────────────────────────────────────────────────────────────────────────────

module "iam" {
  source = "../../modules/iam"

  name                  = local.name
  region                = var.region
  environment           = local.environment
  msk_cluster_arn       = module.msk.cluster_arn
  opensearch_domain_arn = module.opensearch.domain_arn

  tags = local.tags
}

# ─────────────────────────────────────────────────────────────────────────────
# Secrets
# ─────────────────────────────────────────────────────────────────────────────

module "secrets" {
  source = "../../modules/secrets"

  environment             = local.environment
  recovery_window_in_days = 30  # Longer recovery for prod

  openai_api_key      = var.openai_api_key
  langfuse_public_key = var.langfuse_public_key
  langfuse_secret_key = var.langfuse_secret_key
  twilio_account_sid  = var.twilio_account_sid
  twilio_auth_token   = var.twilio_auth_token

  tags = local.tags
}

# ─────────────────────────────────────────────────────────────────────────────
# AppConfig (Feature Flags)
# ─────────────────────────────────────────────────────────────────────────────

module "appconfig" {
  source = "../../modules/appconfig"

  environment = local.environment

  # Feature flag defaults for PROD (conservative - most features disabled by default)
  flag_single_stock_analysis = true
  flag_watchlist_analysis    = var.enable_watchlist_analysis
  flag_premarket_analysis    = var.enable_premarket_analysis
  flag_aftermarket_analysis  = var.enable_aftermarket_analysis

  tags = local.tags
}

# ─────────────────────────────────────────────────────────────────────────────
# Frontend (React Dashboard)
# ─────────────────────────────────────────────────────────────────────────────

module "frontend" {
  source = "../../modules/frontend"

  name        = local.name
  bucket_name = "${local.name}-frontend"
  domain_name = var.frontend_domain_name

  price_class        = "PriceClass_All"  # Global distribution for prod
  create_deploy_user = true

  # Production: Add WAF protection
  # waf_acl_arn = aws_wafv2_web_acl.frontend.arn

  tags = local.tags
}

# ─────────────────────────────────────────────────────────────────────────────
# Kubernetes Provider
# ─────────────────────────────────────────────────────────────────────────────

provider "kubernetes" {
  host                   = module.eks.cluster_endpoint
  cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)

  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
  }
}

provider "helm" {
  kubernetes {
    host                   = module.eks.cluster_endpoint
    cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)

    exec {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "aws"
      args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
    }
  }
}
