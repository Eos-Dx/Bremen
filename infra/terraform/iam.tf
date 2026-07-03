# ECS task execution role
resource "aws_iam_role" "ecs_execution" {
  name = "${var.service_name}-execution-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

# ECS task execution role policy — scoped to ECR pull and CloudWatch logs
resource "aws_iam_role_policy" "ecs_execution" {
  name = "${var.service_name}-execution-policy-${var.environment}"
  role = aws_iam_role.ecs_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ECRAuth"
        Effect   = "Allow"
        Action   = "ecr:GetAuthorizationToken"
        Resource = "*"
        # AWS-required: ECR does not support repository-level scoping
        # for GetAuthorizationToken. This is the only wildcard Resource
        # exception.
      },
      {
        Sid    = "ECRPull"
        Effect = "Allow"
        Action = [
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchCheckLayerAvailability",
        ]
        Resource = aws_ecr_repository.bremen.arn
      },
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ]
        Resource = "${aws_cloudwatch_log_group.bremen.arn}:*"
      },
    ]
  })
}

# ECS task role
resource "aws_iam_role" "ecs_task" {
  name = "${var.service_name}-task-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

# ECS task role policy — scoped to model package read access only
resource "aws_iam_role_policy" "ecs_task" {
  name = "${var.service_name}-task-policy-${var.environment}"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "S3ModelRead"
        Effect   = "Allow"
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.model_packages.arn}/${var.model_package_prefix}*"
      },
    ]
  })
}
