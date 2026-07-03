# CloudWatch log group for ECS service logs
resource "aws_cloudwatch_log_group" "bremen" {
  name              = "/ecs/${var.service_name}"
  retention_in_days = var.log_retention_days
}

# ECS cluster
resource "aws_ecs_cluster" "bremen" {
  name = "${var.project_name}-${var.environment}"
}

# Security group for the ECS service
resource "aws_security_group" "bremen_service" {
  name        = "${var.service_name}-${var.environment}"
  description = "Security group for Bremen ECS service"
  vpc_id      = var.vpc_id

  # Ingress from allowed CIDRs (dev-only by default)
  dynamic "ingress" {
    for_each = var.allowed_ingress_cidr_blocks
    content {
      from_port   = var.container_port
      to_port     = var.container_port
      protocol    = "tcp"
      cidr_blocks = [ingress.value]
    }
  }

  # Egress: allow all outbound traffic
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.service_name}-${var.environment}"
    Environment = var.environment
  }
}

# Task definition
resource "aws_ecs_task_definition" "bremen" {
  family                   = var.service_name
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.container_cpu
  memory                   = var.container_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = var.service_name
      image     = "${aws_ecr_repository.bremen.repository_url}:${var.container_image_tag}"
      essential = true

      portMappings = [
        {
          containerPort = var.container_port
          protocol      = "tcp"
        }
      ]

      environment = [
        {
          name  = "BREMEN_MODEL_BUCKET"
          value = aws_s3_bucket.model_packages.bucket
        },
        {
          name  = "BREMEN_MODEL_PREFIX"
          value = var.model_package_prefix
        },
        {
          name  = "BREMEN_MODEL_VERSION"
          value = ""
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.bremen.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }
    }
  ])

  # NOTE: This is infrastructure scaffolding. PR 0019 created a
  # framework-neutral API skeleton, not a real HTTP server. A future
  # PR will wire an actual service runner before any production
  # deployment. desired_count defaults to 0 to prevent automatic
  # deployment.
}

# ECS service
resource "aws_ecs_service" "bremen" {
  name            = "${var.service_name}-${var.environment}"
  cluster         = aws_ecs_cluster.bremen.id
  task_definition = aws_ecs_task_definition.bremen.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.bremen_service.id]
    assign_public_ip = false
  }

  # NOTE: This is scaffolding pending real HTTP serving / deployment
  # decisions. desired_count defaults to 0. No load balancer is
  # configured at this stage.
}
