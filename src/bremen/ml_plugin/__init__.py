"""Standalone ML plugin for the five IR-03 model releases.

This package is the ML-owned side of the IR-02 release boundary.  It contains
the scientific runtime required to execute one of the five verified model
variants from a staged ``input.h5`` and a ``bremen.worker.v1`` request
envelope, without the Bremen application:

- artifact loading (checksum-verified, through the narrow package bridge),
- H5 canonical input normalization for the supported legacy layouts,
- artifact-owned preprocessing (invoked in the release's pinned auxiliary
  environment),
- scientific QC, feature construction, inference and postprocessing (owned by
  ``bremen.model_packages``), and
- JSON codecs / typed result envelopes (owned by ``bremen.contracts``).

Import boundary: nothing here may import ``bremen.platform``, ``bremen.api``,
FastAPI, S3/boto3, the catalog/discovery layer or application job
orchestration.  ``tests/test_ir03_plugin_import_boundary.py`` enforces this.

The plugin wheel is built by ``bremen.release_build`` and contains only the
neutral contracts, the scientific model packages and this plugin module — not
the full Bremen application distribution.
"""

__all__ = ["PLUGIN_DISTRIBUTION", "PLUGIN_VERSION"]

PLUGIN_DISTRIBUTION = "bremen-ml-plugin"
PLUGIN_VERSION = "0.1.0"
