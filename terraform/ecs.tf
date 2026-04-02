# ECS Cluster, Task Definition, and Service

# CloudWatch Log Group for ECS
resource "aws_cloudwatch_log_group" "ecs" {
  name              = "/ecs/${var.project_name}-${var.environment}"
  retention_in_days = 7

  tags = {
    Name = "${var.project_name}-${var.environment}-logs"
  }
}

# ECS Cluster
resource "aws_ecs_cluster" "main" {
  name = "${var.project_name}-${var.environment}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-cluster"
  }
}

# ECS Task Definition
resource "aws_ecs_task_definition" "app" {
  family                   = "${var.project_name}-${var.environment}"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.ecs_task_cpu
  memory                   = var.ecs_task_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = "${var.project_name}-${var.environment}"
      image     = "${aws_ecr_repository.app.repository_url}:${var.ecr_image_tag}"
      essential = true

      portMappings = [
        {
          containerPort = var.container_port
          protocol      = "tcp"
        }
      ]

      environment = [
        {
          name  = "AUTO_REVIEW_ENABLED"
          value = "true"
        },
        {
          name  = "REVIEW_ON_READY_FOR_REVIEW"
          value = "true"
        },
        {
          name  = "REVIEW_ON_NEW_COMMITS"
          value = "true"
        },
        {
          name  = "DATABASE_URL"
          value = "sqlite+aiosqlite:///./code_review.db"
        }
      ]

      secrets = [
        {
          name      = "GITHUB_APP_ID"
          valueFrom = "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:${var.github_app_secret_name}:GITHUB_APP_ID::"
        },
        {
          name      = "GITHUB_PRIVATE_KEY"
          valueFrom = "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:${var.github_app_secret_name}:GITHUB_PRIVATE_KEY::"
        },
        {
          name      = "GITHUB_WEBHOOK_SECRET"
          valueFrom = "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:${var.github_webhook_secret_name}:GITHUB_WEBHOOK_SECRET::"
        },
        {
          name      = "AZURE_OPENAI_ENDPOINT"
          valueFrom = "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:${var.azure_openai_credentials_secret_name}:AZURE_OPENAI_ENDPOINT::"
        },
        {
          name      = "AZURE_OPENAI_TENANT_ID"
          valueFrom = "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:${var.azure_openai_credentials_secret_name}:AZURE_OPENAI_TENANT_ID::"
        },
        {
          name      = "AZURE_OPENAI_CLIENT_ID"
          valueFrom = "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:${var.azure_openai_credentials_secret_name}:AZURE_OPENAI_CLIENT_ID::"
        },
        {
          name      = "AZURE_OPENAI_CLIENT_SECRET"
          valueFrom = "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:${var.azure_openai_credentials_secret_name}:AZURE_OPENAI_CLIENT_SECRET::"
        },
        {
          name      = "AZURE_OPENAI_API_VERSION"
          valueFrom = "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:${var.azure_openai_credentials_secret_name}:AZURE_OPENAI_API_VERSION::"
        },
        {
          name      = "AZURE_OPENAI_DEPLOYMENT_NAME"
          valueFrom = "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:${var.azure_openai_credentials_secret_name}:AZURE_OPENAI_DEPLOYMENT_NAME::"
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }

      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost:${var.container_port}/health || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }
    }
  ])

  tags = {
    Name = "${var.project_name}-${var.environment}-task-definition"
  }
}

# ECS Service
resource "aws_ecs_service" "app" {
  name            = "${var.project_name}-${var.environment}-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = var.ecs_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.app.arn
    container_name   = "${var.project_name}-${var.environment}"
    container_port   = var.container_port
  }

  deployment_maximum_percent         = 200
  deployment_minimum_healthy_percent = 100
  health_check_grace_period_seconds  = 60

  depends_on = [
    aws_lb_listener.http,
    aws_iam_role_policy_attachment.ecs_task_execution
  ]

  tags = {
    Name = "${var.project_name}-${var.environment}-service"
  }
}
