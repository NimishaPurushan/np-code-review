#!/bin/bash
# Build and Push Docker Image to AWS ECR
# This script builds the Docker image and pushes it to ECR

set -e

# Configuration
PROJECT_NAME="${PROJECT_NAME:-np-code-review}"
ENVIRONMENT="${ENVIRONMENT:-dev}"
AWS_REGION="${AWS_REGION:-us-east-1}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Building and Pushing Docker Image${NC}"
echo -e "${GREEN}========================================${NC}"

# Get AWS account ID
echo -e "${YELLOW}Getting AWS account ID...${NC}"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo -e "AWS Account ID: ${AWS_ACCOUNT_ID}"

# Construct ECR repository URL
ECR_REPOSITORY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${PROJECT_NAME}-${ENVIRONMENT}"
echo -e "ECR Repository: ${ECR_REPOSITORY}"

# Authenticate Docker to ECR
echo -e "${YELLOW}Authenticating to ECR...${NC}"
aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

# Build Docker image
echo -e "${YELLOW}Building Docker image...${NC}"
docker build -t ${PROJECT_NAME}:${IMAGE_TAG} .

# Tag image for ECR
echo -e "${YELLOW}Tagging image for ECR...${NC}"
docker tag ${PROJECT_NAME}:${IMAGE_TAG} ${ECR_REPOSITORY}:${IMAGE_TAG}

# Also tag with git commit SHA if in git repository
if git rev-parse --git-dir > /dev/null 2>&1; then
    GIT_SHA=$(git rev-parse --short HEAD)
    echo -e "${YELLOW}Tagging with git SHA: ${GIT_SHA}${NC}"
    docker tag ${PROJECT_NAME}:${IMAGE_TAG} ${ECR_REPOSITORY}:${GIT_SHA}
fi

# Push image to ECR
echo -e "${YELLOW}Pushing image to ECR...${NC}"
docker push ${ECR_REPOSITORY}:${IMAGE_TAG}

if [ ! -z "${GIT_SHA}" ]; then
    docker push ${ECR_REPOSITORY}:${GIT_SHA}
fi

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Image pushed successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "Repository: ${ECR_REPOSITORY}"
echo -e "Tags: ${IMAGE_TAG}"
if [ ! -z "${GIT_SHA}" ]; then
    echo -e "      ${GIT_SHA}"
fi
