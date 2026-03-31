# IAM Role for Bedrock model invocation
resource "aws_iam_role" "bedrock_execution_role" {
  name = "${var.project_name}-bedrock-execution-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "bedrock.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-bedrock-execution-role"
  }
}

# IAM Policy for Bedrock model invocation
resource "aws_iam_role_policy" "bedrock_invocation_policy" {
  name = "${var.project_name}-bedrock-invocation-policy"
  role = aws_iam_role.bedrock_execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
        ]
        Resource = [
          for model_id in var.bedrock_model_ids :
          "arn:aws:bedrock:${data.aws_region.current.name}::foundation-model/${model_id}"
        ]
      }
    ]
  })
}

# IAM Role for application to invoke Bedrock
resource "aws_iam_role" "app_bedrock_role" {
  name = "${var.project_name}-app-bedrock-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      },
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-app-bedrock-role"
  }
}

# IAM Policy for application to use Bedrock
resource "aws_iam_role_policy" "app_bedrock_policy" {
  name = "${var.project_name}-app-bedrock-policy"
  role = aws_iam_role.app_bedrock_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
          "bedrock:ListFoundationModels",
          "bedrock:GetFoundationModel",
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "bedrock-agent:InvokeAgent",
          "bedrock-agent-runtime:InvokeAgent",
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ]
        Resource = "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:/aws/bedrock/*"
      }
    ]
  })
}

# CloudWatch Log Group for Bedrock invocations
resource "aws_cloudwatch_log_group" "bedrock_logs" {
  count = var.enable_model_invocation_logging ? 1 : 0

  name              = "/aws/bedrock/${var.project_name}-${var.environment}"
  retention_in_days = var.log_retention_days

  tags = {
    Name = "${var.project_name}-bedrock-logs"
  }
}

# IAM Policy for CloudWatch Logs
resource "aws_iam_role_policy" "bedrock_logging_policy" {
  count = var.enable_model_invocation_logging ? 1 : 0

  name = "${var.project_name}-bedrock-logging-policy"
  role = aws_iam_role.bedrock_execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ]
        Resource = aws_cloudwatch_log_group.bedrock_logs[0].arn
      }
    ]
  })
}

# IAM User for local development (optional)
resource "aws_iam_user" "bedrock_dev_user" {
  name = "${var.project_name}-bedrock-dev-${var.environment}"

  tags = {
    Name        = "${var.project_name}-bedrock-dev-user"
    Environment = var.environment
  }
}

# Attach policy to dev user
resource "aws_iam_user_policy_attachment" "bedrock_dev_user_policy" {
  user       = aws_iam_user.bedrock_dev_user.name
  policy_arn = aws_iam_policy.bedrock_full_access.arn
}

# Create an IAM policy for full Bedrock access
resource "aws_iam_policy" "bedrock_full_access" {
  name        = "${var.project_name}-bedrock-full-access-${var.environment}"
  description = "Full access to Amazon Bedrock for ${var.project_name}"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:*",
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ]
        Resource = "arn:aws:logs:*:*:log-group:/aws/bedrock/*"
      }
    ]
  })
}

# Create access key for dev user (store securely!)
resource "aws_iam_access_key" "bedrock_dev_user_key" {
  user = aws_iam_user.bedrock_dev_user.name
}
