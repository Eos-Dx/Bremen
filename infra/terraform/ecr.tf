resource "aws_ecr_repository" "bremen" {
  name                 = var.ecr_repository_name
  image_tag_mutability = "MUTABLE"

  # Image scanning on push enabled for vulnerability detection
  image_scanning_configuration {
    scan_on_push = true
  }

  # TODO: Add lifecycle policy when retention requirements are known.
  # Current default: no automatic deletion. A lifecycle policy should be
  # added before production use to manage untagged and old images.
}
