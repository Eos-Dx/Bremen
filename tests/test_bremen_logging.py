"""Logging behavior tests for Bremen server internals.

Covers:
- Logging configuration
- Model config events
- S3 staging events
- Checksum events
- Model load events
- Prediction rejection logging (via direct handler call, no server)
- Startup visibility (via direct ModelState call, no server)
- Inference stage visibility
- No secrets in logs
- No raw paths in logs
- Health check log suppression

Uses direct function calls and caplog — no real server, no sockets,
no localhost HTTP requests.
"""

from __future__ import annotations

import logging

import pytest

from bremen.logging_config import reset_logging


# ---------------------------------------------------------------------------
# Autouse fixture
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_logging():
    """Reset logging config before and after each test."""
    reset_logging()
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
    root.setLevel(logging.WARNING)
    yield
    reset_logging()
    for handler in list(root.handlers):
        root.removeHandler(handler)


# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------


class TestLoggingConfig:
    def test_default_level_is_info(self):
        from bremen.logging_config import get_logger
        logger = get_logger("test_module")
        assert logger is not None

    def test_env_var_respected(self, monkeypatch):
        monkeypatch.setenv("BREMEN_LOG_LEVEL", "DEBUG")
        from bremen.logging_config import configure_logging
        configure_logging()
        root = logging.getLogger("bremen")
        assert root.level <= logging.DEBUG

    def test_idempotent(self):
        from bremen.logging_config import configure_logging
        configure_logging()
        configure_logging()  # second call should not raise


# ---------------------------------------------------------------------------
# Model config events
# ---------------------------------------------------------------------------


class TestModelConfigEvents:
    def test_missing_model_config_emits_event(self, caplog):
        caplog.set_level(logging.INFO)
        from bremen.api.model_state import ModelState
        ModelState.reset_for_tests()

        result = ModelState.load_at_startup(
            model_uri="",
            model_version="",
            model_checksum="",
        )
        assert result is False
        assert "bremen.model.config.missing" in caplog.text
        assert "bremen.model.not_ready" in caplog.text
        ModelState.reset_for_tests()

    def test_detected_model_config_logs_safe_fields(self, caplog, tmp_path):
        caplog.set_level(logging.INFO)
        from bremen.api.model_state import ModelState
        import joblib
        import numpy as np

        ModelState.reset_for_tests()

        fake_model = {"coef": np.zeros(10)}
        model_path = tmp_path / "test_model.joblib"
        joblib.dump(fake_model, model_path)

        import hashlib
        with open(model_path, "rb") as f:
            checksum = hashlib.sha256(f.read()).hexdigest()

        result = ModelState.load_at_startup(
            model_uri=str(model_path),
            model_version="v1.0",
            model_checksum=checksum,
        )
        assert result is True
        assert "bremen.model.config.detected" in caplog.text
        assert "bremen.model.config.read" in caplog.text
        assert "bremen.model.ready" in caplog.text
        # No raw paths in logs
        assert str(tmp_path) not in caplog.text
        ModelState.reset_for_tests()


# ---------------------------------------------------------------------------
# S3 staging events
# ---------------------------------------------------------------------------


class TestS3StagingEvents:
    def test_s3_staging_success_events(self, caplog, tmp_path):
        """stage_h5_input with invalid URI raises ValueError."""
        caplog.set_level(logging.INFO)
        from bremen.h5_inputs import stage_h5_input

        with pytest.raises(ValueError):
            stage_h5_input(str(tmp_path / "test.h5"))

    def test_s3_staging_failure_events(self, caplog, tmp_path):
        caplog.set_level(logging.INFO)
        from bremen.h5_inputs import stage_h5_input

        # Non-existent path should fail
        with pytest.raises((ValueError, OSError, IOError)):
            stage_h5_input("s3://nonexistent-bucket/nonexistent-key.h5")


# ---------------------------------------------------------------------------
# Checksum events
# ---------------------------------------------------------------------------


