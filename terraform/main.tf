# Terraform configuration for AI Code Review Bot ECS Deployment
# Provider: AWS
# Region: us-east-1
# Infrastructure: VPC, ECS Fargate, ALB, ECR

terraform {
  required_version = ">= 1.5.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Optional: Configure S3 backend for state storage
  # Uncomment and configure after creating S3 bucket
  # backend "s3" {
  #   bucket         = "your-terraform-state-bucket"
  #   key            = "np-code-review/terraform.tfstate"
  #   region         = "us-east-1"
  #   encrypt        = true
  #   dynamodb_table = "terraform-state-lock"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
      Application = "AI-Code-Review-Bot"
    }
  }
}

# Data source for current AWS account
data "aws_caller_identity" "current" {}

# Data source for availability zones
data "aws_availability_zones" "available" {
  state = "available"
}
