terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }

  # Backend intentionally omitted.
  # Human operators must configure a remote backend before any apply.
}

provider "aws" {
  region = var.aws_region

  # No hardcoded credentials. Use AWS CLI / environment variables / IAM role.
}