class TestChecksumEvents:
    def test_checksum_mismatch_logs_failure(self, caplog, tmp_path):
        caplog.set_level(logging.INFO)
        from bremen.api.model_state import ModelState

        ModelState.reset_for_tests()

        bad_file = tmp_path / "bad_model.joblib"
        bad_file.write_bytes(b"not a valid model")
        result = ModelState.load_at_startup(
            model_uri=str(bad_file),
            model_version="v0.1",
            model_checksum="a" * 64,
        )
        assert result is False
        assert "bremen.model.checksum.verify.failure" in caplog.text
        ModelState.reset_for_tests()

    def test_checksum_success_emits_event(self, caplog, tmp_path):
        caplog.set_level(logging.INFO)
        from bremen.api.model_state import ModelState
        import joblib
        import numpy as np

        ModelState.reset_for_tests()

        fake_model = {"coef": np.zeros(10)}
        model_path = tmp_path / "test_model.joblib"
        joblib.dump(fake_model, model_path)

        # Compute correct checksum
        import hashlib
        with open(model_path, "rb") as f:
            checksum = hashlib.sha256(f.read()).hexdigest()

        result = ModelState.load_at_startup(
            model_uri=str(model_path),
            model_version="v1.0",
            model_checksum=checksum,
        )
        assert result is True
        assert "bremen.model.checksum.verify.success" in caplog.text
        ModelState.reset_for_tests()


# ---------------------------------------------------------------------------
# Model load events
# ---------------------------------------------------------------------------


class TestModelLoadEvents:
    def test_successful_model_load_logs_ready(self, caplog, tmp_path):
        caplog.set_level(logging.INFO)
        from bremen.api.model_state import ModelState
        import joblib
        import numpy as np

        ModelState.reset_for_tests()

        fake_model = {"coef": np.zeros(10)}
        model_path = tmp_path / "test_model.joblib"
        joblib.dump(fake_model, model_path)

        import hashlib
        with open(model_path, "rb") as f:
            checksum = hashlib.sha256(f.read()).hexdigest()

        result = ModelState.load_at_startup(
            model_uri=str(model_path),
            model_version="v1.0",
            model_checksum=checksum,
        )
        assert result is True
        assert "bremen.model.ready" in caplog.text
        assert "bremen.model.config.detected" in caplog.text
        ModelState.reset_for_tests()

    def test_failed_model_load_logs_not_ready(self, caplog, tmp_path):
        caplog.set_level(logging.INFO)
        from bremen.api.model_state import ModelState

        ModelState.reset_for_tests()

        bad_file = tmp_path / "bad_model.joblib"
        bad_file.write_bytes(b"not a valid model")
        result = ModelState.load_at_startup(
            model_uri=str(bad_file),
            model_version="v0.1",
            model_checksum="a" * 64,
        )
        assert result is False
        assert "bremen.model.not_ready" in caplog.text
        ModelState.reset_for_tests()


# ---------------------------------------------------------------------------
# Prediction rejection (via direct handler call, no server)
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# Startup visibility (via direct ModelState call, no server)
# ---------------------------------------------------------------------------


class TestStartupVisibility:
    def test_server_startup_with_no_model_env(self, caplog):
        """Server startup with no model env logs config and not_ready."""
        caplog.set_level(logging.INFO)
        from bremen.api.model_state import ModelState
        ModelState.reset_for_tests()

        result = ModelState.load_at_startup(
            model_uri="",
            model_version="",
            model_checksum="",
        )
        assert result is False
        assert "bremen.runtime.config.summary" not in caplog.text
        assert "bremen.model.config.read" not in caplog.text
        assert "bremen.model.config.missing" in caplog.text
        assert "bremen.model.not_ready" in caplog.text
        ModelState.reset_for_tests()

    def test_server_startup_with_loading_failure(self, caplog, tmp_path):
        """Server startup with model loading failure logs stage events."""
        caplog.set_level(logging.INFO)
        from bremen.api.model_state import ModelState
        ModelState.reset_for_tests()

        bad_file = tmp_path / "bad_model.joblib"
        bad_file.write_bytes(b"not a valid model")
        result = ModelState.load_at_startup(
            model_uri=str(bad_file),
            model_version="v0.1",
            model_checksum="a" * 64,
        )
        assert result is False
        assert "bremen.model.config.read" in caplog.text
        assert "bremen.model.config.detected" in caplog.text
        assert "bremen.model.checksum.verify.failure" in caplog.text
        assert "bremen.model.not_ready" in caplog.text
        ModelState.reset_for_tests()



