output "ecr_repository_url" {
  description = "URL of the ECR repository."
  value       = aws_ecr_repository.bremen.repository_url
}

output "ecr_repository_arn" {
  description = "ARN of the ECR repository."
  value       = aws_ecr_repository.bremen.arn
}

output "model_bucket_name" {
  description = "Name of the model package S3 bucket."
  value       = aws_s3_bucket.model_packages.bucket
}

output "model_bucket_arn" {
  description = "ARN of the model package S3 bucket."
  value       = aws_s3_bucket.model_packages.arn
}

output "model_package_prefix" {
  description = "Prefix for model package objects."
  value       = var.model_package_prefix
}

output "ecs_cluster_name" {
  description = "Name of the ECS cluster."
  value       = aws_ecs_cluster.bremen.name
}

output "ecs_service_name" {
  description = "Name of the ECS service."
  value       = aws_ecs_service.bremen.name
}

output "task_definition_arn" {
  description = "ARN of the ECS task definition."
  value       = aws_ecs_task_definition.bremen.arn
}

output "task_execution_role_arn" {
  description = "ARN of the ECS task execution role."
  value       = aws_iam_role.ecs_execution.arn
}

output "task_role_arn" {
  description = "ARN of the ECS task role."
  value       = aws_iam_role.ecs_task.arn
}

output "log_group_name" {
  description = "Name of the CloudWatch log group."
  value       = aws_cloudwatch_log_group.bremen.name
}

output "service_security_group_id" {
  description = "ID of the ECS service security group."
  value       = aws_security_group.bremen_service.id
}

# ---------------------------------------------------------------------------
# App Runner outputs (smoke / proving target)
# ---------------------------------------------------------------------------

output "app_runner_service_name" {
  description = "Name of the App Runner smoke/proving service."
  value       = aws_apprunner_service.bremen_smoke.service_name
}

output "app_runner_service_url" {
  description = "URL of the App Runner smoke/proving service."
  value       = aws_apprunner_service.bremen_smoke.service_url
}

output "app_runner_service_arn" {
  description = "ARN of the App Runner smoke/proving service."
  value       = aws_apprunner_service.bremen_smoke.arn
}

output "app_runner_image_tag" {
  description = "Image tag used by App Runner auto-deploy."
  value       = var.app_runner_image_tag
}

# ---------------------------------------------------------------------------
# Training ECR outputs
# ---------------------------------------------------------------------------

output "training_ecr_repository_url" {
  description = "URL of the training ECR repository."
  value       = aws_ecr_repository.bremen_training.repository_url
}

output "training_ecr_repository_arn" {
  description = "ARN of the training ECR repository."
  value       = aws_ecr_repository.bremen_training.arn
}

# ---------------------------------------------------------------------------
# Model package outputs
# ---------------------------------------------------------------------------

output "model_version" {
  description = "Active model version string for the runtime."
  value       = var.model_version
}

output "model_uri" {
  description = "S3 URI or equivalent reference for the active model package."
  value       = var.model_uri
}

output "model_checksum" {
  description = "SHA-256 hex digest of the active model package joblib file."
  value       = var.model_checksum
}
