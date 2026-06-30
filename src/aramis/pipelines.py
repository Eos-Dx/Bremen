"""Aramis preprocessing pipeline entrypoints."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from xrd_preprocessing import (
    AzimuthalIntegration,
    ColumnValueFilter,
    FaultyPixelDetector,
    H5SessionFilter,
    PatientSpecimenValidityFilter,
    QRangeNormalizer,
    QRangeValueNormalizer,
    RadialProfileValueFilter,
    SNRFilter,
    SNRTransformer,
    calibrant_thickness_h5_filters,
    load_preprocessing_config,
)
from xrd_preprocessing.transformers import (
    ConstantQRangeTransformer,
    DropColumnsTransformer,
    H5BlobDataFrameTransformer,
    H5ToDataFrameTransformer,
    JoblibWriterTransformer,
    PairedGroupFilter,
    ProductColumnBuilder,
    ProductStatusGroupFilter,
    SelectColumnsTransformer,
)


PAYLOAD_COLUMNS = (
    "measurement_data",
    "gfrm_data",
    "raw_data",
    "processed_data",
    "detector_measurements",
    "faulty_pixel_mask",
    "radial_profile_data_raw",
    "radial_profile_sigma",
)
LEGACY_DEBUG_PAYLOAD_COLUMNS = (
    "invalid_pixel_mask",
    "pyfai_faulty_pixel_mask",
    "suspected_hot_pixel_mask",
    "faulty_pixel_reason_map",
    "faulty_pixel_reason_counts",
)


class AramisPreprocessingPipeline(TransformerMixin, BaseEstimator):
    """Aramis product route composed only from xrd_preprocessing transformers."""

    def __init__(
        self,
        *,
        config: dict[str, Any] | str | Path,
        branch: str,
        output_joblib_path: str | Path | None = None,
    ) -> None:
        self.config = config
        self.branch = branch
        self.output_joblib_path = output_joblib_path

    def fit(self, X: str | Path, y: Any = None):
        _ = X
        _ = y
        return self

    def transform(self, X: str | Path) -> pd.DataFrame:
        config = _load_config(self.config)
        data: Any = X
        self.steps_ = build_aramis_preprocessing_steps(
            config=config,
            branch=self.branch,
            output_joblib_path=self.output_joblib_path,
        )
        for step in self.steps_:
            data = step.fit_transform(data)
        return data


class AramisOneToOnePreprocessingPipeline(AramisPreprocessingPipeline):
    """One-to-one paired-breast preprocessing route."""

    def __init__(
        self,
        *,
        config: dict[str, Any] | str | Path,
        output_joblib_path: str | Path | None = None,
    ) -> None:
        super().__init__(
            config=config,
            branch="one_to_one",
            output_joblib_path=output_joblib_path,
        )


class AramisOneToManyPreprocessingPipeline(AramisPreprocessingPipeline):
    """One-to-many specimen-level preprocessing route."""

    def __init__(
        self,
        *,
        config: dict[str, Any] | str | Path,
        output_joblib_path: str | Path | None = None,
    ) -> None:
        super().__init__(
            config=config,
            branch="one_to_many",
            output_joblib_path=output_joblib_path,
        )


def build_aramis_preprocessing_steps(
    *,
    config: dict[str, Any],
    branch: str,
    output_joblib_path: str | Path | None = None,
) -> list[TransformerMixin]:
    """Build the ordered product route from xrd_preprocessing transformers."""
    _validate_branch(branch)
    branch_config = _branch_config(config, branch)

    return [
        _reader_step(config=config, branch=branch),
        ProductColumnBuilder(),
        *_common_filter_steps(config),
        *_label_steps(branch=branch, branch_config=branch_config),
        _faulty_pixel_step(),
        _constant_q_range_step(config["integration"]),
        _azimuthal_integration_step(config["integration"]),
        *_snr_and_validity_steps(config=config, branch_config=branch_config),
        *_normalization_and_gate_steps(config),
        *_payload_drop_steps(config),
        *_output_column_steps(config),
        JoblibWriterTransformer(output_joblib_path),
    ]


def payload_columns_to_drop(config: dict[str, Any]) -> tuple[str, ...]:
    """Return payload columns that should be dropped before writing joblib."""
    metadata = config.get("metadata", {})
    if not bool(metadata.get("drop_payload_columns", True)):
        return ()
    keep = {str(column) for column in metadata.get("keep_payload_columns", [])}
    keep.update(str(column) for column in metadata.get("output_columns", []))
    drop = [
        column
        for column in (*PAYLOAD_COLUMNS, *LEGACY_DEBUG_PAYLOAD_COLUMNS)
        if column not in keep
    ]
    return tuple(drop)


def _payload_drop_steps(config: dict[str, Any]) -> list[TransformerMixin]:
    columns = payload_columns_to_drop(config)
    if len(columns) == 0:
        return []
    return [DropColumnsTransformer(columns)]


def _output_column_steps(config: dict[str, Any]) -> list[TransformerMixin]:
    columns = tuple(
        str(column)
        for column in config.get("metadata", {}).get("output_columns", [])
    )
    if len(columns) == 0:
        return []
    return [SelectColumnsTransformer(columns)]


def _label_steps(
    *,
    branch: str,
    branch_config: dict[str, Any],
) -> list[TransformerMixin]:
    steps: list[TransformerMixin] = [
        ColumnValueFilter(
            "specimen_status",
            op="in",
            values=branch_config["specimen_status_keep"],
        )
    ]
    if branch == "one_to_one":
        return [
            *steps,
            ProductStatusGroupFilter(["BENIGN", "CANCER", "NORMAL"]),
            PairedGroupFilter(allowed_pairs=branch_config["patient_pair_keep"]),
        ]
    return [*steps, ProductStatusGroupFilter(["BENIGN", "CANCER"])]


def _faulty_pixel_step() -> TransformerMixin:
    return FaultyPixelDetector(
        local_hot_min_value=500.0,
        exclude_beam_center_radius=0.04,
    )


def _constant_q_range_step(integration: dict[str, Any]) -> TransformerMixin:
    q_min, q_max = integration["q_range_nm_inv"]
    return ConstantQRangeTransformer(q_min=q_min, q_max=q_max)


def _azimuthal_integration_step(integration: dict[str, Any]) -> TransformerMixin:
    thickness = integration["thickness_correction"]
    return AzimuthalIntegration(
        npt=integration["npt"],
        calibration_mode="poni",
        mask_column="faulty_pixel_mask",
        error_model=integration["error_model"],
        thickness_adjustment=thickness["enabled"],
        require_thickness_adjustment=thickness["enabled"],
        sample_thickness_column=thickness["sample_thickness_column"],
        thickness_reference_column=thickness["calibrant_thickness_column"],
    )


def _snr_and_validity_steps(
    *,
    config: dict[str, Any],
    branch_config: dict[str, Any],
) -> list[TransformerMixin]:
    return [
        SNRTransformer(snr_method=config["snr"]["method"]),
        SNRFilter(min_snr_db=config["snr"]["min_snr_db"]),
        PatientSpecimenValidityFilter(
            min_measurements_per_specimen=branch_config[
                "min_measurements_per_specimen_after_snr"
            ],
            min_specimens_per_patient=branch_config.get(
                "min_specimens_per_patient_after_snr",
                1,
            ),
        ),
    ]


def _normalization_and_gate_steps(config: dict[str, Any]) -> list[TransformerMixin]:
    normalization = config["normalization"]
    norm_q_min, norm_q_max = normalization["q_range_nm_inv"]
    gate = config["profile_gate"]
    normalizer = _normalizer_step(normalization, norm_q_min, norm_q_max)
    return [
        normalizer,
        RadialProfileValueFilter(
            q_value_nm_inv=gate["q_nm_inv"],
            threshold=gate["min_value"],
            op=">",
        )
    ]


def _normalizer_step(
    normalization: dict[str, Any],
    norm_q_min: float,
    norm_q_max: float,
) -> TransformerMixin:
    mode = str(normalization.get("mode", "area")).lower()
    save_initial_data = normalization.get("save_initial_data", False)
    if mode == "value":
        return QRangeValueNormalizer(
            q_min=norm_q_min,
            q_max=norm_q_max,
            statistic=normalization.get("statistic", "median"),
            save_initial_data=save_initial_data,
        )
    if mode == "area":
        return QRangeNormalizer(
            q_min=norm_q_min,
            q_max=norm_q_max,
            save_initial_data=save_initial_data,
        )
    raise ValueError(f"Unknown normalization mode: {mode!r}")


def run_one_to_one_preprocessing_pipeline(
    h5_path: str | Path,
    config: dict[str, Any] | str | Path,
    *,
    output_joblib_path: str | Path | None = None,
) -> pd.DataFrame:
    """Build the one-to-one paired-breast preprocessing DataFrame."""
    return AramisOneToOnePreprocessingPipeline(
        config=config,
        output_joblib_path=output_joblib_path,
    ).fit_transform(h5_path)


def run_one_to_many_preprocessing_pipeline(
    h5_path: str | Path,
    config: dict[str, Any] | str | Path,
    *,
    output_joblib_path: str | Path | None = None,
) -> pd.DataFrame:
    """Build the one-to-many specimen-level preprocessing DataFrame."""
    return AramisOneToManyPreprocessingPipeline(
        config=config,
        output_joblib_path=output_joblib_path,
    ).fit_transform(h5_path)


def run_preprocessing_from_config(config_path: str | Path) -> pd.DataFrame:
    """Run Aramis preprocessing using only paths and branch stored in YAML."""
    config_path = Path(config_path)
    config = load_preprocessing_config(config_path)
    branch = config["aramis_preprocessing"]["branch"]
    h5_path = _config_path(config, config_path, "input_h5_path")
    output_joblib_path = _config_path(config, config_path, "output_joblib_path")
    if branch == "one_to_one":
        return run_one_to_one_preprocessing_pipeline(
            h5_path,
            config,
            output_joblib_path=output_joblib_path,
        )
    if branch == "one_to_many":
        return run_one_to_many_preprocessing_pipeline(
            h5_path,
            config,
            output_joblib_path=output_joblib_path,
        )
    raise ValueError(f"Unknown Aramis preprocessing branch: {branch}")


def _config_path(config: dict[str, Any], config_path: Path, key: str) -> Path:
    value = config.get("io", {}).get(key)
    if value in {None, ""}:
        raise ValueError(f"Missing io.{key} in preprocessing config: {config_path}")
    path = Path(str(value)).expanduser()
    if path.is_absolute():
        return path
    return (config_path.parent / path).resolve()


def _common_filter_steps(config: dict[str, Any]) -> list[TransformerMixin]:
    filters = config["filters"]
    thickness = filters.get("thickness", {})
    sample = thickness.get("sample", {})
    calibrant = thickness.get("calibrant", {})
    steps: list[TransformerMixin] = []
    # Legacy compatibility: new product configs should use
    # filters.quality_exclusions at H5 level instead of accepted date allowlists.
    if filters.get("accepted_dates"):
        steps.append(
            ColumnValueFilter(
                "started_at",
                op="date in",
                values=filters["accepted_dates"],
            )
        )
    steps.append(
        ColumnValueFilter(
            "poni_q_max_nm_inv",
            op=">=",
            value=filters["required_q_max_nm_inv"],
        )
    )
    if filters.get("measurement_positions"):
        steps.append(
            ColumnValueFilter(
                "position",
                op="in",
                values=filters["measurement_positions"],
            )
        )
    if sample.get("require", filters.get("require_sample_thickness_mm", False)):
        steps.append(
            ColumnValueFilter(
                sample.get("column", "sample_thickness_mm"),
                op=">",
                value=sample.get("min_mm", 0.0),
            )
        )
    if calibrant.get("require", filters.get("require_calibrant_thickness_mm", False)):
        steps.append(
            ColumnValueFilter(
                calibrant.get("column", "calibrant_thickness_mm"),
                op="between",
                lower=calibrant.get("min_mm", 10.0),
                upper=calibrant.get("max_mm", 40.0),
            )
        )
    if filters.get("require_biopsy"):
        steps.append(
            ColumnValueFilter(
                filters.get("biopsy_column", "biopsy"),
                op="==",
                value=True,
            )
        )
    return steps


def _reader_step(config: dict[str, Any], branch: str) -> TransformerMixin:
    raw_config = config["raw_data"]
    source = str(raw_config["source"]).lower()
    if source in {"gfrm", "raw", "container_raw", "fabio"}:
        h5_filters = _h5_filters(config=config, branch=branch)
        measurement_filters = _measurement_filters(config)
        return H5ToDataFrameTransformer(
            data_preference=source,
            drop_missing_sample_thickness=config["filters"].get(
                "require_sample_thickness_mm",
                False,
            ),
            h5_filters=h5_filters,
            measurement_filters=measurement_filters,
            session_category="SAMPLE",
            set_category="SAMPLE",
        )
    candidates = raw_config.get("h5_dataset_candidates", {}).get(source)
    return H5BlobDataFrameTransformer(
        source=source,
        dataset_candidates=tuple(candidates or ()),
    )


def _h5_filters(config: dict[str, Any], branch: str) -> list[H5SessionFilter]:
    filters = config["filters"]
    out: list[H5SessionFilter] = _quality_exclusion_h5_filters(filters)
    # Legacy compatibility: new product configs should use quality_exclusions.
    if filters.get("accepted_dates"):
        out.append(
            H5SessionFilter(
                column="started_at",
                op="date in",
                values=filters["accepted_dates"],
            )
        )
    if filters.get("require_biopsy"):
        out.append(
            H5SessionFilter(
                column=filters.get("biopsy_column", "biopsy"),
                op="==",
                value=True,
            )
        )
    out.append(
        H5SessionFilter(
            column="specimen_status",
            op="in",
            values=_branch_config(config, branch)["specimen_status_keep"],
        )
    )
    out.extend(
        calibrant_thickness_h5_filters(
            min_mm=filters["calibrant_thickness_range_mm"][0],
            max_mm=filters["calibrant_thickness_range_mm"][1],
        )
    )
    return out


def _quality_exclusion_h5_filters(filters: dict[str, Any]) -> list[H5SessionFilter]:
    exclusions = filters.get("quality_exclusions", {})
    if not exclusions.get("enabled", False):
        return []
    primary = exclusions.get("primary_key", {})
    fallback = exclusions.get("fallback_date", {})
    excluded_values = primary.get("excluded_values") or []
    excluded_dates = fallback.get("excluded_dates") or []
    fallback_filter = None
    if excluded_dates and fallback.get("use_when_primary_key_missing", True):
        fallback_filter = {
            "column": fallback.get("column", "started_at"),
            "op": "date not in",
            "values": excluded_dates,
        }
    if excluded_values:
        return [
            H5SessionFilter(
                column=primary.get("column", "linked_agbh_session_uid"),
                op="not in",
                values=excluded_values,
                fallback=fallback_filter,
            )
        ]
    if excluded_dates:
        return [
            H5SessionFilter(
                column=fallback.get("column", "started_at"),
                op="date not in",
                values=excluded_dates,
            )
        ]
    return []


def _measurement_filters(config: dict[str, Any]) -> list[H5SessionFilter]:
    filters = config["filters"]
    out: list[H5SessionFilter] = []
    positions = filters.get("measurement_positions")
    if positions:
        out.append(
            H5SessionFilter(
                column="position",
                op="in",
                values=positions,
            )
        )
    return out


def _load_config(config: dict[str, Any] | str | Path) -> dict[str, Any]:
    if isinstance(config, str | Path):
        return load_preprocessing_config(config)
    return config


def _branch_config(config: dict[str, Any], branch: str) -> dict[str, Any]:
    if config.get("aramis_preprocessing", {}).get("branch") == branch:
        return config["branch_settings"]
    return config[branch]


def _validate_branch(branch: str) -> None:
    if branch not in {"one_to_one", "one_to_many"}:
        raise ValueError(f"Unknown Aramis preprocessing branch: {branch}")
