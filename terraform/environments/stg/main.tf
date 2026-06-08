# STG Environment Configuration
# =============================

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
      Environment = "stg"
      Project     = "stock-signal"
      ManagedBy   = "terraform"
    }
  }
}

locals {
  name        = "stock-signal-stg"
  environment = "stg"
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
  single_nat_gateway = false  # Multi-AZ NAT for staging

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

  # STG-sized cluster (larger than QA)
  node_instance_types = ["m5.large"]
  node_desired_size   = 3
  node_min_size       = 2
  node_max_size       = 6

  enable_public_access = true
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

  # STG-sized Kafka cluster
  broker_count         = 3
  broker_instance_type = "kafka.m5.large"
  broker_volume_size   = 200
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

  # STG-sized OpenSearch (3 nodes for HA)
  instance_type  = "r6g.large.search"
  instance_count = 3
  volume_size    = 150

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

  environment = local.environment

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

  # Feature flag defaults for STG
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

  price_class        = "PriceClass_100"
  create_deploy_user = true

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
