# PR0162 validation and metrics

| Metric | Before | After |
|---|---:|---:|
| Python source LOC | 37647 | 35477 |
| Python test LOC | 58729 | 56105 |
| Test files | 123 | 117 |
| Collected tests | 4411 | 4248 |
| Passed / skipped | 4398 / 13 | 4237 / 11 |
| pytest reported seconds | 52.84 | 34.76 |
| subprocess wall seconds | 53.580 | 35.528 |

The suites differ: provider/scaffold/unused bridge tests were retired after the baseline, while package golden/parity tests and public HTTP contracts remain. Timing is observational, not an identical-workload benchmark. Lazy root imports remove training/scientific startup cost from CLI-only tests. No claim of scientific runtime acceleration.

Compileall, full collect-only, full pytest --durations=100 and git diff --check pass. Focused architecture plus PR0160 package-owned preprocessing suite: 40 passed, 2 skipped. The two skips require private real-evidence input/artifact/interpreter configuration; no new real-evidence reproduction is claimed.

Full `ruff check .` was executed. HEAD baseline reconstructed from tracked Python files: 354 findings. Current findings: 163, including inherited warnings in legacy files and the moved symmetry module. New platform/contracts modules and PR0162 architecture tests pass ruff. Full-repository lint is not green; unrelated lint debt is retained explicitly.

Public route inventory matches all 29 baseline method/path pairs (27 paths). Successful normalized result snapshots match exactly. Existing legacy risk_score / technical_demo_only and additive standard_result tests pass, as do auth/token/refresh/tickets, SSE access policy, model requirements, source upload/listing, duplicate/replay, jobs, reports, safe failure and concurrent repository tests.

Before: app.openapi() failed on unresolved HTMLResponse annotation. Router extraction placed response types at module scope; app.openapi() now builds 27 paths. No public route was added or removed.

## After top 100 durations

