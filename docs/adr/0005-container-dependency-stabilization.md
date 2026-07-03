# ADR-0005: Container Dependency Stabilization

**Status**: Accepted

## Context (cited from evidence)

- `.github/workflows/quality.yml` installs `"git+https://github.com/Eos-Dx/container.git@feat/v0_3-eoscan-session-container"` — pinned to a feature branch, not main.
- `requirements.txt` contains a separate local-path defect: `-e /Users/sad/dev/container`.
- The current safety net is the `VERSION_REGISTRY "0_3"` assertion in the CI workflow (`from container.registry import VERSION_REGISTRY; assert "0_3" in VERSION_REGISTRY`).

## Decisions

### Event-triggered response

The container repo merging `feat/v0_3` to `main` is an EXTERNAL EVENT, not a schedulable date. Registered as event-triggered Decision Gate G-DEP-1 in ROADMAP.md, not a calendar date.

Required response once that event happens: re-pin within a fixed window (recommended default: 5 business days, marked revisable). Re-verify the `VERSION_REGISTRY` assertion against the new main — do not assume it still holds.

### requirements.txt fix

The `requirements.txt` local-path defect (`-e /Users/sad/dev/container`) is fixed in the same delegated PR as the re-pin work, since both are "container dependency hygiene."

## Decision Gate

| Gate ID | Question | Trigger type | Recommended default | Status |
|---------|----------|-------------|-------------------|--------|
| G-DEP-1 | Container repo merges feat/v0_3 to main | Event-bound (external event) | Re-pin within 5 business days; re-verify VERSION_REGISTRY | OPEN |
