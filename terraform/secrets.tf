# AWS Secrets Manager Configuration
# This file defines the secret names that must be created manually before deployment

# Note: Secrets must be created manually in AWS Secrets Manager before running Terraform
# These data sources reference existing secrets

# To create secrets, run:
# aws secretsmanager create-secret --name np-code-review/github-app \
#   --secret-string '{
#     "GITHUB_APP_ID":"123456",
#     "GITHUB_PRIVATE_KEY":"-----BEGIN RSA PRIVATE KEY-----\nYour\nPrivate\nKey\nHere\n-----END RSA PRIVATE KEY-----"
#   }'
#
# aws secretsmanager create-secret --name np-code-review/github-webhook-secret \
#   --secret-string '{"GITHUB_WEBHOOK_SECRET":"your-webhook-secret-here"}'
#
# aws secretsmanager create-secret --name np-code-review/azure-openai-credentials \
#   --secret-string '{
#     "AZURE_OPENAI_ENDPOINT":"https://your-resource.openai.azure.com",
#     "AZURE_OPENAI_TENANT_ID":"your-tenant-id",
#     "AZURE_OPENAI_CLIENT_ID":"your-client-id",
#     "AZURE_OPENAI_CLIENT_SECRET":"your-client-secret",
#     "AZURE_OPENAI_API_VERSION":"2024-08-01-preview",
#     "AZURE_OPENAI_DEPLOYMENT_NAME":"your-deployment-name"
#   }'

# Data sources to reference existing secrets
data "aws_secretsmanager_secret" "github_app" {
  name = var.github_app_secret_name
}

data "aws_secretsmanager_secret" "github_webhook_secret" {
  name = var.github_webhook_secret_name
}

data "aws_secretsmanager_secret" "azure_openai_credentials" {
  name = var.azure_openai_credentials_secret_name
}

# Output secret ARNs for reference
output "secret_arns" {
  description = "ARNs of secrets used by the application"
  value = {
    github_app                = data.aws_secretsmanager_secret.github_app.arn
    github_webhook_secret     = data.aws_secretsmanager_secret.github_webhook_secret.arn
    azure_openai_credentials  = data.aws_secretsmanager_secret.azure_openai_credentials.arn
  }
}
