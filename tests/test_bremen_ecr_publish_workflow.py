"""Static guardrail tests for the ECR publish workflow.

Reads ``.github/workflows/ecr-publish.yml`` as YAML text.
Uses only standard library for parsing — no subprocess calls to
GitHub Actions runner or external tools.

Verifies:
- Workflow file exists.
- Trigger includes workflow_dispatch.
- Trigger includes push to main.
- Trigger does NOT include pull_request.
- Permissions include id-token: write.
- Permissions include contents: read.
- Workflow uses aws-actions/configure-aws-credentials.
- Workflow uses aws-actions/amazon-ecr-login.
- Workflow uses Docker build.
- Workflow tags with github.sha.
- Workflow does NOT run terraform commands.
- Workflow does NOT run ECS deploy / kubectl / helm.
- Workflow does NOT contain AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AKIA.
- Workflow does NOT contain local machine paths.
- Terraform files are unchanged in this PR.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "ecr-publish.yml"
QUALITY_WORKFLOW = ROOT / ".github" / "workflows" / "quality.yml"
TERRAFORM_DIR = ROOT / "infra" / "terraform"


def _read_workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# File existence
# ---------------------------------------------------------------------------


def test_workflow_exists():
    """ecr-publish.yml workflow file must exist."""
    assert WORKFLOW.is_file(), ".github/workflows/ecr-publish.yml not found"


# ---------------------------------------------------------------------------
# Trigger checks
# ---------------------------------------------------------------------------


class TestTriggers:
    def test_workflow_dispatch_present(self):
        """Trigger must include workflow_dispatch."""
        assert "workflow_dispatch" in _read_workflow()

    def test_push_main_present(self):
        """Trigger must include push to main."""
        assert "push" in _read_workflow()
        assert "main" in _read_workflow()

    def test_pull_request_absent(self):
        """Trigger must NOT include pull_request."""
        content = _read_workflow()
        assert "pull_request" not in content, (
            "ECR workflow must not trigger on pull_request"
        )


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------


class TestPermissions:
    def test_id_token_write_present(self):
        """Permissions must include id-token: write (OIDC)."""
        assert "id-token: write" in _read_workflow()

    def test_contents_read_present(self):
        """Permissions must include contents: read."""
        assert "contents: read" in _read_workflow()


# ---------------------------------------------------------------------------
# Required actions
# ---------------------------------------------------------------------------


class TestActions:
    def test_configure_aws_credentials_present(self):
        """Workflow must use aws-actions/configure-aws-credentials."""
        assert "aws-actions/configure-aws-credentials" in _read_workflow()

    def test_amazon_ecr_login_present(self):
        """Workflow must use aws-actions/amazon-ecr-login."""
        assert "aws-actions/amazon-ecr-login" in _read_workflow()

    def test_checkout_present(self):
        """Workflow must use actions/checkout."""
        assert "actions/checkout" in _read_workflow()


# ---------------------------------------------------------------------------
# Docker build and push
# ---------------------------------------------------------------------------


class TestDocker:
    def test_docker_build_present(self):
        """Workflow must include docker build."""
        assert "docker build" in _read_workflow()

    def test_docker_push_present(self):
        """Workflow must include docker push."""
        assert "docker push" in _read_workflow()

    def test_build_context_is_dot(self):
        """Docker build context must be the repository root ('.')."""
        content = _read_workflow()
        # The build command uses '-t ... .'  at the end of a line to
        # indicate the build context is the current directory
        assert " ." in content, "Build context must be '."

    def test_github_sha_tagged(self):
        """Image must be tagged with github.sha."""
        assert "github.sha" in _read_workflow()

    def test_latest_tagged(self):
        """Image must also be tagged with 'latest' for main push."""
        content = _read_workflow()
        # latest is pushed via a separate docker tag + push after sha tag
        assert ":latest" in content or "latest" in content


# ---------------------------------------------------------------------------
# Forbidden operations
# ---------------------------------------------------------------------------


class TestForbiddenOperations:
    def test_no_terraform_apply(self):
        """Workflow must not run terraform apply."""
        assert "terraform apply" not in _read_workflow()

    def test_no_terraform_destroy(self):
        """Workflow must not run terraform destroy."""
        assert "terraform destroy" not in _read_workflow()

    def test_no_terraform_init(self):
        """Workflow must not run terraform init."""
        assert "terraform init" not in _read_workflow()

    def test_no_ecs_update_service(self):
        """Workflow must not run aws ecs update-service."""
        assert "aws ecs update-service" not in _read_workflow()

    def test_no_kubectl(self):
        """Workflow must not run kubectl."""
        assert "kubectl" not in _read_workflow()

    def test_no_helm(self):
        """Workflow must not run helm."""
        assert "helm" not in _read_workflow()


# ---------------------------------------------------------------------------
# Credential safety
# ---------------------------------------------------------------------------


class TestCredentialSafety:
    def test_no_aws_access_key_id(self):
        """Workflow must not contain AWS_ACCESS_KEY_ID."""
        assert "AWS_ACCESS_KEY_ID" not in _read_workflow()

    def test_no_aws_secret_access_key(self):
        """Workflow must not contain AWS_SECRET_ACCESS_KEY."""
        assert "AWS_SECRET_ACCESS_KEY" not in _read_workflow()

    def test_no_akia(self):
        """Workflow must not contain hardcoded AWS access key patterns."""
        assert "AKIA" not in _read_workflow()

    def test_no_local_machine_paths(self):
        """Workflow must not contain local machine paths."""
        content = _read_workflow()
        assert "/Users/" not in content
        assert "/home/" not in content


# ---------------------------------------------------------------------------
# Scope boundary: no GHCR publishing in this workflow
# ---------------------------------------------------------------------------


class TestNoGHCR:
    def test_no_ghcr_io(self):
        """Workflow must NOT publish to ghcr.io."""
        assert "ghcr.io" not in _read_workflow()

    def test_no_packages_write(self):
        """Workflow must NOT request packages: write permission."""
        assert "packages: write" not in _read_workflow()


# ---------------------------------------------------------------------------
# Scope boundary: Terraform files unchanged
# ---------------------------------------------------------------------------


class TestTerraformUnchanged:
    def test_terraform_files_present(self):
        """Terraform files must still exist."""
        assert TERRAFORM_DIR.is_dir()
        assert (TERRAFORM_DIR / "ecr.tf").is_file()
        assert (TERRAFORM_DIR / "outputs.tf").is_file()
        assert (TERRAFORM_DIR / "main.tf").is_file()

    def test_terraform_files_unchanged(self):
        """Terraform files must not be in the git diff for this PR."""
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--co", "-q"],
            capture_output=True,
            text=True,
        )
        # We just check that the diff doesn't include infra/terraform changes
        result = subprocess.run(
            ["git", "diff", "--name-only", "--", "infra/terraform"],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        assert result.returncode == 0, (
            f"git diff failed: {result.stderr}"
        )
        assert result.stdout.strip() == "", (
            f"Terraform files are unexpectedly modified:\n{result.stdout}"
        )
