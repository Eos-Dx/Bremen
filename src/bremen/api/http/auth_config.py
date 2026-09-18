"""HTTP authentication configuration shared by FastAPI adapters."""
from __future__ import annotations
import json
_auth_config = None
_AUTH_ERROR_SHAPE = json.dumps({"error":"Authentication failed","token_type":"Bearer","technical_demo_only":True})
_AUTH_DISABLED_SHAPE = json.dumps({"error":"Authentication is not configured"})
def _get_auth_config():
 global _auth_config
 if _auth_config is None:
  from bremen.config import read_auth_config
  _auth_config = read_auth_config()
 return _auth_config
def _reset_auth_config():
 global _auth_config
 _auth_config = None
