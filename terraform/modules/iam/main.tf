# IAM Module for Stock Signal API
# ================================
# Creates IAM policies for Bedrock, MSK, and OpenSearch access.

locals {
  tags = merge(var.tags, {
    Module = "iam"
  })
}

data "aws_caller_identity" "current" {}

# ─────────────────────────────────────────────────────────────────────────────
# Bedrock Access Policy
# ─────────────────────────────────────────────────────────────────────────────

resource "aws_iam_policy" "bedrock_access" {
  name        = "${var.name}-bedrock-access"
  description = "Allows access to AWS Bedrock for LLM inference"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "BedrockInvoke"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = [
          "arn:aws:bedrock:${var.region}::foundation-model/anthropic.*",
          "arn:aws:bedrock:${var.region}::foundation-model/amazon.*"
        ]
      },
      {
        Sid    = "BedrockList"
        Effect = "Allow"
        Action = [
          "bedrock:ListFoundationModels"
        ]
        Resource = "*"
      }
    ]
  })

  tags = local.tags
}

# ─────────────────────────────────────────────────────────────────────────────
# MSK Access Policy
# ─────────────────────────────────────────────────────────────────────────────

resource "aws_iam_policy" "msk_access" {
  name        = "${var.name}-msk-access"
  description = "Allows access to Amazon MSK for Kafka operations"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "MSKConnect"
        Effect = "Allow"
        Action = [
          "kafka-cluster:Connect",
          "kafka-cluster:DescribeCluster"
        ]
        Resource = var.msk_cluster_arn != "" ? var.msk_cluster_arn : "arn:aws:kafka:${var.region}:${data.aws_caller_identity.current.account_id}:cluster/${var.name}/*"
      },
      {
        Sid    = "MSKTopics"
        Effect = "Allow"
        Action = [
          "kafka-cluster:CreateTopic",
          "kafka-cluster:DescribeTopic",
          "kafka-cluster:AlterTopic",
          "kafka-cluster:DeleteTopic",
          "kafka-cluster:WriteData",
          "kafka-cluster:ReadData"
        ]
        Resource = var.msk_cluster_arn != "" ? "${var.msk_cluster_arn}/*" : "arn:aws:kafka:${var.region}:${data.aws_caller_identity.current.account_id}:topic/${var.name}/*"
      },
      {
        Sid    = "MSKGroups"
        Effect = "Allow"
        Action = [
          "kafka-cluster:AlterGroup",
          "kafka-cluster:DescribeGroup"
        ]
        Resource = var.msk_cluster_arn != "" ? "${var.msk_cluster_arn}/*" : "arn:aws:kafka:${var.region}:${data.aws_caller_identity.current.account_id}:group/${var.name}/*"
      }
    ]
  })

  tags = local.tags
}

# ─────────────────────────────────────────────────────────────────────────────
# OpenSearch Access Policy
# ─────────────────────────────────────────────────────────────────────────────

resource "aws_iam_policy" "opensearch_access" {
  name        = "${var.name}-opensearch-access"
  description = "Allows access to Amazon OpenSearch for vector search"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "OpenSearchHTTP"
        Effect = "Allow"
        Action = [
          "es:ESHttpGet",
          "es:ESHttpPut",
          "es:ESHttpPost",
          "es:ESHttpDelete",
          "es:ESHttpHead"
        ]
        Resource = var.opensearch_domain_arn != "" ? "${var.opensearch_domain_arn}/*" : "arn:aws:es:${var.region}:${data.aws_caller_identity.current.account_id}:domain/${var.name}/*"
      },
      {
        Sid    = "OpenSearchDescribe"
        Effect = "Allow"
        Action = [
          "es:DescribeDomain",
          "es:DescribeDomains"
        ]
        Resource = var.opensearch_domain_arn != "" ? var.opensearch_domain_arn : "arn:aws:es:${var.region}:${data.aws_caller_identity.current.account_id}:domain/${var.name}"
      }
    ]
  })

  tags = local.tags
}

# ─────────────────────────────────────────────────────────────────────────────
# Secrets Manager Access Policy
# ─────────────────────────────────────────────────────────────────────────────

resource "aws_iam_policy" "secrets_access" {
  name        = "${var.name}-secrets-access"
  description = "Allows access to AWS Secrets Manager"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "SecretsRead"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = "arn:aws:secretsmanager:${var.region}:${data.aws_caller_identity.current.account_id}:secret:stock-signal/${var.environment}/*"
      },
      {
        Sid    = "SecretsList"
        Effect = "Allow"
        Action = [
          "secretsmanager:ListSecrets"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "secretsmanager:ResourceTag/Environment" = var.environment
          }
        }
      }
    ]
  })

  tags = local.tags
}

# ─────────────────────────────────────────────────────────────────────────────
# CloudWatch Logs Policy
# ─────────────────────────────────────────────────────────────────────────────

resource "aws_iam_policy" "cloudwatch_logs" {
  name        = "${var.name}-cloudwatch-logs"
  description = "Allows writing to CloudWatch Logs"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams"
        ]
        Resource = "arn:aws:logs:${var.region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/stock-signal/*"
      }
    ]
  })

  tags = local.tags
}

# ─────────────────────────────────────────────────────────────────────────────
# Combined Policy for Stock Signal API
# ─────────────────────────────────────────────────────────────────────────────

resource "aws_iam_policy" "stock_signal_combined" {
  name        = "${var.name}-stock-signal-api"
  description = "Combined policy for Stock Signal API"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      jsondecode(aws_iam_policy.bedrock_access.policy).Statement,
      jsondecode(aws_iam_policy.msk_access.policy).Statement,
      jsondecode(aws_iam_policy.opensearch_access.policy).Statement,
      jsondecode(aws_iam_policy.secrets_access.policy).Statement,
      jsondecode(aws_iam_policy.cloudwatch_logs.policy).Statement
    )
  })

  tags = local.tags
}
