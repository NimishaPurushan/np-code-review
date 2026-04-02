# Deploy infrastructure and update ECS service
# PowerShell script for Windows

param(
    [string]$ProjectName = "np-code-review",
    [string]$Environment = "dev",
    [string]$AwsRegion = "us-east-1"
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Green
Write-Host "Deploying Infrastructure" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green

# Change to terraform directory
Set-Location terraform

# Initialize Terraform if needed
if (-not (Test-Path ".terraform")) {
    Write-Host "Initializing Terraform..." -ForegroundColor Yellow
    terraform init
}

# Validate configuration
Write-Host "Validating Terraform configuration..." -ForegroundColor Yellow
terraform validate

# Plan changes
Write-Host "Planning Terraform changes..." -ForegroundColor Yellow
terraform plan -out=tfplan

# Apply changes
Write-Host "Applying Terraform changes..." -ForegroundColor Yellow
terraform apply tfplan

# Clean up plan file
Remove-Item tfplan -ErrorAction SilentlyContinue

# Get ECS cluster and service names
$ClusterName = terraform output -raw ecs_cluster_name
$ServiceName = terraform output -raw ecs_service_name

# Force new deployment to pull latest image
Write-Host "Forcing new ECS deployment..." -ForegroundColor Yellow
aws ecs update-service `
    --cluster $ClusterName `
    --service $ServiceName `
    --force-new-deployment `
    --region $AwsRegion `
    | Out-Null

Write-Host "========================================" -ForegroundColor Green
Write-Host "Deployment completed successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green

# Display important outputs
$AlbUrl = terraform output -raw alb_url
$HealthCheckUrl = terraform output -raw health_check_url
$WebhookUrl = terraform output -raw github_webhook_url
$LogGroup = terraform output -raw cloudwatch_log_group

Write-Host "Application URL: $AlbUrl" -ForegroundColor Yellow
Write-Host "Health Check URL: $HealthCheckUrl" -ForegroundColor Yellow
Write-Host "GitHub Webhook URL: $WebhookUrl" -ForegroundColor Yellow
Write-Host "CloudWatch Logs: $LogGroup" -ForegroundColor Yellow

Write-Host ""
Write-Host "To view logs, run:" -ForegroundColor Yellow
Write-Host "  aws logs tail $LogGroup --follow --region $AwsRegion"
