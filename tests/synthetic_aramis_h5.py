from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np
from xrd_preprocessing import load_preprocessing_config


EXPECTED_PROFILE_LENGTH = 100
COMMON_OUTPUT_COLUMNS = {
    "age",
    "biopsy",
    "birads",
    "breast_density",
    "calibrant_thickness_mm",
    "id",
    "meas_name",
    "measurementDate",
    "measurement_data_source",
    "noise_std",
    "patientId",
    "patient_product_diagnosis",
    "patient_specimen_valid",
    "patient_specimen_validity_reason",
    "patient_valid_specimen_count",
    "poni_q_max_nm_inv",
    "position",
    "product_diagnosis",
    "product_status_group",
    "q_range",
    "q_range_normalization_area",
    "q_range_normalization_max",
    "q_range_normalization_min",
    "radial_profile_data",
    "radial_profile_nearest_q_nm_inv",
    "radial_profile_q_delta_nm_inv",
    "radial_profile_value_at_q",
    "radial_profile_value_pass",
    "sample_biopsy",
    "sample_biopsy_type",
    "sample_height_in",
    "sample_thickness_mm",
    "sample_weight_lb",
    "set_name",
    "side",
    "snr_db",
    "snr_linear",
    "snr_method_used",
    "snr_min_db",
    "snr_pass",
    "specimenId",
    "specimen_measurement_count",
    "specimen_status",
    "started_at",
    "thickness_correction_applied",
    "thickness_reference_column",
    "thickness_sample_column",
}
ONE_TO_ONE_OUTPUT_COLUMNS = COMMON_OUTPUT_COLUMNS | {
    "one_to_one_pair_type",
}
ONE_TO_MANY_OUTPUT_COLUMNS = COMMON_OUTPUT_COLUMNS
PAYLOAD_COLUMNS = {
    "measurement_data",
    "raw_data",
    "processed_data",
    "detector_measurements",
    "pyfai_faulty_pixel_mask",
    "radial_profile_data_raw",
    "radial_profile_sigma",
}


def load_synthetic_config(branch: str = "one_to_one") -> dict:
    config_file = {
        "one_to_one": "aramis_one_to_one_preprocessing_v0_1.yaml",
        "one_to_many": "aramis_one_to_many_preprocessing_v0_1.yaml",
    }[branch]
    config_path = Path(__file__).parents[1] / "config" / "preprocessing" / config_file
    config = load_preprocessing_config(config_path)
    config["raw_data"]["source"] = "npy"
    config["raw_data"]["h5_dataset_candidates"]["npy"] = ["raw/data"]
    config["filters"]["accepted_dates"] = ["2026-05-01"]
    config["snr"]["min_snr_db"] = 0.0
    config["profile_gate"]["min_value"] = 0.0
    return config


def write_known_synthetic_h5(path: Path) -> None:
    with h5py.File(path, "w") as h5:
        _write_measurement(
            h5,
            "p1_left",
            patient_id="P1",
            specimen_id="P1_LEFT",
            side="Left",
            status="BENIGN",
            seed=1,
        )
        _write_measurement(
            h5,
            "p1_right",
            patient_id="P1",
            specimen_id="P1_RIGHT",
            side="Right",
            status="CANCER",
            seed=2,
        )
        _write_measurement(
            h5,
            "p2_left_only",
            patient_id="P2",
            specimen_id="P2_LEFT",
            side="Left",
            status="BENIGN",
            seed=3,
        )
        _write_measurement(
            h5,
            "p3_left_normal",
            patient_id="P3",
            specimen_id="P3_LEFT",
            side="Left",
            status="NORMAL",
            seed=4,
        )
        _write_measurement(
            h5,
            "p3_right_atypical",
            patient_id="P3",
            specimen_id="P3_RIGHT",
            side="Right",
            status="ATYPICAL",
            seed=5,
        )
        _write_measurement(
            h5,
            "p4_left_missing_thickness",
            patient_id="P4",
            specimen_id="P4_LEFT",
            side="Left",
            status="BENIGN",
            seed=6,
            sample_thickness_mm=None,
        )
        _write_measurement(
            h5,
            "p4_right_orphan_after_thickness",
            patient_id="P4",
            specimen_id="P4_RIGHT",
            side="Right",
            status="CANCER",
            seed=7,
        )
        _write_measurement(
            h5,
            "p5_bad_calibrant",
            patient_id="P5",
            specimen_id="P5_LEFT",
            side="Left",
            status="CANCER",
            seed=8,
            calibrant_thickness_mm=50.0,
        )


def assert_common_output_contract(frame) -> None:
    assert PAYLOAD_COLUMNS.isdisjoint(set(frame.columns))
    assert bool(frame["thickness_correction_applied"].all())
    assert set(frame["thickness_sample_column"]) == {"sample_thickness_mm"}
    assert set(frame["thickness_reference_column"]) == {"calibrant_thickness_mm"}
    assert set(frame["calibrant_thickness_mm"]) == {10.0}
    assert frame["sample_thickness_mm"].notna().all()
    assert set(frame["measurement_data_source"]).issubset(
        {"npy:raw/data", "npy:processed/data"}
    )
    assert all(len(values) == EXPECTED_PROFILE_LENGTH for values in frame["q_range"])
    assert all(
        len(values) == EXPECTED_PROFILE_LENGTH for values in frame["radial_profile_data"]
    )


def _write_measurement(
    h5: h5py.File,
    name: str,
    *,
    patient_id: str,
    specimen_id: str,
    side: str,
    status: str,
    seed: int,
    sample_thickness_mm: float | None = 70.0,
    calibrant_thickness_mm: float = 10.0,
) -> None:
    group = h5.require_group(f"measurements/{name}")
    raw = group.require_group("raw")
    processed = group.require_group("processed")
    raw.create_dataset("data", data=_image(seed, offset=200.0))
    processed.create_dataset("data", data=_image(seed, offset=180.0))
    group.attrs.update(
        {
            "patientId": patient_id,
            "specimenId": specimen_id,
            "side": side,
            "position": "P1",
            "started_at": "2026-05-01 10:00:00",
            "specimen_status": status,
            "biopsy": status not in {"NORMAL", "BENIGN"},
            "sample_biopsy": status not in {"NORMAL", "BENIGN"},
            "sample_biopsy_type": "Post-biopsy" if status == "CANCER" else "Pre-biopsy",
            "age": 55.0 + seed,
            "sample_height_in": 64.0,
            "sample_weight_lb": 160.0,
            "breast_density": "C",
            "birads": "BI-RADS 4 Suspicious for Malignancy/High Risk",
            "calibrant_thickness_mm": calibrant_thickness_mm,
            "poni_q_max_nm_inv": 25.0,
        }
    )
    if sample_thickness_mm is not None:
        group.attrs["sample_thickness_mm"] = sample_thickness_mm


def _image(seed: int, *, offset: float) -> np.ndarray:
    rng = np.random.default_rng(seed)
    base = np.full((32, 32), offset + seed)
    return base + rng.normal(0.0, 2.0, size=base.shape)
