# IAM Module Outputs
# ==================

output "bedrock_policy_arn" {
  description = "ARN of Bedrock access policy"
  value       = aws_iam_policy.bedrock_access.arn
}

output "msk_policy_arn" {
  description = "ARN of MSK access policy"
  value       = aws_iam_policy.msk_access.arn
}

output "opensearch_policy_arn" {
  description = "ARN of OpenSearch access policy"
  value       = aws_iam_policy.opensearch_access.arn
}

output "secrets_policy_arn" {
  description = "ARN of Secrets Manager access policy"
  value       = aws_iam_policy.secrets_access.arn
}

output "cloudwatch_logs_policy_arn" {
  description = "ARN of CloudWatch Logs policy"
  value       = aws_iam_policy.cloudwatch_logs.arn
}

output "combined_policy_arn" {
  description = "ARN of combined Stock Signal API policy"
  value       = aws_iam_policy.stock_signal_combined.arn
}
