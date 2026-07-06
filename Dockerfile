# Bremen — Runtime Service Image
#
# Two build targets:
#
#   smoke      CI validation only — public deps, no private GitHub installs,
#              runs import identity test. Used by quality.yml on every PR.
#
#   production Full runtime service — all deps including private
#              (xrd-preprocessing), non-root user, healthcheck, EXPOSE.
#              Used by ecr-publish.yml for ECR publish.
#
# Build examples:
#   CI smoke:      docker build --target smoke .
#   ECR publish:   docker build --target production \
#                    --build-arg BREMEN_CI_GITHUB_TOKEN=<token> .
#
# Note: server uses stdlib http.server (single-threaded).
# Replacing with gunicorn/uvicorn is tracked as a future PR.
# See ADR-0003 for the API architecture decision.

# ── shared base ────────────────────────────────────────────────────────────
FROM python:3.13-slim AS base

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ /app/src/

# ── smoke target ────────────────────────────────────────────────────────────
FROM base AS smoke-builder

# Install only public dependencies — private deps handled by CI workflow
RUN pip install --no-cache-dir . && \
    pip install --no-cache-dir pytest

FROM python:3.13-slim AS smoke

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

COPY --from=smoke-builder /usr/local/lib/python3.13/site-packages \
                          /usr/local/lib/python3.13/site-packages
COPY --from=smoke-builder /usr/local/bin /usr/local/bin
COPY src/ /app/src/
COPY tests/ /app/tests/

WORKDIR /app

RUN python -m compileall src tests

CMD ["python", "-m", "pytest", "-q", "tests/test_bremen_import_identity.py"]

# ── production target ────────────────────────────────────────────────────────
FROM base AS production

# Build arg for private GitHub dependency — never hardcoded, always from CI.
# ARG (not ENV) — does not persist into the final image.
ARG BREMEN_CI_GITHUB_TOKEN

# Install all dependencies including private xrd-preprocessing.
# Token is configured, used, and removed in one RUN layer —
# it never appears in any cached image layer.
RUN if [ -n "$BREMEN_CI_GITHUB_TOKEN" ]; then \
        git config --global \
            url."https://${BREMEN_CI_GITHUB_TOKEN}@github.com/".insteadOf \
            "https://github.com/"; \
    fi && \
    pip install --no-cache-dir "." && \
    if [ -n "$BREMEN_CI_GITHUB_TOKEN" ]; then \
        git config --global --unset \
            url."https://${BREMEN_CI_GITHUB_TOKEN}@github.com/".insteadOf \
            || true; \
    fi

RUN python -m compileall src

# Non-root user — required for ECS/App Runner security best practices
RUN useradd --system --no-create-home --shell /sbin/nologin bremen
USER bremen

EXPOSE 8080

# Healthcheck for ECS task health / App Runner health check
# Matches the /health route in src/bremen/api/server.py
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c \
        "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" \
        2>/dev/null || exit 1

ENTRYPOINT ["python", "-m", "bremen"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8080"]