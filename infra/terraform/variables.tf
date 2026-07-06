variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
}

variable "project_name" {
  description = "Project name for resource tagging and naming."
  type        = string
  default     = "bremen"
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)."
  type        = string
  default     = "dev"
}

variable "service_name" {
  description = "Service name for ECS resources."
  type        = string
  default     = "bremen"
}

variable "ecr_repository_name" {
  description = "ECR repository name for the Bremen service image."
  type        = string
  default     = "bremen"
}

variable "model_bucket_name" {
  description = <<-EOT
    Name of the S3 bucket for model packages.
    Human must provide a globally unique name.
  EOT
  type        = string
}

variable "model_package_prefix" {
  description = "Prefix within the model bucket for model package objects."
  type        = string
  default     = "model-packages/"
}

variable "vpc_id" {
  description = "VPC ID where ECS resources are deployed."
  type        = string
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs for ECS service placement."
  type        = list(string)
}

variable "allowed_ingress_cidr_blocks" {
  description = "List of CIDR blocks allowed to reach the service (dev-only placeholder by default)."
  type        = list(string)
  default     = []
}

variable "container_port" {
  description = "Port the Bremen container listens on (planned; PR 0019 skeleton does not yet serve HTTP)."
  type        = number
  default     = 8000
}

variable "container_cpu" {
  description = "CPU units for the Fargate task."
  type        = number
  default     = 512
}

variable "container_memory" {
  description = "Memory (MiB) for the Fargate task."
  type        = number
  default     = 1024
}

variable "desired_count" {
  description = "Desired number of ECS service tasks. Default 0 — human must intentionally raise for deployment."
  type        = number
  default     = 0
}

variable "container_image_tag" {
  description = "Tag of the Bremen image to deploy."
  type        = string
  default     = "latest"
}

variable "log_retention_days" {
  description = "CloudWatch log group retention in days."
  type        = number
  default     = 14
}

# ---------------------------------------------------------------------------
# App Runner variables
# ---------------------------------------------------------------------------

variable "app_runner_image_tag" {
  description = "Image tag used by App Runner auto-deploy. Default 'app-runner'."
  type        = string
  default     = "app-runner"
}

variable "app_runner_instance_role_arn" {
  description = "ARN of an IAM role to associate with the App Runner service for instance-level permissions. Set to null to skip instance role."
  type        = string
  default     = null
}

# ---------------------------------------------------------------------------
# Training ECR variables
# ---------------------------------------------------------------------------

variable "training_ecr_repository_name" {
  description = "ECR repository name for the Bremen training image."
  type        = string
  default     = "bremen-training"
}
