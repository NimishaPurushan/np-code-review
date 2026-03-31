output "aws_region" {
  description = "AWS region where resources are deployed"
  value       = var.aws_region
}

output "aws_account_id" {
  description = "AWS Account ID"
  value       = data.aws_caller_identity.current.account_id
}

output "bedrock_execution_role_arn" {
  description = "ARN of the Bedrock execution role"
  value       = aws_iam_role.bedrock_execution_role.arn
}

output "app_bedrock_role_arn" {
  description = "ARN of the application role for Bedrock access"
  value       = aws_iam_role.app_bedrock_role.arn
}

output "bedrock_log_group_name" {
  description = "Name of the CloudWatch log group for Bedrock"
  value       = var.enable_model_invocation_logging ? aws_cloudwatch_log_group.bedrock_logs[0].name : null
}

output "dev_user_name" {
  description = "IAM user name for development"
  value       = aws_iam_user.bedrock_dev_user.name
}

output "dev_user_access_key_id" {
  description = "Access key ID for dev user (store securely!)"
  value       = aws_iam_access_key.bedrock_dev_user_key.id
  sensitive   = true
}

output "dev_user_secret_access_key" {
  description = "Secret access key for dev user (store securely!)"
  value       = aws_iam_access_key.bedrock_dev_user_key.secret
  sensitive   = true
}

output "enabled_model_ids" {
  description = "List of enabled Bedrock model IDs"
  value       = var.bedrock_model_ids
}
