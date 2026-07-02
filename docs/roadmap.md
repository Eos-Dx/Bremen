# Bremen Roadmap

## Completed Milestones

- **PR 0001 — Bremen Agent Workflow**: Established the four-role agent workflow (planner, plan-review, coder, precommit-review) with PLAN.md, review artifacts, drift gates, and evidence capture.
- **PR 0002 — Identity Surfaces**: Updated README.md, AGENTS.md, pyproject.toml description, and docs/repository_cleanup.md to establish Bremen as the primary product identity, with Aramis acknowledged as source material.
- **PR 0003 — Full Alignment**: Renamed the source package from `src/aramis/` to `src/bremen/`, updated all imports, class names, config filenames, test files, CLI entrypoints, and MLflow environment variable.

## Future PRs

### PR 0005 — Docker + GitHub Actions + SonarCloud Skeleton

PR 0005 will add Docker packaging (Dockerfile, .dockerignore) for the Bremen application, with a container smoke test that verifies the container starts and `--help` works. No model or H5 data will be baked into the image, and no secrets will be committed.

PR 0005 will add a GitHub Actions workflow that will run `compileall` across source and test files, `pytest` to execute the existing test suite, a Docker build check to verify the image builds, and a SonarCloud scan for static quality visibility.

PR 0005 will add SonarCloud configuration with project key, organization, and token sourced from human-provided GitHub secrets only. No secrets will be committed. SonarCloud is quality visibility only and is not a release gate.

**Required tests and checks**: compileall, pytest, Docker build smoke verification, SonarCloud scan execution.

### PR 0006 — Unified Bremen Entrypoint and Config Discovery/Loading

PR 0006 will converge Bremen to one command surface, replacing multiple config-specific scripts with a single entrypoint. It will support config selection by name, by explicit file path, or by default discovery. A command to list available configs will be provided when no argument is given.

PR 0006 will load existing config files without changing their semantics. It will not change preprocessing behavior, model behavior, or config file structure.

**Required tests**: Entrypoint unit tests, config discovery and listing tests, config path/name/default resolution tests. Precommit-review evidence with command outputs will be required.

### PR 0007 — Config Validation Contract and Tests

PR 0007 will introduce config validation with a config schema or contract defining required fields and structure. It will produce strict validation errors for missing required fields, invalid paths, unsupported modes, and target/control consistency violations. Validation will integrate with the unified entrypoint from PR 0006.

PR 0007 will not change preprocessing behavior, model behavior, or config file structure. It will not modify H5 or HDF5 files.

**Required tests**: Config validation unit tests, negative validation tests (expecting rejection of invalid configs), target/control consistency tests. Precommit-review evidence with command outputs will be required.

### Later PRs (After PR 0007)

- **Model package contract**: Define the controlled joblib package format, checksum verification, model metadata schema, and loading gate.
- **H5 metadata gate**: Validate H5 metadata against contract, enforce target/control same-patient and opposite-side rules.
- **Inference API**: Prediction endpoint with feature schema validation, QC gates, and required prediction metadata fields.
- **Matador integration**: Platform API integration with Matador as system of record.

## Future Test Policy

| Future PR | Required tests / checks |
|-----------|------------------------|
| PR 0005 | compileall, pytest, Docker build smoke verification, SonarCloud scan execution |
| PR 0006 | Entrypoint unit tests, config discovery/listing tests, config path/name/default resolution tests |
| PR 0007 | Config validation unit tests, negative validation tests (rejection of invalid configs), target/control consistency tests |
| All later PRs | Precommit-review evidence with command outputs for each check |

## Scope Notes

- **PR 0004 is documentation-only**. Docker, GitHub Actions, SonarCloud, unified entrypoint, config discovery, and config validation are **not implemented** in PR 0004. They are planned for future PRs as described above.
- **Config validation is deferred** to PR 0007.
- **Docker, GitHub Actions, and SonarCloud do not exist yet**. They are planned for PR 0005.
- **The unified entrypoint does not exist yet**. It is planned for PR 0006.
- **Config discovery and config loading do not exist yet**. They are planned for PR 0006.
- **Config validation does not exist yet**. It is deferred to PR 0007.
- All future implementation PRs will require tests and precommit-review evidence before merge.
