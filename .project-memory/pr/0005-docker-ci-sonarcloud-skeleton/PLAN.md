# PR 0005 — Docker, GitHub Actions, and SonarCloud Skeleton Plan

## Goal

Add the minimal infrastructure skeleton for Bremen Docker packaging, GitHub Actions quality checks, and SonarCloud visibility.

This PR is infrastructure-skeleton only.

It does not change runtime behavior, preprocessing behavior, H5 handling, model behavior, joblib behavior, training behavior, inference behavior, config discovery, config validation, or clinical claims.

## Allowed implementation files

Exactly these files may be added or modified:

- Dockerfile
- .dockerignore
- .github/workflows/quality.yml
- sonar-project.properties

No other repository files may be changed by the implementation.

The later precommit-review stage may write only this review artifact:

- .project-memory/pr/0005-docker-ci-sonarcloud-skeleton/reviews/precommit-review.yml

## Docker contract

The Dockerfile is for non-clinical build and smoke validation.

The Docker image must not intentionally include H5/HDF5 data, model artifacts, credentials, repository metadata, virtual environments, caches, or project-memory artifacts.

The Docker work must not push images, deploy, download large datasets, or bake credentials.

Required Docker smoke behavior:

- compile the source and tests
- run the focused Bremen import identity test

## GitHub Actions contract

Add one workflow:

- .github/workflows/quality.yml

The workflow must run on pull requests to main, pushes to main, and manual dispatch.

The workflow must perform:

- checkout
- Python setup
- dependency setup
- dependency import proof
- source and test compile check
- focused Bremen import identity test
- full pytest
- Docker build smoke
- SonarCloud scan

The workflow must not deploy, push Docker images, commit changes, or commit credentials.

## SonarCloud contract

Add one SonarCloud project configuration file:

- sonar-project.properties

SonarCloud is quality visibility only in PR 0005.

SonarCloud is not a release gate in PR 0005.

The SonarCloud token must come only from a GitHub Secret named:

- SONAR_TOKEN

No token value may be committed.

If the exact SonarCloud organization or project key is unknown, the coder must stop and report a blocker before writing sonar-project.properties.

## Private dependency strategy

Use one private dependency strategy only: SSH deploy key through GitHub Secrets.

Required GitHub Secret:

- BREMEN_CI_SSH_PRIVATE_KEY

The human must configure that key as read-only access for:

- Eos-Dx/XRD-preprocessing
- Eos-Dx/container

The CI dependency setup must install:

- XRD-preprocessing from the Eos-Dx GitHub repository
- container from Eos-Dx/container branch feat/v0_3-eoscan-session-container

Required dependency proof:

- xrd_preprocessing imports
- container imports
- container VERSION_REGISTRY contains 0_3

If the required secret is absent or dependency setup fails, CI must fail with an explicit message.

No private key, token, deploy key, or credential value may be committed.

## Validation policy

Plan-review is static only. It must not run Docker, pytest, or dependency installation. It only verifies that this plan requires implementation and precommit checks later.

Local implementation and precommit-review must run and pass:

- dependency import proof
- source and test compile check
- focused Bremen import identity test
- full pytest
- secret material scan
- no data fixture changes check
- no H5/HDF5 modification check
- no unexpected file changes check

Local Docker validation:

- if Docker is available, Docker build and Docker smoke must pass
- if Docker is unavailable locally, precommit-review records a warning

CI validation requires:

- private dependency setup through BREMEN_CI_SSH_PRIVATE_KEY
- dependency import proof
- source and test compile check
- focused Bremen import identity test
- full pytest
- Docker build smoke
- SonarCloud scan with SONAR_TOKEN

## Safety boundaries

PR 0005 must not:

- change runtime behavior
- change preprocessing semantics
- change H5 reader behavior
- change model or joblib behavior
- change training behavior
- implement API or deployment
- implement config discovery
- implement config validation
- push Docker images
- deploy anything
- commit credentials
- modify H5/HDF5 data
- modify test data

## Plan Drift Gate

Precommit-review must check:

- changed files match the four allowed implementation files plus the precommit-review artifact
- Docker skeleton matches this plan
- GitHub Actions workflow matches this plan
- SonarCloud configuration matches this plan
- private dependency strategy matches this plan
- secret handling matches this plan
- validation policy is consistent
- runtime behavior did not change
- ML, preprocessing, H5, model, and joblib behavior did not change
- config discovery and config validation were not implemented
- Docker image push and deployment were not added
- all required implementation and precommit checks were recorded

## Stop conditions

Block if:

- any file outside the allowed implementation files is changed
- any credential value is committed
- CI private dependency setup is hidden or unclear
- required local checks are not run
- required local checks fail
- Docker is available locally and Docker build or smoke fails
- Docker image push or deployment is added
- SonarCloud is presented as a release gate
- runtime behavior changes
- preprocessing, H5, model, or joblib behavior changes
- config discovery is implemented
- config validation is implemented
- H5/HDF5 data or test data changes
