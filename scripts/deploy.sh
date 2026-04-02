#!/bin/bash
# Deploy infrastructure and update ECS service

set -e

# Configuration
PROJECT_NAME="${PROJECT_NAME:-np-code-review}"
ENVIRONMENT="${ENVIRONMENT:-dev}"
AWS_REGION="${AWS_REGION:-us-east-1}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deploying Infrastructure${NC}"
echo -e "${GREEN}========================================${NC}"

# Change to terraform directory
cd terraform

# Initialize Terraform if needed
if [ ! -d ".terraform" ]; then
    echo -e "${YELLOW}Initializing Terraform...${NC}"
    terraform init
fi

# Validate configuration
echo -e "${YELLOW}Validating Terraform configuration...${NC}"
terraform validate

# Plan changes
echo -e "${YELLOW}Planning Terraform changes...${NC}"
terraform plan -out=tfplan

# Apply changes
echo -e "${YELLOW}Applying Terraform changes...${NC}"
terraform apply tfplan

# Clean up plan file
rm -f tfplan

# Get ECS cluster and service names
CLUSTER_NAME=$(terraform output -raw ecs_cluster_name)
SERVICE_NAME=$(terraform output -raw ecs_service_name)

# Force new deployment to pull latest image
echo -e "${YELLOW}Forcing new ECS deployment...${NC}"
aws ecs update-service \
    --cluster ${CLUSTER_NAME} \
    --service ${SERVICE_NAME} \
    --force-new-deployment \
    --region ${AWS_REGION} \
    > /dev/null

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment completed successfully!${NC}"
echo -e "${GREEN}========================================${NC}"

# Display important outputs
echo -e "${YELLOW}Application URL:${NC} $(terraform output -raw alb_url)"
echo -e "${YELLOW}Health Check URL:${NC} $(terraform output -raw health_check_url)"
echo -e "${YELLOW}GitHub Webhook URL:${NC} $(terraform output -raw github_webhook_url)"
echo -e "${YELLOW}CloudWatch Logs:${NC} $(terraform output -raw cloudwatch_log_group)"

echo ""
echo -e "${YELLOW}To view logs, run:${NC}"
echo "  aws logs tail $(terraform output -raw cloudwatch_log_group) --follow --region ${AWS_REGION}"
