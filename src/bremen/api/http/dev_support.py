"""Small development support helpers used by in-process smoke tests."""
from __future__ import annotations

_patient_name_cache = {}
def _load_synthetic_model() -> None:
 import hashlib, tempfile
 from pathlib import Path
 from joblib import dump
 from bremen.platform.models.state import ModelState
 from bremen.model_packages.bremen_v01.features import FEATURE_COLS
 tmp_path=Path(tempfile.mkdtemp())
 package={"portable_logreg":{"feature_columns":list(FEATURE_COLS),"imputer_statistics":[0.0]*15,"scaler_mean":[0.0]*15,"scaler_scale":[1.0]*15,"coef":[0.1]*15,"intercept":0.0,"threshold":0.5}}
 model_path=tmp_path/'synth_model.joblib'; dump(package,model_path)
 checksum=hashlib.sha256(model_path.read_bytes()).hexdigest()
 ModelState.load_at_startup(model_uri=str(model_path),model_version='smoke-v0.1',model_checksum=checksum)
