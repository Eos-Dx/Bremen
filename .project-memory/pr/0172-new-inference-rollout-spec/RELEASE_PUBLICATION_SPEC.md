# Release publication spec (local only — no AWS existence checks performed)

For each of the five IR-07 releases, this is the complete local source evidence a human operator needs to publish the release. **Existence of any of these objects in the real S3 catalog is `UNKNOWN — OPERATOR MUST VERIFY`** — this agent did not query S3.

## Target object layout (derived from `release_build/assemble.py`, not guessed)

Every release directory, once assembled locally (`bremen.release_build.assemble`), has this exact structure, and `_file_ref` generates `s3_key = f"releases/{release_id}/{relative_path}"` for every declared file:

```
releases/<release_id>/manifest.json                          (written directly; relative convention, see TARGET_CATALOG_POINTERS.md)
releases/<release_id>/plugin/<plugin wheel>.whl               (role: plugin_wheel)
releases/<release_id>/feature_library/<feature wheel>.whl     (role: feature_library_wheel — IR-07 addition)
releases/<release_id>/model/<artifact filename>                (role: model_artifact)
releases/<release_id>/configs/runtime.json                     (role: config)
releases/<release_id>/configs/artifact_manifest.json           (role: config)
releases/<release_id>/requirements/main.lock                   (role: requirements_lock)
releases/<release_id>/requirements/aux-<tag>.lock               (role: requirements_lock_aux, if applicable)
releases/<release_id>/provenance/build.json                     (role: provenance)
releases/<release_id>/provenance/xrd-preprocessing-<tag>.json    (role: provenance, if applicable)
releases/<release_id>/wheelhouse/main/<dep wheel>.whl            (role: dependency_wheel, one per main dependency)
releases/<release_id>/wheelhouse/aux/<tag>/<dep wheel>.whl       (role: dependency_wheel_aux, if applicable)
releases/<release_id>/golden_tests/cases.json                    (role: golden_cases)
releases/<release_id>/golden_tests/fixtures/<fixture>.h5         (role: golden_fixture)
```

Relative to the deployed catalog's own bucket/prefix (unknown — see `TARGET_CATALOG_POINTERS.md`).

## Per-release publication record

| Release | Local evidence source | manifest_sha256 | plugin wheel sha256 | feature wheel sha256 | feature contract |
|---|---|---|---|---|---|
| A1 | `/tmp/ir07/releases/a1` (this session's local rebuild) | `94a0033b64fd8e664cbd515607cf5d03f3820b9f9ebc0125edcecd5bf2984498` | `67ed55226d7c8088f013a11aa9723f8bc0b3b346053e2f0000403563b196efae` | `75498c315990dbe26e591c13c9cb64f06eb9b4139f57608bba4b8576db84a72d` | `aramina_sk_symmetry_v0_2` |
| A2 | `/tmp/ir07/releases/a2` | `2126e2c325003b014a80db7d927d31285ff71b03afa172dd0dd7c3b9ee8025df` | (same) | (same) | `aramina_sk_symmetry_v0_2` |
| B1 | `/tmp/ir07/releases/b1` | `b9169e1766c3ffb56561c5668af0c2f264a363ec6493f893e35e48c8b2b59088` | (same) | (same) | `bremen_feature_schema_v0.1` |
| B2 | `/tmp/ir07/releases/b2` | `c384a27f21d98d78025360ed77c4db5eb72f1cf9b007a549b52591c7a56a69a2` | (same) | (same) | `bremen_feature_schema_v0.1` |
| B3 | `/tmp/ir07/releases/b3` | `940c41427b2d7b4bba6d39c4e1905dd5d661ce8273a261205e3db8a65fb1d9a3` | (same) | (same) | `bremen_feature_schema_v0.1` |

Declared file counts and golden-case counts are in each release's own `manifest.json`/`release.json` (not reproduced in full here to avoid duplicating `.project-memory/pr/0171-ir-07-xrd-feature-library/WHEEL_EVIDENCE.md`).

**Important:** `/tmp/ir07/releases/*` is this machine's local, ephemeral build output from the IR-07 session (verified via real `ReleaseCache.install()` runs — see `FIVE_RELEASE_PARITY.md` in the IR-07 evidence directory). It is not itself a durable artifact store; before any real publication, an operator must either reproduce these releases (the exact local build-input evidence — artifact dirs, wheelhouses, aux environments — is documented in `.project-memory/pr/0171-ir-07-xrd-feature-library/PLAN.md` and `WHEEL_EVIDENCE.md`) or retain the already-built directories through to upload time.

## Existence at target keys

`UNKNOWN — OPERATOR MUST VERIFY.` This agent did not list or read any S3 object. Before publication, the operator should check whether the target keys already hold objects and, if so, whether their SHA-256 matches these values exactly (`SAME`) or differs (`CONFLICT` — a blocker, since release objects are immutable by design). This classification cannot be performed without AWS access and is explicitly deferred.
