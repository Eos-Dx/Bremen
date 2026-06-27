"""Aramis preprocessing pipeline entrypoints."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from xrd_preprocessing import (
    ColumnValueFilter,
    DropColumnsTransformer,
    H5BlobDataFrameTransformer,
    H5SessionFilter,
    H5ToDataFrameTransformer,
    JoblibWriterTransformer,
    PairedGroupFilter,
    PatientSpecimenValidityFilter,
    ProductColumnBuilder,
    ProductStatusGroupFilter,
    QRangeNormalizer,
    RadialProfileValueFilter,
    SNRFilter,
    SNRTransformer,
    SimpleRadialProfileTransformer,
    calibrant_thickness_h5_filters,
    load_preprocessing_config,
)


PAYLOAD_COLUMNS = (
    "measurement_data",
    "gfrm_data",
    "raw_data",
    "processed_data",
    "detector_measurements",
    "pyfai_faulty_pixel_mask",
    "radial_profile_data_raw",
    "radial_profile_sigma",
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
    integration = config["integration"]
    q_min, q_max = integration["q_range_nm_inv"]
    norm_q_min, norm_q_max = config["normalization"]["q_range_nm_inv"]
    gate = config["profile_gate"]
    branch_config = _branch_config(config, branch)

    steps: list[TransformerMixin] = [
        _reader_step(config=config, branch=branch),
        ProductColumnBuilder(),
        *_common_filter_steps(config),
        ColumnValueFilter(
            "specimen_status",
            op="in",
            values=branch_config["specimen_status_keep"],
        ),
    ]

    if branch == "one_to_one":
        steps.extend(
            [
                ProductStatusGroupFilter(["BENIGN", "CANCER", "NORMAL"]),
                PairedGroupFilter(
                    allowed_pairs=branch_config["patient_pair_keep"],
                ),
            ]
        )
    else:
        steps.append(ProductStatusGroupFilter(["BENIGN", "CANCER"]))

    steps.extend(
        [
            SimpleRadialProfileTransformer(
                npt=integration["npt"],
                q_min=q_min,
                q_max=q_max,
                thickness_adjustment_applied=integration["thickness_correction"][
                    "enabled"
                ],
                sample_thickness_column=integration["thickness_correction"][
                    "sample_thickness_column"
                ],
                thickness_reference_column=integration["thickness_correction"][
                    "calibrant_thickness_column"
                ],
            ),
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
            QRangeNormalizer(
                q_min=norm_q_min,
                q_max=norm_q_max,
                save_initial_data=config["normalization"].get(
                    "save_initial_data",
                    False,
                ),
            ),
            RadialProfileValueFilter(
                q_value_nm_inv=gate["q_nm_inv"],
                threshold=gate["min_value"],
                op=">",
            ),
            DropColumnsTransformer(PAYLOAD_COLUMNS),
            JoblibWriterTransformer(output_joblib_path),
        ]
    )
    return steps


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


def _common_filter_steps(config: dict[str, Any]) -> list[TransformerMixin]:
    filters = config["filters"]
    thickness = filters.get("thickness", {})
    sample = thickness.get("sample", {})
    calibrant = thickness.get("calibrant", {})
    steps: list[TransformerMixin] = []
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
    out: list[H5SessionFilter] = []
    if filters.get("accepted_dates"):
        out.append(
            H5SessionFilter(
                column="started_at",
                op="date in",
                values=filters["accepted_dates"],
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
