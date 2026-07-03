resource "aws_s3_bucket" "model_packages" {
  bucket = var.model_bucket_name

  # Human responsibility: ensure bucket name is globally unique.
  # No force_destroy true by default — protect against accidental deletion.
}

resource "aws_s3_bucket_versioning" "model_packages" {
  bucket = aws_s3_bucket.model_packages.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "model_packages" {
  bucket = aws_s3_bucket.model_packages.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "model_packages" {
  bucket = aws_s3_bucket.model_packages.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
