"""Source byte integrity and request/source identity binding."""

import hashlib


def source_checksum(path: str) -> str:
    with open(path, "rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def validate_source_binding(path: str, expected_checksum: str, patient_id: str) -> None:
    from bremen.platform.sources.preflight import resolve_patient_metadata
    import h5py

    if source_checksum(path) != expected_checksum:
        raise ValueError("Input integrity mismatch")
    with h5py.File(path, "r") as source:
        patient = resolve_patient_metadata(source)
    if patient.patient_identifier != patient_id:
        raise ValueError("Input patient mismatch")
