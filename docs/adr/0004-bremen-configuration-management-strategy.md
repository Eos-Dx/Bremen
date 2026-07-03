# ADR-0004: Bremen Configuration Management Strategy

**Status**: Accepted

## Context (cited from evidence)

- Current config is static YAML under `config/preprocessing/`, chained via `extends:` (confirmed in `bremen_one_to_one_minimal_v0_1.yaml`).
- Config files use relative local paths (e.g., `io.output_joblib_path: ../../examples/outputs/...`), coupling Bremen's operating mode to a local checkout.
- Config discovery is implemented in `src/bremen/config.py` with deterministic order: explicit path → `BREMEN_CONFIG` env → `bremen.yml` → `bremen.yaml` → `bremen.toml` → `ConfigNotFoundError`.
- Config loading tests exist in `tests/test_bremen_config_loading.py` (PR 0009).

## Decisions

### Config versioning discipline

Every semantically meaningful config change bumps a version marker; no silent overwrite.

### Config sourcing must become environment-aware for cloud deployment

The PR 0009 discovery order must not be broken. A future PR extends it to support a remote/mounted source (e.g., S3-backed or environment-injected) without changing existing local-discovery semantics.

### Config editing surface (deferred)

The config editing surface is EXPLICITLY DEFERRED — not designed here. Non-negotiable guardrails for when it is built:

1. Must reuse the existing config-validation contract.
2. Must disable unsafe YAML features (no arbitrary Python execution).
3. Must never hot-write to a production-serving config without review/approval.
4. Every write must be versioned and attributable.

## OPEN Decision Gate

| Gate ID | Question | Trigger type | Recommended default | Status |
|---------|----------|-------------|-------------------|--------|
| G-CFG-1 | Build in-house vs. adopt an existing config-management/feature-flag product | Date-bound (before PR 0024) | Not decided (no default stated) | OPEN |
