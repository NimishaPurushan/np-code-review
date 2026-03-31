# AWS Bedrock Terraform Infrastructure

This directory contains Terraform configuration for provisioning AWS Bedrock resources for the np-code-review bot.

## Prerequisites

1. **Install Terraform**: [Download Terraform](https://www.terraform.io/downloads.html)
2. **AWS CLI**: [Install AWS CLI](https://aws.amazon.com/cli/)
3. **AWS Credentials**: Configure your AWS credentials

```bash
aws configure
```

## Infrastructure Overview

This Terraform configuration creates:

- **IAM Roles**:
  - Bedrock execution role
  - Application role for Bedrock access
  - Development user for local testing

- **IAM Policies**:
  - Bedrock model invocation permissions
  - CloudWatch logging permissions
  - Agent invocation permissions

- **CloudWatch Log Group**:
  - Bedrock model invocation logs (optional)

- **IAM Access Keys**:
  - Development user access keys (for local development)

## Supported Bedrock Models

- Claude 3.5 Sonnet
- Claude 3.5 Haiku  
- Claude 3 Opus
- (Add more as needed)

## Usage

### 1. Initialize Terraform

```bash
cd terraform
terraform init
```

### 2. Configure Variables

Copy the example variables file:

```bash
cp terraform.tfvars.example terraform.tfvars
```

### 3. Plan Infrastructure

```bash
terraform plan
```

### 4. Apply Infrastructure

```bash
terraform apply
```

### 5. Get Outputs

After applying, retrieve the outputs:

```bash
# Get all outputs
terraform output

# Get sensitive outputs (access keys)
terraform output -json dev_user_access_key_id
terraform output -json dev_user_secret_access_key
```

### 6. Update .env File

Add the AWS credentials to your `.env` file:

```bash
# Get the values
AWS_ACCESS_KEY_ID=$(terraform output -raw dev_user_access_key_id)
AWS_SECRET_ACCESS_KEY=$(terraform output -raw dev_user_secret_access_key)
AWS_REGION=$(terraform output -raw aws_region)

# Add to .env
echo "AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID" >> ../.env
echo "AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY" >> ../.env
echo "AWS_REGION=$AWS_REGION" >> ../.env
```

## Cleanup

To destroy all resources:

```bash
terraform destroy
```

## Security Best Practices

1. **Never commit** `terraform.tfvars` or `.tfstate` files to version control
2. **Use AWS Secrets Manager** or **Parameter Store** for production credentials
3. **Rotate access keys** regularly
4. **Use IAM roles** instead of access keys when running in AWS (EC2, ECS, Lambda)
5. **Enable MFA** for AWS Console access
6. **Use least privilege** IAM policies

## Cost Considerations

- **Bedrock**: Pay-per-use pricing based on tokens processed
- **CloudWatch Logs**: Data ingestion and storage costs
- **IAM**: No cost

Monitor your costs in AWS Cost Explorer.

## Troubleshooting

### Model Access Issues

Some Bedrock models require you to request access in the AWS Console:

1. Go to AWS Console → Bedrock → Model access
2. Request access for the models you want to use
3. Wait for approval (usually instant for most models)

### Permission Denied Errors

Ensure your AWS credentials have permissions to create IAM roles and policies:

```bash
aws sts get-caller-identity
```

## References

- [AWS Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [Anthropic Claude Models](https://docs.anthropic.com/claude/docs)
