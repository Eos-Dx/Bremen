# App Runner service skeleton — smoke / proving / testing target only.
# See ADR-0008 for the full decision.
# ECS Fargate remains the long-term primary production target.

resource "aws_apprunner_service" "bremen_smoke" {
  service_name = "${var.project_name}-apprunner-${var.environment}"

  source_configuration {
    authentication_configuration {
      access_role_arn = var.app_runner_instance_role_arn != null ? var.app_runner_instance_role_arn : null
    }

    image_repository {
      image_configuration {
        port = var.container_port
      }

      image_identifier      = "${aws_ecr_repository.bremen.repository_url}:${var.app_runner_image_tag}"
      image_repository_type = "ECR"

      # NOTE: ECR pull is authenticated by App Runner's internal ECR
      # integration.  No credentials are stored in this Terraform.
    }

    auto_deployments_enabled = true
  }

  health_check_configuration {
    # The existing runtime /health endpoint serves as App Runner health check.
    # A future startup-readiness PR will add a readiness endpoint.
    path = "/health"
  }

  # No instance role by default — use var.app_runner_instance_role_arn when available.

  tags = {
    Name        = "${var.project_name}-apprunner-${var.environment}"
    Environment = var.environment
    Subtarget   = "smoke-proving"
  }
}
