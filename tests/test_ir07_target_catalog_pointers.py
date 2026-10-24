"""IR-07 rollout-spec (PR 0172): validate the five generated target
``runtime_release`` fragments under
``.project-memory/pr/0172-new-inference-rollout-spec/target-catalog/`` against
the current merged contracts — no AWS, no network.

These fragments are local specification artifacts for a future human/operator
catalog pointer update; this test only proves they are well-formed and
internally consistent with the IR-07 release evidence, not that they match
any live deployed catalog (which this repository has no access to inspect
from this test).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from bremen.contracts.inference_release import SCHEMA_ID
from bremen.platform.models.release_cache import ReleaseCache, ReleaseReference

TARGET_CATALOG_DIR = (
    Path(__file__).resolve().parents[1]
    / ".project-memory" / "pr" / "0172-new-inference-rollout-spec" / "target-catalog"
)

#: Expected (model_id, manifest_sha256) per variant, frozen from
#: .project-memory/pr/0171-ir-07-xrd-feature-library/WHEEL_EVIDENCE.md — a
#: change here must be a deliberate, reviewed update to that evidence, not an
#: accidental edit of the generated fragment.
EXPECTED = {
    "a1": (
        "aramina_target_breast_risk_0_2_12-beta_9bb911189af6",
        "aramina-target-breast-risk-0-2-12-beta-9bb9111",
        "94a0033b64fd8e664cbd515607cf5d03f3820b9f9ebc0125edcecd5bf2984498",
    ),
    "a2": (
        "aramina_target_breast_risk_0_2_13-beta_f5e4a04cad11",
        "aramina-target-breast-risk-0-2-13-beta-f5e4a04",
        "2126e2c325003b014a80db7d927d31285ff71b03afa172dd0dd7c3b9ee8025df",
    ),
    "b1": (
        "bremen-mri-triage-logreg-v0-1",
        "bremen-mri-triage-logreg-v0-1",
        "b9169e1766c3ffb56561c5668af0c2f264a363ec6493f893e35e48c8b2b59088",
    ),
    "b2": (
        "bremen-paper-reference-v0-2-0",
        "bremen-paper-reference-v0-2-0",
        "c384a27f21d98d78025360ed77c4db5eb72f1cf9b007a549b52591c7a56a69a2",
    ),
    "b3": (
        "bremen-v0-2-0-symmetry-candidate",
        "bremen-v0-2-0-symmetry-candidate",
        "940c41427b2d7b4bba6d39c4e1905dd5d661ce8273a261205e3db8a65fb1d9a3",
    ),
}


class _FakeEntry:
    def __init__(self, model_id: str, runtime_release: dict) -> None:
        self.model_id = model_id
        self._runtime_release = runtime_release

    def get_runtime_release(self):
        return self._runtime_release


def _load(key: str) -> dict:
    return json.loads((TARGET_CATALOG_DIR / f"{key}-runtime-release.json").read_text())


@pytest.mark.parametrize("key", sorted(EXPECTED))
def test_fragment_exists_and_is_well_formed(key: str) -> None:
    fragment = _load(key)
    assert set(fragment) == {"schema_version", "release_id", "manifest_key", "manifest_sha256"}
    assert fragment["schema_version"] == SCHEMA_ID


@pytest.mark.parametrize("key", sorted(EXPECTED))
def test_fragment_matches_frozen_ir07_evidence(key: str) -> None:
    fragment = _load(key)
    _model_id, release_id, manifest_sha256 = EXPECTED[key]
    assert fragment["release_id"] == release_id
    assert fragment["manifest_sha256"] == manifest_sha256


@pytest.mark.parametrize("key", sorted(EXPECTED))
def test_fragment_resolves_through_release_cache(key: str) -> None:
    """The generated fragment must pass ReleaseCache.resolve()'s fail-closed
    validation (schema, identity, path-safety, SHA-256 shape) under an
    assumed empty catalog prefix. The deployed catalog's real prefix is
    unknown (no AWS access) -- see TARGET_CATALOG_POINTERS.md; this proves
    the fragment's *shape* is valid, not that the deployed prefix matches."""
    fragment = _load(key)
    model_id, _release_id, _manifest_sha256 = EXPECTED[key]
    cache = ReleaseCache(
        root="/tmp/does-not-matter-for-resolve",
        catalog_uri="s3://test-bucket/",
    )
    reference = cache.resolve(_FakeEntry(model_id, fragment))
    assert isinstance(reference, ReleaseReference)
    assert reference.model_id == model_id
    assert reference.release_id == fragment["release_id"]
    assert reference.manifest_sha256 == fragment["manifest_sha256"]


def test_all_five_release_ids_are_distinct() -> None:
    release_ids = [_load(key)["release_id"] for key in EXPECTED]
    assert len(release_ids) == len(set(release_ids)) == 5


def test_all_five_manifest_shas_are_distinct() -> None:
    """Five releases, five distinct release bundles -- a repeated manifest
    SHA across different release_ids would mean two "different" releases
    share byte-identical manifests, which is a rollout identity blocker."""
    manifest_shas = [_load(key)["manifest_sha256"] for key in EXPECTED]
    assert len(manifest_shas) == len(set(manifest_shas)) == 5