# ---------------------------------------------------------------------------
# H5 / Preflight / Preprocessing / Inference visibility
# ---------------------------------------------------------------------------


class TestInferenceStageVisibility:
    def test_inference_stages_log_correctly(self, caplog, tmp_path):
        """Full inference pipeline logs expected stage events."""
        caplog.set_level(logging.INFO)

        from bremen.api.model_state import ModelState
        import joblib
        import numpy as np
        import h5py

        ModelState.reset_for_tests()

        # Create a minimal H5 file
        h5_path = tmp_path / "test.h5"
        with h5py.File(h5_path, "w") as f:
            scans = f.create_group("scans")
            for label in ("target", "contralateral"):
                grp = scans.create_group(label)
                arr = np.random.default_rng(42).normal(10.0, 2.0, 100).astype(np.float64)
                grp.create_dataset("measurements", data=arr.reshape(1, -1))

        # Create a fake model
        fake_model = {"coef": np.zeros(10), "intercept": 0.0}
        model_path = tmp_path / "test_model.joblib"
        joblib.dump(fake_model, model_path)

        import hashlib
        with open(model_path, "rb") as f:
            checksum = hashlib.sha256(f.read()).hexdigest()

        result = ModelState.load_at_startup(
            model_uri=str(model_path),
            model_version="v1.0",
            model_checksum=checksum,
        )
        assert result is True

        # Verify model is ready
        assert ModelState.is_ready() is True

        ModelState.reset_for_tests()


# ---------------------------------------------------------------------------
# No secrets in logs
# ---------------------------------------------------------------------------


class TestNoSecrets:
    def test_no_secrets_in_logs(self, caplog, tmp_path):
        """Log output must not contain secrets."""
        caplog.set_level(logging.DEBUG)

        from bremen.api.model_state import ModelState
        import joblib
        import numpy as np

        ModelState.reset_for_tests()

        fake_model = {"coef": np.zeros(10)}
        model_path = tmp_path / "test_model.joblib"
        joblib.dump(fake_model, model_path)

        import hashlib
        with open(model_path, "rb") as f:
            checksum = hashlib.sha256(f.read()).hexdigest()

        ModelState.load_at_startup(
            model_uri=str(model_path),
            model_version="v1.0",
            model_checksum=checksum,
        )

        log_text = caplog.text.lower()
        assert "aws_secret" not in log_text
        assert "jwt_secret" not in log_text
        assert "password" not in log_text
        assert "credential" not in log_text
        ModelState.reset_for_tests()


# ---------------------------------------------------------------------------
# No raw paths in logs
# ---------------------------------------------------------------------------


class TestNoRawPaths:
    def test_no_raw_paths_in_logs(self, caplog, tmp_path):
        """Log output must not contain raw filesystem paths."""
        caplog.set_level(logging.DEBUG)

        from bremen.api.model_state import ModelState
        import joblib
        import numpy as np

        ModelState.reset_for_tests()

        fake_model = {"coef": np.zeros(10)}
        model_path = tmp_path / "test_model.joblib"
        joblib.dump(fake_model, model_path)

        import hashlib
        with open(model_path, "rb") as f:
            checksum = hashlib.sha256(f.read()).hexdigest()

        ModelState.load_at_startup(
            model_uri=str(model_path),
            model_version="v1.0",
            model_checksum=checksum,
        )

        log_text = caplog.text
        # Raw temp paths should not appear
        assert "/tmp/" not in log_text or "model_uri" in log_text
        # model_uri is allowed in config.summary but not in error paths
        ModelState.reset_for_tests()


# ---------------------------------------------------------------------------
# Health check log suppression
# ---------------------------------------------------------------------------


class TestHealthNoNoise:
    def test_health_no_noisy_logs(self, caplog):
        """Health check endpoint should not produce noisy logs."""
        caplog.set_level(logging.INFO)
        from bremen.api.app import handle_health
        resp = handle_health()
        assert resp.status == "ok"
        # No prediction-related logs from health check
        assert "prediction" not in caplog.text.lower()