```text
============================ slowest 100 durations =============================
10.76s call     tests/test_bremen_logging.py::TestS3StagingEvents::test_s3_staging_failure_events
1.16s call     tests/test_bremen_publish_model_package_cli.py::TestCliDryRun::test_cli_dry_run_with_synthetic_artifact
1.11s call     tests/test_bremen_auth.py::TestSafetyInvariants::test_expired_error_generic
1.11s call     tests/test_bremen_auth.py::TestAuthenticateRequest::test_expired_token_returns_none
1.10s call     tests/test_bremen_auth_credential_storage_contract.py::TestNoInternalLeakage::test_no_stack_traces_in_auth_errors
1.10s call     tests/test_bremen_auth.py::TestJWTToken::test_expired_token_rejected
1.10s call     tests/test_bremen_auth.py::TestStreamTicket::test_expired_ticket_rejected
1.03s call     tests/test_bremen_publish_model_package_cli.py::TestCliDryRun::test_cli_stages_package_with_no_dry_run
0.99s call     tests/test_bremen_publish_model_package_cli.py::TestCliDryRun::test_cli_does_not_write_files_by_default
0.93s call     tests/test_bremen_v01_package.py::test_importing_package_entry_does_not_load_workflow
0.39s call     tests/test_bremen_h5_layouts.py::TestRealLikeMatador::test_ambiguous_multiple_complete_pairs_retained
0.31s call     tests/test_aramina_v0213_package.py::test_package_entry_imports_no_workflow_modules
0.25s call     tests/test_bremen_concurrent_server.py::TestConcurrentJobStorage::test_concurrent_list_during_creation
0.21s call     tests/test_platform_architecture_pr0162.py::test_imports_do_not_load_scientific_dependencies
0.21s call     tests/test_bremen_event_stream.py::TestSSEPromptDelivery::test_heartbeat_only_when_no_events
0.12s call     tests/test_aramina_workflow_runtime.py::test_no_external_dependency_or_execution_configuration
0.12s call     tests/test_bremen_model_package_deduplication.py::test_single_authoritative_scientific_definitions
0.11s call     tests/test_bremen_pipeline_config.py::test_preprocess_cli_reads_input_and_output_from_yaml
0.09s call     tests/test_bremen_api_skeleton.py::TestImportSafety::test_no_pickle_import
0.09s call     tests/test_bremen_no_server_spawning_tests.py::TestNoServerSpawningInPytest::test_no_server_spawning_code[test_bremen_logging.py]
0.08s call     tests/test_bremen_mlflow_tracking.py::test_log_product_run_dry_run_writes_required_artifacts
0.08s call     tests/test_bremen_auth_activation_readiness.py::TestTokenAccessesProtectedRoute::test_token_grants_jobs_list_access
0.08s call     tests/test_bremen_modeling.py::test_one_to_many_product_comparison_returns_named_summaries
0.07s call     tests/test_bremen_fastapi_public_demo_surface_smoke.py::TestNoServerSpawning::test_no_http_server_imports
0.07s call     tests/test_bremen_modeling.py::test_fusion_feature_table_and_model_comparison_run_on_shared_splits
0.06s call     tests/test_bremen_fastapi_jobs_report_parity.py::TestJobReportsRoute::test_reports_for_unknown_job_has_empty_reports
0.06s call     tests/test_bremen_launch_flow.py::TestControlRoomLaunchFlow::test_launch_flow_no_dual_payload
0.06s call     tests/test_bremen_launch_flow.py::TestControlRoomLaunchFlow::test_launch_flow_catalog_selection
0.06s call     tests/test_bremen_launch_flow.py::TestControlRoomLaunchFlow::test_launch_flow_workflow_compat
0.06s call     tests/test_bremen_launch_flow.py::TestControlRoomLaunchFlow::test_launch_flow_executes
0.06s call     tests/test_bremen_launch_flow.py::TestControlRoomLaunchFlow::test_launch_flow_state_transitions
0.06s call     tests/test_bremen_launch_flow.py::TestControlRoomLaunchFlow::test_launch_flow_job_payload
0.06s call     tests/test_bremen_launch_flow.py::TestControlRoomLaunchFlow::test_launch_flow_no_model
0.06s call     tests/test_bremen_launch_flow.py::TestControlRoomLaunchFlow::test_launch_flow_stale_source
0.06s call     tests/test_bremen_launch_flow.py::TestControlRoomLaunchFlow::test_launch_flow_catalog_refresh
0.06s call     tests/test_bremen_demo_run.py::TestDemoRunCLI::test_demo_run_in_main_help
0.06s call     tests/test_bremen_launch_flow.py::TestControlRoomLaunchFlow::test_launch_flow_keyboard_selection
0.06s call     tests/test_bremen_launch_flow.py::TestControlRoomLaunchFlow::test_launch_flow_multi_model
0.06s call     tests/test_bremen_event_stream.py::TestSSEPromptDelivery::test_new_event_notified_quickly
0.05s call     tests/test_bremen_3x3_runtime_parity.py::test_h5_enumeration_does_not_change_scientific_output[3]
0.05s call     tests/test_bremen_auth_activation_readiness.py::TestMissingInvalidToken401::test_wrong_secret_token_401
0.05s call     tests/test_bremen_auth_activation_readiness.py::TestMissingInvalidToken401::test_401_no_secrets_in_response
0.05s call     tests/test_bremen_auth_activation_readiness.py::TestPublicPagesStillPublic::test_auth_refresh_endpoint_accessible
0.05s call     tests/test_bremen_auth_activation_readiness.py::TestTokenAccessesProtectedRoute::test_token_grants_workspace_access
0.05s call     tests/test_bremen_3x3_runtime_parity.py::test_h5_enumeration_does_not_change_scientific_output[0]
0.05s call     tests/test_bremen_auth_activation_readiness.py::TestTokenAccessesProtectedRoute::test_token_grants_external_report_access
0.05s call     tests/test_bremen_launch_flow.py::TestControlRoomLaunchFlow::test_js_parses_with_node
0.05s call     tests/test_bremen_auth_activation_readiness.py::TestPublicPagesStillPublic::test_auth_token_endpoint_accessible
0.05s call     tests/test_bremen_auth_activation_readiness.py::TestTokenAccessesProtectedRoute::test_token_grants_report_access
0.05s call     tests/test_bremen_auth_activation_readiness.py::TestTokenAccessesProtectedRoute::test_token_grants_workspace_job_access
0.05s call     tests/test_bremen_auth_activation_readiness.py::TestTokenAccessesProtectedRoute::test_token_grants_h5_containers_access
0.05s call     tests/test_bremen_modeling.py::test_repeated_one_to_many_product_logistic_returns_specimen_predictions
0.05s call     tests/test_bremen_model_v01_publication.py::TestV01Publish::test_v01_publish_dry_run_does_not_write_files
0.05s call     tests/test_bremen_auth_activation_readiness.py::TestTokenIssuance::test_authenticate_credentials_returns_token_pair
0.05s call     tests/test_aramina_v0213_package.py::test_direct_package_prediction_matches_provider_route
0.05s call     tests/test_bremen_auth_activation_readiness.py::TestTokenIssuance::test_wrong_password_returns_none
0.04s call     tests/test_bremen_cli_entrypoint.py::test_python_m_bremen_no_args_smoke
0.04s call     tests/test_bremen_js_parse.py::TestControlRoomJavaScriptParse::test_js_parses_with_node
0.04s call     tests/test_bremen_auth.py::TestAuthenticateCredentials::test_valid_credentials_returns_token_pair
0.04s call     tests/test_bremen_auth_activation_readiness.py::TestPublicPagesStillPublic::test_public_routes_no_auth_required
0.04s call     tests/test_bremen_demo_run.py::TestDemoRunCLI::test_demo_run_cli_skip_prediction
0.04s call     tests/test_bremen_demo_run.py::TestDemoRunCLI::test_demo_run_help_exits_0
0.04s call     tests/test_bremen_model_v01_publication.py::TestV01Publish::test_v01_model_filename_is_relative
0.04s call     tests/test_bremen_model_v01_publication.py::TestV01Publish::test_v01_requires_feature_schema_version
0.04s call     tests/test_bremen_model_v01_publication.py::TestV01Publish::test_v01_checksum_matches_staged_file
0.04s call     tests/test_bremen_model_v01_publication.py::TestV01Publish::test_v01_cli_help_works
0.04s call     tests/test_bremen_model_v01_publication.py::TestV01Publish::test_v01_manifest_has_correct_artifact_type
0.04s call     tests/test_bremen_auth_activation_readiness.py::TestFailClosedMissingConfig::test_missing_jwt_secret_fails_closed
0.04s call     tests/test_bremen_preprocessing_one_to_one.py::test_one_to_one_pipeline_dataframe_and_joblib_contract
0.03s call     tests/test_bremen_model_v01_publication.py::TestV01Publish::test_v01_validate_model_package_accepts_staged
0.03s call     tests/test_bremen_model_v01_publication.py::TestV01Publish::test_v01_missing_joblib_file_rejected
0.03s call     tests/test_bremen_model_v01_publication.py::TestV01Publish::test_v01_publish_stages_files
0.03s call     tests/test_bremen_cli_entrypoint.py::test_python_m_bremen_stub_smoke
0.03s call     tests/test_bremen_preprocessing_one_to_many.py::test_one_to_many_pipeline_dataframe_and_joblib_contract
0.03s call     tests/test_bremen_training_runtime_separation.py::TestCliSeparation::test_runtime_cli_does_not_show_training
0.03s call     tests/test_bremen_pipeline_config.py::test_preprocess_cli_can_write_minimal_output_columns
0.03s call     tests/test_bremen_publish_model_package_cli.py::TestCliHelp::test_cli_help_works
0.03s call     tests/test_bremen_demo_smoke.py::TestCliHelp::test_demo_smoke_help_exits_0
0.03s call     tests/test_bremen_training_runtime_separation.py::TestCliSeparation::test_training_cli_help_works
0.03s call     tests/test_bremen_fastapi_auth_enforcement.py::TestPublicRoutesAlwaysReachable::test_auth_routes_no_existing_token
0.03s call     tests/test_bremen_auth_activation_readiness.py::TestMissingInvalidToken401::test_401_no_traceback
0.03s call     tests/test_bremen_auth_activation_readiness.py::TestEnforcementScopePreserved::test_public_routes_no_token_needed
0.03s call     tests/test_bremen_preprocessing_one_to_many.py::test_one_to_many_biopsy_pipeline_keeps_only_biopsy_rows
0.03s call     tests/test_bremen_demo_smoke.py::TestCliHelp::test_demo_smoke_in_main_help
0.03s call     tests/test_bremen_publish_model_package_cli.py::TestCliMissingFlags::test_cli_missing_required_flags_errors
0.03s call     tests/test_aramina_workflow_runtime.py::TestFastAPIAraminaRoutePlumbing::test_model_id_post_uses_real_provider_without_scaffold[False]
0.03s call     tests/test_bremen_modeling.py::test_summary_helpers_handle_named_product_results
0.03s call     tests/test_bremen_auth_activation_readiness.py::TestEnforcementScopePreserved::test_protected_routes_require_token
0.03s call     tests/test_bremen_auth_activation_readiness.py::TestMissingInvalidToken401::test_missing_token_401
0.03s call     tests/test_bremen_auth_activation_readiness.py::TestMissingInvalidToken401::test_malformed_token_401
0.03s call     tests/test_bremen_auth_activation_readiness.py::TestMissingInvalidToken401::test_401_shape_is_safe
0.03s call     tests/test_bremen_auth_activation_readiness.py::TestPublicPagesStillPublic::test_auth_token_disabled_returns_503
0.03s call     tests/test_bremen_auth.py::TestPasswordVerification::test_valid_password_passes
0.03s call     tests/test_bremen_auth_activation_readiness.py::TestEnforcementScopePreserved::test_report_bootstrap_route_returns_shell
0.03s call     tests/test_bremen_auth_activation_readiness.py::TestEnforcementScopePreserved::test_browser_nav_routes_redirect_to_login
0.03s call     tests/test_bremen_auth.py::TestAuthenticateCredentials::test_wrong_password_returns_none
0.03s call     tests/test_bremen_auth_activation_readiness.py::TestFailClosedMissingConfig::test_short_jwt_secret_fails_closed
0.03s call     tests/test_bremen_model_loader.py::TestModelPackageUnchanged::test_model_package_not_modified
0.02s call     tests/test_bremen_auth_activation_readiness.py::TestFailClosedMissingConfig::test_missing_username_fails_closed
0.02s call     tests/test_bremen_auth_activation_readiness.py::TestFailClosedMissingConfig::test_jwt_secret_equals_hash_fails_closed
4237 passed, 11 skipped, 1678 warnings in 34.76s

```

