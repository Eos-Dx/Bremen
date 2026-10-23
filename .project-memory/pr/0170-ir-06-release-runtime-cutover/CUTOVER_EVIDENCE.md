# IR-06 cutover evidence

## Discovery

Release-backed entries bypass legacy artifact staging, checksum verification,
joblib deserialization, package adaptation, and model-specific imports. A
manifest-only catalog directory with a valid `runtime_release` is available
without a sibling `.joblib`. Legacy entries retain their existing validation
and artifact path.

## Registry and descriptors

`runtime_release` is now the routing authority. `BREMEN_CANDIDATE_SUBPROCESS_MODELS`
does not control release-backed routing. Descriptors supplied with a runtime do
not import or instantiate `BremenRuntime` or `AraminaRuntime`; release-backed
descriptors remain configured, ready, raw-input capable where applicable, and
use existing projection/telemetry/binding behavior.

## Parent/child boundary

Dynamic subprocess tests prove importing discovery and constructing supplied
release descriptors does not load Bremen scientific packages, Aramina scientific
packages, or the ML plugin. The existing Worker launch continues to use the
installed release executable, not `sys.executable`, request data, or PATH
resolution. Release installation and supervision remain in IR-04/IR-05 code.

## Failure semantics

Release installation, Worker, timeout, protocol, and scientific failures remain
release-route failures. There is no per-request legacy fallback. Legacy behavior
is selected only when the catalog entry has no `runtime_release`.

## Files and hashes

The current rebuilt plugin wheel SHA-256 is
`f4c4bf1ee52b7002b49598a1d40200517469b97e9f8f6809761949595d23d626`.
Release manifest and artifact hashes are recorded in
`FIVE_RELEASE_PARITY.md`.
