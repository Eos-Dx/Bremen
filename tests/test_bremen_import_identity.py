"""Focused import/package identity test for Bremen.

Verifies via filesystem inspection (no imports that trigger xrd_preprocessing):
- bremen package directory exists
- bremen __init__.py docstring mentions Bremen
- bremen.pipelines source contains Bremen* class names (not Aramis*)
- bremen.__main__ source contains prog="bremen"
- No Aramis class names remain in src/bremen/ source files
"""

from __future__ import annotations

from pathlib import Path


SRC_BREMEN = Path(__file__).parents[1] / "src" / "bremen"


def test_bremen_package_dir_exists():
    """src/bremen/ directory exists."""
    assert SRC_BREMEN.is_dir(), f"Expected {SRC_BREMEN} to exist"


def test_bremen_init_docstring_is_bremen():
    """__init__.py docstring references Bremen product draft."""
    path = SRC_BREMEN / "__init__.py"
    assert path.is_file()
    content = path.read_text(encoding="utf-8")
    assert "Bremen product draft" in content, (
        "__init__.py docstring must reference Bremen"
    )


def test_bremen_pipelines_has_bremen_class_names():
    """pipelines.py contains Bremen* class names (not Aramis*)."""
    path = SRC_BREMEN / "pipelines.py"
    assert path.is_file()
    content = path.read_text(encoding="utf-8")
    assert "class BremenPreprocessingPipeline" in content, (
        "pipelines.py must define BremenPreprocessingPipeline"
    )
    assert "class BremenOneToOnePreprocessingPipeline" in content, (
        "pipelines.py must define BremenOneToOnePreprocessingPipeline"
    )
    assert "class BremenOneToManyPreprocessingPipeline" in content, (
        "pipelines.py must define BremenOneToManyPreprocessingPipeline"
    )


def test_bremen_pipelines_no_aramis_class_names():
    """pipelines.py does not contain Aramis* class definitions."""
    path = SRC_BREMEN / "pipelines.py"
    assert path.is_file()
    content = path.read_text(encoding="utf-8")
    assert "class AramisPreprocessingPipeline" not in content, (
        "pipelines.py must not define AramisPreprocessingPipeline"
    )
    assert "class AramisOneToOnePreprocessingPipeline" not in content, (
        "pipelines.py must not define AramisOneToOnePreprocessingPipeline"
    )
    assert "class AramisOneToManyPreprocessingPipeline" not in content, (
        "pipelines.py must not define AramisOneToManyPreprocessingPipeline"
    )


def test_bremen_main_has_prog_bremen():
    """__main__.py argparse prog is 'bremen'."""
    path = SRC_BREMEN / "__main__.py"
    assert path.is_file()
    content = path.read_text(encoding="utf-8")
    assert 'prog="bremen"' in content, (
        "__main__.py must set prog='bremen'"
    )


def test_bremen_main_docstring_is_bremen():
    """__main__.py docstring references Bremen."""
    path = SRC_BREMEN / "__main__.py"
    assert path.is_file()
    content = path.read_text(encoding="utf-8")
    assert "Bremen product workflows" in content, (
        "__main__.py docstring must reference Bremen"
    )


def test_bremen_mlflow_env_var_is_bremen():
    """mlflow_tracking.py uses BREMEN_LOG_MLFLOW_MODEL (not ARAMIS)."""
    path = SRC_BREMEN / "mlflow_tracking.py"
    assert path.is_file()
    content = path.read_text(encoding="utf-8")
    assert "BREMEN_LOG_MLFLOW_MODEL" in content, (
        "mlflow_tracking.py must use BREMEN_LOG_MLFLOW_MODEL env var"
    )
    assert "ARAMIS_LOG_MLFLOW_MODEL" not in content, (
        "mlflow_tracking.py must not reference ARAMIS_LOG_MLFLOW_MODEL"
    )


def test_bremen_mlflow_experiment_is_bremen():
    """mlflow_tracking.py default experiment name is Bremen."""
    path = SRC_BREMEN / "mlflow_tracking.py"
    assert path.is_file()
    content = path.read_text(encoding="utf-8")
    assert 'DEFAULT_EXPERIMENT_NAME = "Bremen"' in content, (
        "mlflow_tracking.py must set DEFAULT_EXPERIMENT_NAME to Bremen"
    )


def test_bremen_modeling_docstring_is_bremen():
    """modeling.py docstring references Bremen."""
    path = SRC_BREMEN / "modeling.py"
    assert path.is_file()
    content = path.read_text(encoding="utf-8")
    assert "Bremen research-draft" in content, (
        "modeling.py docstring must reference Bremen"
    )


def test_no_aramis_class_names_in_src():
    """No source file under src/bremen/ defines an Aramis* class."""
    aramis_class_patterns = [
        "class AramisPreprocessingPipeline",
        "class AramisOneToOnePreprocessingPipeline",
        "class AramisOneToManyPreprocessingPipeline",
    ]
    for py_file in SRC_BREMEN.glob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        for pattern in aramis_class_patterns:
            assert pattern not in content, (
                f"{py_file.name} must not define {pattern}"
            )
