from __future__ import annotations

import subprocess
from pathlib import Path


WORKFLOW = Path(".github/workflows/ecr-publish.yml")


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_ecr_publish_workflow_exists() -> None:
    assert WORKFLOW.is_file()


def test_workflow_triggers_are_main_and_manual_only() -> None:
    text = _workflow_text()
    assert "workflow_dispatch:" in text
    assert "push:" in text
    assert "branches: [main]" in text or "- main" in text
    assert "pull_request" not in text


def test_workflow_permissions_are_minimal_for_static_credentials() -> None:
    text = _workflow_text()
    assert "contents: read" in text
    assert "id-token: write" not in text
    assert "packages: write" not in text


def test_workflow_uses_static_aws_credentials_from_github_secrets() -> None:
    text = _workflow_text()
    assert "aws-actions/configure-aws-credentials" in text
    assert "aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}" in text
    assert "aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}" in text
    assert "aws-region: ${{ env.AWS_REGION }}" in text
    assert "role-to-assume" not in text
    assert "AWS_ROLE_TO_ASSUME" not in text


def test_workflow_uses_ecr_login_and_repository_variables() -> None:
    text = _workflow_text()
    assert "aws-actions/amazon-ecr-login" in text
    assert "AWS_REGION: ${{ vars.AWS_REGION }}" in text
    assert "ECR_REPOSITORY: ${{ vars.ECR_REPOSITORY }}" in text


def test_workflow_builds_and_pushes_docker_image_to_ecr() -> None:
    text = _workflow_text()
    assert "docker build" in text
    assert "docker push" in text
    assert "${{ github.sha }}" in text
    assert ":app-runner" in text
    assert ":latest" in text
    assert "steps.login-ecr.outputs.registry" in text


def test_workflow_passes_private_dependency_token_as_build_arg() -> None:
    text = _workflow_text()
    assert "BREMEN_CI_GITHUB_TOKEN" in text
    assert "--build-arg BREMEN_CI_GITHUB_TOKEN=" in text


def test_workflow_does_not_run_terraform_or_deploy_ecs() -> None:
    text = _workflow_text()
    forbidden = [
        "terraform apply",
        "terraform destroy",
        "terraform init",
        "aws ecs update-service",
        "kubectl",
        "helm",
    ]
    for value in forbidden:
        assert value not in text


def test_workflow_does_not_publish_to_ghcr() -> None:
    text = _workflow_text()
    assert "ghcr.io" not in text


def test_workflow_has_no_hardcoded_aws_key_material() -> None:
    text = _workflow_text()
    assert "AKIA" not in text
    assert "aws_access_key_id" not in text
    assert "aws_secret_access_key" not in text
    assert "BEGIN RSA" not in text
    assert "private_key" not in text


def test_workflow_has_no_local_machine_paths() -> None:
    text = _workflow_text()
    assert "/Users/" not in text
    assert "/home/" not in text
    assert "file://" not in text


def test_terraform_files_are_not_modified() -> None:
    result = subprocess.run(
        ["git", "diff", "--name-only", "--", "infra/terraform"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == ""
