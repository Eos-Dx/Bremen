# Bremen — non-clinical build and smoke validation image
#
# This Dockerfile is for CI smoke testing only.
# It does NOT include H5 data, model artifacts, credentials, or project-memory.
# It does NOT push images, deploy, or download large datasets.
#
# Private dependencies (xrd-preprocessing, container) are installed by the
# CI workflow, not by this Dockerfile. This image installs only public/base
# dependencies and runs the non-clinical Bremen import identity test.

FROM python:3.13-slim AS builder

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency manifests and readme
COPY pyproject.toml README.md ./

# Copy source for bremen package install
COPY src/ /app/src/

# Install bremen package and its public dependencies.
# Private dependencies (xrd-preprocessing, container) are handled
# by the CI workflow and are not needed for the smoke test.
RUN pip install --no-cache-dir . && \
    pip install --no-cache-dir \
        pytest

# --- Smoke stage ---
FROM python:3.13-slim AS smoke

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy source and tests
COPY src/ /app/src/
COPY tests/ /app/tests/

WORKDIR /app

# Verify source and tests compile
RUN python -m compileall src tests

# Run focused Bremen import identity test as smoke validation
CMD ["python", "-m", "pytest", "-q", "tests/test_bremen_import_identity.py"]