## Largest remaining modules

```json
[
  [
    "src/bremen/api/server.py",
    1952
  ],
  [
    "src/bremen/report_ui.py",
    1541
  ],
  [
    "src/bremen/platform/sources/legacy_layouts.py",
    1506
  ],
  [
    "src/bremen/workspace_ui.py",
    1334
  ],
  [
    "src/bremen/modeling.py",
    1325
  ],
  [
    "src/bremen/control_room_ui.py",
    1281
  ],
  [
    "src/bremen/api/s3_model_discovery.py",
    1163
  ],
  [
    "src/bremen/training/pipeline.py",
    736
  ],
  [
    "src/bremen/api/model_requirements.py",
    687
  ],
  [
    "src/bremen/platform/api/legacy_jobs.py",
    599
  ],
  [
    "src/bremen/config.py",
    588
  ],
  [
    "src/bremen/demo_ui.py",
    587
  ],
  [
    "src/bremen/api/preflight.py",
    583
  ],
  [
    "src/bremen/model_packages/aramina_v0213/inference.py",
    544
  ],
  [
    "src/bremen/api_docs_ui.py",
    513
  ],
  [
    "src/bremen/pipelines.py",
    513
  ],
  [
    "src/bremen/model_packages/bremen_v01/symmetry_signals.py",
    487
  ],
  [
    "src/bremen/platform/jobs/service.py",
    479
  ],
  [
    "src/bremen/model_packages/bremen_v01/features.py",
    462
  ],
  [
    "src/bremen/demo_smoke.py",
    454
  ]
]
```

Final lint comparison (same rule configuration, matching code/message and accounting for the symmetry-module move) found **no new findings relative to HEAD**. Ruff over all changed/new Python files reports 46 inherited findings; full-repository ruff reports 163. The isolated new platform/contracts/PR0162-test scope passes.

Slowest final test: `TestS3StagingEvents::test_s3_staging_failure_events` at 10.76s (baseline 3.92s), showing that individual timings vary. The next reported test is a CLI publication dry-run at 1.16s. All top-100 entries above are retained without filtering.
