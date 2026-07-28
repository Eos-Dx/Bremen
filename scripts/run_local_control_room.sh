#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT_DIR"

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"

PRIVATE_ARTIFACTS_DIR="${PRIVATE_ARTIFACTS_DIR:-$ROOT_DIR/../bremen-private-artifacts}"
MANIFEST_PATH="${MANIFEST_PATH:-$PRIVATE_ARTIFACTS_DIR/manifest_v02.json}"

H5_DIR="${H5_DIR:-$PRIVATE_ARTIFACTS_DIR/h5}"
MODELS_DIR="${MODELS_DIR:-$PRIVATE_ARTIFACTS_DIR/models}"
LABELS_DIR="${LABELS_DIR:-$PRIVATE_ARTIFACTS_DIR/labels}"
COMBINED_DIR="${COMBINED_DIR:-$PRIVATE_ARTIFACTS_DIR/combined}"

echo "== Bremen local Control Room =="
echo "root:              $ROOT_DIR"
echo "branch:            $(git branch --show-current 2>/dev/null || echo unknown)"
echo "head:              $(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
echo "private artifacts: $PRIVATE_ARTIFACTS_DIR"
echo "manifest:          $MANIFEST_PATH"
echo

if [[ ! -d "$PRIVATE_ARTIFACTS_DIR" ]]; then
  echo "ERROR: private artifacts directory not found: $PRIVATE_ARTIFACTS_DIR"
  exit 1
fi

for path in "$H5_DIR" "$MODELS_DIR" "$LABELS_DIR" "$COMBINED_DIR"; do
  if [[ ! -e "$path" ]]; then
    echo "WARN: expected artifact path missing: $path"
  fi
done

if [[ ! -f "$MANIFEST_PATH" ]]; then
  echo "ERROR: manifest not found: $MANIFEST_PATH"
  echo "Available manifests:"
  ls -lah "$PRIVATE_ARTIFACTS_DIR"/manifest*.json 2>/dev/null || true
  exit 1
fi

if [[ -d "$ROOT_DIR/venv" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT_DIR/venv/bin/activate"
elif [[ -d "$ROOT_DIR/.venv" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.venv/bin/activate"
else
  echo "WARN: no venv/.venv found; using current Python: $(command -v python)"
fi

export PYTHONPATH="$ROOT_DIR/src:${PYTHONPATH:-}"

# Demo/local-safe defaults.
export BREMEN_DEMO_MODE="${BREMEN_DEMO_MODE:-1}"
export BREMEN_TECHNICAL_DEMO_ONLY="${BREMEN_TECHNICAL_DEMO_ONLY:-1}"
export BREMEN_MODEL_STAGING_DIR="${BREMEN_MODEL_STAGING_DIR:-/tmp/bremen-models}"

# Private artifact paths for local testing.
export BREMEN_PRIVATE_ARTIFACTS_DIR="$PRIVATE_ARTIFACTS_DIR"
export BREMEN_LOCAL_ARTIFACTS_DIR="$PRIVATE_ARTIFACTS_DIR"
export BREMEN_LOCAL_DEMO_DATA_DIR="$PRIVATE_ARTIFACTS_DIR"
export BREMEN_LOCAL_H5_DIR="$H5_DIR"
export BREMEN_H5_DIR="$H5_DIR"
export BREMEN_LABELS_DIR="$LABELS_DIR"
export BREMEN_COMBINED_DIR="$COMBINED_DIR"
export BREMEN_MODELS_DIR="$MODELS_DIR"

# Model catalog aliases. The app may use one of these depending on branch.
export BREMEN_MODEL_CATALOG_PATH="$MANIFEST_PATH"
export BREMEN_MODEL_CATALOG_URI="${BREMEN_MODEL_CATALOG_URI:-file://$MANIFEST_PATH}"

export_MODEL_CATALOG_URI="${BREMEN_MODEL_CATALOG_URI:-file://$MANIFEST_PATH}"

export HOST
export PORT
export BREMEN_HOST="$HOST"
export BREMEN_PORT="$PORT"

echo "python: $(command -v python)"
python --version
echo
echo "env:"
echo "  BREMEN_DEMO_MODE=$BREMEN_DEMO_MODE"
echo "  BREMEN_TECHNICAL_DEMO_ONLY=$BREMEN_TECHNICAL_DEMO_ONLY"
echo "  BREMEN_MODEL_STAGING_DIR=$BREMEN_MODEL_STAGING_DIR"
echo "  BREMEN_MODEL_CATALOG_PATH=$BREMEN_MODEL_CATALOG_PATH"
echo "  BREMEN_MODEL_CATALOG_URI=$BREMEN_MODEL_CATALOG_URI"
echo "  BREMEN_LOCAL_H5_DIR=$BREMEN_LOCAL_H5_DIR"
echo

echo "Artifact quick view:"
find "$PRIVATE_ARTIFACTS_DIR" -maxdepth 2 -type f | sed "s#^$PRIVATE_ARTIFACTS_DIR/#  #g" | head -80
echo

echo "Quick compile check..."
python -m compileall src tests >/tmp/bremen_compileall.log || {
  echo "compileall failed; see /tmp/bremen_compileall.log"
  cat /tmp/bremen_compileall.log
  exit 1
}

echo
echo "Starting server..."
echo "Open: http://$HOST:$PORT/demo/control-room"
echo

python -m bremen.api.server
