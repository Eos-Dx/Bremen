# Bremen Roadmap

**Track**: Product Track only.

No Platform Readiness Track. No Decision Gate Register. No hard calendar dates — use sequence and dependencies.

## Completed foundation PRs

- PR-0001 — Agent workflow foundation
- PR-0002 — Planning/identity cleanup
- PR-0003 — Full Aramis-to-Bremen alignment
- PR-0004 — Roadmap quality/docker/entrypoint planning
- PR-0005 — Docker/CI/Sonar skeleton
- PR-0006 — Coverage/cache
- PR-0007 — GHCR Docker smoke publish
- PR-0008 — Unified Bremen entrypoint
- PR-0009 — Config discovery/loading

## Product Track sequence

Product core before infrastructure wrappers.

1. **Product identity / document separation baseline** — This cascade (0011A/B). ADR-0001 and ADR-0002, architecture baseline, and updated roadmap.
2. **YAML/PDF clinical report template** — Public + internal, per Bremen Assembly plan v1 Phase 1 (currently overdue).
3. **YAML training config template** — Per Bremen Assembly plan v1 Phase 1 (currently overdue).
4. **Bremen feature-family implementation/verification** — For all seven families: `sigma_l1`, `sigma_l2`, `Mahalanobis1`, `Mahalanobis2`, `wasserstein_distance_full_q2`, `meanrms2`, `weightedrms1`.
5. **`train_classifier.py` pipeline + QC criteria document + `bremen_v1.joblib` reproducible model package** — The first controlled model release.
6. **GitHub demo** — Real H5 patients, end-to-end prediction shown.
7. **platform deployment plan document** — Documented deployment architecture.
8. **Safety preflight gates** — H5 metadata validation, target/control consistency, config integrity.
9. **Matador boundary / system-of-record adapter skeleton** — Platform integration contract.
10. **Workflow wrapper / decision-support output** — First end-to-end workflow (preprocess → QC → inference → report).
11. **Model artifact/version reporting** — Artifact management.
12. **Release readiness / operator notes** — Final preparation.

Items 8–12 must not be silently dropped, but must appear after items 1–7 because there is no model, API surface, or workflow yet for them to gate.
