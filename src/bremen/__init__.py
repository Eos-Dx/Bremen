"""Bremen product draft package. Training dependencies load only when requested."""

from importlib import import_module

_EXPORTS = {
    "DEFAULT_EXPERIMENT_NAME": ("bremen.mlflow_tracking", "DEFAULT_EXPERIMENT_NAME"),
    "build_run_name": ("bremen.mlflow_tracking", "build_run_name"),
    "dataset_fingerprint": ("bremen.mlflow_tracking", "dataset_fingerprint"),
    "log_product_run": ("bremen.mlflow_tracking", "log_product_run"),
    "FusionModelComparisonResult": ("bremen.modeling", "FusionModelComparisonResult"),
    "OneToManyProductComparisonResult": (
        "bremen.modeling",
        "OneToManyProductComparisonResult",
    ),
    "OneToManyProductLogisticResult": (
        "bremen.modeling",
        "OneToManyProductLogisticResult",
    ),
    "RepeatedLogisticResult": ("bremen.modeling", "RepeatedLogisticResult"),
    "aggregate_measurement_scores_by_specimen": (
        "bremen.modeling",
        "aggregate_measurement_scores_by_specimen",
    ),
    "build_fusion_feature_table": ("bremen.modeling", "build_fusion_feature_table"),
    "compute_binary_thresholds": ("bremen.modeling", "compute_binary_thresholds"),
    "default_fusion_feature_sets": ("bremen.modeling", "default_fusion_feature_sets"),
    "fit_repeated_fusion_logistic_models": (
        "bremen.modeling",
        "fit_repeated_fusion_logistic_models",
    ),
    "fit_repeated_one_to_many_product_logistic_comparison": (
        "bremen.modeling",
        "fit_repeated_one_to_many_product_logistic_comparison",
    ),
    "fit_repeated_one_to_many_product_logistic": (
        "bremen.modeling",
        "fit_repeated_one_to_many_product_logistic",
    ),
    "fit_repeated_one_to_many_logistic": (
        "bremen.modeling",
        "fit_repeated_one_to_many_logistic",
    ),
    "fusion_ablation_feature_sets": ("bremen.modeling", "fusion_ablation_feature_sets"),
    "load_one_to_many_dataframe": ("bremen.modeling", "load_one_to_many_dataframe"),
    "profile_matrix": ("bremen.modeling", "profile_matrix"),
    "summarize_one_to_many_datasets": (
        "bremen.modeling",
        "summarize_one_to_many_datasets",
    ),
    "summarize_one_to_many_dataframe": (
        "bremen.modeling",
        "summarize_one_to_many_dataframe",
    ),
    "summarize_one_to_many_product_results": (
        "bremen.modeling",
        "summarize_one_to_many_product_results",
    ),
    "BremenOneToManyPreprocessingPipeline": (
        "bremen.pipelines",
        "BremenOneToManyPreprocessingPipeline",
    ),
    "BremenOneToOnePreprocessingPipeline": (
        "bremen.pipelines",
        "BremenOneToOnePreprocessingPipeline",
    ),
    "BremenPreprocessingPipeline": ("bremen.pipelines", "BremenPreprocessingPipeline"),
    "run_preprocessing_from_config": (
        "bremen.pipelines",
        "run_preprocessing_from_config",
    ),
    "run_one_to_many_preprocessing_pipeline": (
        "bremen.pipelines",
        "run_one_to_many_preprocessing_pipeline",
    ),
    "run_one_to_one_preprocessing_pipeline": (
        "bremen.pipelines",
        "run_one_to_one_preprocessing_pipeline",
    ),
}
__all__ = list(_EXPORTS)


def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(name)
    module, attribute = _EXPORTS[name]
    value = getattr(import_module(module), attribute)
    globals()[name] = value
    return value
