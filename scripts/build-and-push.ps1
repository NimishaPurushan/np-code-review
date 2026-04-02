# Build and Push Docker Image to AWS ECR
# PowerShell script for Windows

param(
    [string]$ProjectName = "np-code-review",
    [string]$Environment = "dev",
    [string]$AwsRegion = "us-east-1",
    [string]$ImageTag = "latest"
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Green
Write-Host "Building and Pushing Docker Image" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green

# Get AWS account ID
Write-Host "Getting AWS account ID..." -ForegroundColor Yellow
$AwsAccountId = (aws sts get-caller-identity --query Account --output text)
Write-Host "AWS Account ID: $AwsAccountId"

# Construct ECR repository URL
$EcrRepository = "$AwsAccountId.dkr.ecr.$AwsRegion.amazonaws.com/$ProjectName-$Environment"
Write-Host "ECR Repository: $EcrRepository"

# Authenticate Docker to ECR
Write-Host "Authenticating to ECR..." -ForegroundColor Yellow
aws ecr get-login-password --region $AwsRegion | docker login --username AWS --password-stdin "$AwsAccountId.dkr.ecr.$AwsRegion.amazonaws.com"

# Build Docker image
Write-Host "Building Docker image..." -ForegroundColor Yellow
docker build -t "${ProjectName}:${ImageTag}" .

# Tag image for ECR
Write-Host "Tagging image for ECR..." -ForegroundColor Yellow
docker tag "${ProjectName}:${ImageTag}" "${EcrRepository}:${ImageTag}"

# Also tag with git commit SHA if in git repository
try {
    $GitSha = git rev-parse --short HEAD 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Tagging with git SHA: $GitSha" -ForegroundColor Yellow
        docker tag "${ProjectName}:${ImageTag}" "${EcrRepository}:${GitSha}"
    }
} catch {
    $GitSha = $null
}

# Push image to ECR
Write-Host "Pushing image to ECR..." -ForegroundColor Yellow
docker push "${EcrRepository}:${ImageTag}"

if ($GitSha) {
    docker push "${EcrRepository}:${GitSha}"
}

Write-Host "========================================" -ForegroundColor Green
Write-Host "Image pushed successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "Repository: $EcrRepository"
Write-Host "Tags: $ImageTag"
if ($GitSha) {
    Write-Host "      $GitSha"
}
