# Baseline (before production edits)

Commit: `dc6e99d8fa0a7f1a5cf641e6da6533f759a11d18`. Source LOC: 37647; test LOC: 58729; test files: 123.

Compileall, collect-only and git diff --check passed. Full pytest: **4398 passed, 13 skipped**, 1676 warnings; pytest time 52.84s; subprocess wall time **53.580s**. 4411 collected tests.

Known baseline defect: app.openapi() raises PydanticUserError for unresolved HTMLResponse ForwardRef. No pytest failures. No OpenAPI snapshot fabricated.

Public snapshots: public_routes.json (complete live route inventory); public_results.json (existing mapper projections with fixed identity/time). Existing endpoint characterization is in tests/test_bremen_fastapi*, test_bremen_standard*, test_bremen_auth*, test_bremen_job*, test_bremen_event_stream.py and test_aramina_workflow_runtime.py.

## Routes

- GET `/demo`
- GET `/demo/api-docs`
- POST `/demo/api/auth/refresh`
- POST `/demo/api/auth/token`
- GET `/demo/api/h5/containers`
- POST `/demo/api/h5/containers`
- GET `/demo/api/jobs`
- POST `/demo/api/jobs`
- GET `/demo/api/jobs/{job_id}`
- POST `/demo/api/jobs/{job_id}/auth/ticket`
- GET `/demo/api/jobs/{job_id}/events`
- GET `/demo/api/jobs/{job_id}/events/stream`
- GET `/demo/api/jobs/{job_id}/reports`
- GET `/demo/api/jobs/{job_id}/reports/{workflow_id}`
- GET `/demo/api/models`
- GET `/demo/api/models/{model_id}/requirements`
- POST `/demo/api/models/{model_id}/requirements/validate`
- GET `/demo/api/reports/{job_id}/external`
- GET `/demo/api/reports/{job_id}/internal`
- GET `/demo/control-room`
- GET `/demo/login`
- GET `/demo/model-guide`
- GET `/demo/model-playground`
- GET `/demo/model-playground/sandpit-0104t-preview`
- GET `/demo/report/{job_id}`
- GET `/demo/workspace`
- GET `/demo/workspace/{job_id}`
- GET `/health`
- GET `/model/version`

## Import/size hotspots

```json
{
  "commit": "dc6e99d8fa0a7f1a5cf641e6da6533f759a11d18",
  "source_loc": 37647,
  "test_loc": 58729,
  "test_files": 123,
  "largest_source_modules": [
    [
      "src/bremen/api/server.py",
      1955
    ],
    [
      "src/bremen/api/job_api_handler.py",
      1683
    ],
    [
      "src/bremen/api/fastapi_app.py",
      1603
    ],
    [
      "src/bremen/report_ui.py",
      1541
    ],
    [
      "src/bremen/api/h5_layouts.py",
      1428
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
      1165
    ],
    [
      "src/bremen/api/preprocessing_bridge.py",
      944
    ],
    [
      "src/bremen/training/pipeline.py",
      736
    ],
    [
      "src/bremen/api/model_requirements.py",
      678
    ],
    [
      "src/bremen/api/workflow_bremen.py",
      676
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
      "src/bremen/api/workflow_orchestrator.py",
      565
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
    ]
  ],
  "dependency_hotspots": [
    [
      "__future__",
      106
    ],
    [
      "typing",
      72
    ],
    [
      "dataclasses",
      34
    ],
    [
      "pathlib",
      27
    ],
    [
      "json",
      26
    ],
    [
      "logging",
      25
    ],
    [
      "os",
      22
    ],
    [
      "datetime",
      20
    ],
    [
      "uuid",
      14
    ],
    [
      "hashlib",
      14
    ],
    [
      "numpy",
      14
    ],
    [
      "pandas",
      13
    ],
    [
      "re",
      12
    ],
    [
      "joblib",
      9
    ],
    [
      "sys",
      9
    ],
    [
      "model_registry",
      9
    ],
    [
      "time",
      8
    ],
    [
      "h5py",
      8
    ],
    [
      "yaml",
      7
    ],
    [
      "threading",
      6
    ],
    [
      "argparse",
      6
    ],
    [
      "workflow_provider",
      6
    ],
    [
      "workflow_orchestrator",
      6
    ],
    [
      "decision_contract",
      6
    ],
    [
      "math",
      5
    ],
    [
      "tempfile",
      5
    ],
    [
      "xrd_preprocessing",
      5
    ],
    [
      "bremen.model_packages.aramina_v0213.errors",
      5
    ],
    [
      "model_state",
      5
    ],
    [
      "bremen.model_packages.aramina_v0213",
      5
    ]
  ],
  "openapi_baseline_failure": "PydanticUserError: unresolved HTMLResponse ForwardRef (existing baseline)"
}
```

## Top 100 durations

```text
============================ slowest 100 durations =============================
3.92s call     tests/test_bremen_logging.py::TestS3StagingEvents::test_s3_staging_failure_events
1.26s call     tests/test_bremen_v01_package.py::test_importing_package_entry_does_not_load_workflow
1.22s call     tests/test_bremen_training_runtime_separation.py::TestCliSeparation::test_runtime_cli_does_not_show_training
1.21s call     tests/test_bremen_training_runtime_separation.py::TestCliSeparation::test_training_cli_help_works
1.19s call     tests/test_bremen_model_v01_publication.py::TestV01Publish::test_v01_publish_dry_run_does_not_write_files
1.18s call     tests/test_bremen_model_v01_publication.py::TestV01Publish::test_v01_manifest_has_correct_artifact_type
1.18s call     tests/test_bremen_publish_model_package_cli.py::TestCliDryRun::test_cli_dry_run_with_synthetic_artifact
1.18s call     tests/test_aramina_v0213_package.py::test_package_entry_imports_no_workflow_modules
1.18s call     tests/test_bremen_model_v01_publication.py::TestV01Publish::test_v01_missing_joblib_file_rejected
1.17s call     tests/test_bremen_demo_run.py::TestDemoRunCLI::test_demo_run_help_exits_0
1.17s call     tests/test_bremen_cli_entrypoint.py::test_python_m_bremen_no_args_smoke
1.17s call     tests/test_bremen_model_v01_publication.py::TestV01Publish::test_v01_validate_model_package_accepts_staged
1.17s call     tests/test_bremen_publish_model_package_cli.py::TestCliDryRun::test_cli_stages_package_with_no_dry_run
1.17s call     tests/test_bremen_model_v01_publication.py::TestV01Publish::test_v01_checksum_matches_staged_file
1.16s call     tests/test_bremen_demo_smoke.py::TestCliHelp::test_demo_smoke_in_main_help
1.16s call     tests/test_bremen_model_v01_publication.py::TestV01Publish::test_v01_cli_help_works
1.16s call     tests/test_bremen_publish_model_package_cli.py::TestCliHelp::test_cli_help_works
1.16s call     tests/test_bremen_model_v01_publication.py::TestV01Publish::test_v01_publish_stages_files
1.16s call     tests/test_bremen_publish_model_package_cli.py::TestCliMissingFlags::test_cli_missing_required_flags_errors
1.15s call     tests/test_bremen_model_v01_publication.py::TestV01Publish::test_v01_model_filename_is_relative
1.15s call     tests/test_bremen_demo_run.py::TestDemoRunCLI::test_demo_run_cli_skip_prediction
1.15s call     tests/test_bremen_demo_run.py::TestDemoRunCLI::test_demo_run_in_main_help
1.15s call     tests/test_bremen_publish_model_package_cli.py::TestCliDryRun::test_cli_does_not_write_files_by_default
1.15s call     tests/test_bremen_model_v01_publication.py::TestV01Publish::test_v01_requires_feature_schema_version
1.15s call     tests/test_bremen_demo_smoke.py::TestCliHelp::test_demo_smoke_help_exits_0
1.14s call     tests/test_bremen_cli_entrypoint.py::test_python_m_bremen_stub_smoke
1.11s call     tests/test_bremen_auth.py::TestStreamTicket::test_expired_ticket_rejected
1.11s call     tests/test_bremen_auth.py::TestSafetyInvariants::test_expired_error_generic
1.11s call     tests/test_bremen_auth.py::TestJWTToken::test_expired_token_rejected
1.11s call     tests/test_bremen_auth_credential_storage_contract.py::TestNoInternalLeakage::test_no_stack_traces_in_auth_errors
1.10s call     tests/test_bremen_auth.py::TestAuthenticateRequest::test_expired_token_returns_none
0.81s call     tests/test_bremen_h5_layouts.py::TestRealLikeMatador::test_ambiguous_multiple_complete_pairs_retained
0.24s call     tests/test_bremen_concurrent_server.py::TestConcurrentJobStorage::test_concurrent_list_during_creation
0.20s call     tests/test_bremen_event_stream.py::TestSSEPromptDelivery::test_heartbeat_only_when_no_events
0.14s call     tests/test_aramina_workflow_runtime.py::test_no_external_dependency_or_execution_configuration
0.12s call     tests/test_bremen_mlflow_tracking.py::test_log_product_run_dry_run_writes_required_artifacts
0.11s call     tests/test_bremen_pipeline_config.py::test_preprocess_cli_reads_input_and_output_from_yaml
0.11s call     tests/test_bremen_model_package_deduplication.py::test_single_authoritative_scientific_definitions
0.09s call     tests/test_bremen_no_server_spawning_tests.py::TestNoServerSpawningInPytest::test_no_server_spawning_code[test_bremen_event_stream.py]
0.08s call     tests/test_bremen_modeling.py::test_one_to_many_product_comparison_returns_named_summaries
0.07s setup    tests/test_bremen_fastapi_phase2_catalog.py::TestPhase1RoutesStillWork::test_model_version_still_works
0.07s call     tests/test_bremen_launch_flow.py::TestControlRoomLaunchFlow::test_launch_flow_executes
0.07s call     tests/test_bremen_launch_flow.py::TestControlRoomLaunchFlow::test_launch_flow_state_transitions
0.07s call     tests/test_bremen_fastapi_auth_enforcement.py::TestTicketMintingEndpoint::test_mint_endpoint_auth_disabled_allows_through
0.07s call     tests/test_bremen_modeling.py::test_fusion_feature_table_and_model_comparison_run_on_shared_splits
0.07s call     tests/test_bremen_launch_flow.py::TestControlRoomLaunchFlow::test_launch_flow_multi_model
0.06s call     tests/test_bremen_launch_flow.py::TestControlRoomLaunchFlow::test_launch_flow_no_dual_payload
0.06s call     tests/test_bremen_auth_activation_readiness.py::TestTokenAccessesProtectedRoute::test_token_grants_jobs_list_access
0.06s call     tests/test_bremen_api_skeleton.py::TestImportSafety::test_no_pickle_import
0.06s call     tests/test_bremen_launch_flow.py::TestControlRoomLaunchFlow::test_launch_flow_no_model
0.06s call     tests/test_bremen_launch_flow.py::TestControlRoomLaunchFlow::test_launch_flow_catalog_refresh
0.06s call     tests/test_bremen_launch_flow.py::TestControlRoomLaunchFlow::test_launch_flow_catalog_selection
0.06s call     tests/test_bremen_launch_flow.py::TestControlRoomLaunchFlow::test_launch_flow_job_payload
0.06s call     tests/test_bremen_launch_flow.py::TestControlRoomLaunchFlow::test_launch_flow_keyboard_selection
0.06s call     tests/test_bremen_launch_flow.py::TestControlRoomLaunchFlow::test_launch_flow_stale_source
0.06s call     tests/test_bremen_launch_flow.py::TestControlRoomLaunchFlow::test_launch_flow_workflow_compat
0.06s call     tests/test_bremen_api_server.py::TestDemoH5Containers::test_containers_returns_200
0.06s call     tests/test_bremen_3x3_runtime_parity.py::test_h5_enumeration_does_not_change_scientific_output[3]
0.06s call     tests/test_bremen_auth_activation_readiness.py::TestPublicPagesStillPublic::test_auth_refresh_endpoint_accessible
0.06s call     tests/test_bremen_event_stream.py::TestSSEPromptDelivery::test_new_event_notified_quickly
0.06s call     tests/test_bremen_3x3_runtime_parity.py::test_h5_enumeration_does_not_change_scientific_output[0]
0.06s call     tests/test_bremen_auth_activation_readiness.py::TestPublicPagesStillPublic::test_auth_token_endpoint_accessible
0.06s call     tests/test_bremen_auth_activation_readiness.py::TestTokenAccessesProtectedRoute::test_token_grants_workspace_access
0.06s call     tests/test_bremen_auth_activation_readiness.py::TestTokenAccessesProtectedRoute::test_token_grants_workspace_job_access
0.05s call     tests/test_bremen_auth_activation_readiness.py::TestTokenAccessesProtectedRoute::test_token_grants_h5_containers_access
0.05s call     tests/test_bremen_auth_activation_readiness.py::TestTokenAccessesProtectedRoute::test_token_grants_report_access
0.05s call     tests/test_bremen_auth_activation_readiness.py::TestTokenIssuance::test_wrong_password_returns_none
0.05s call     tests/test_bremen_auth_activation_readiness.py::TestMissingInvalidToken401::test_wrong_secret_token_401
0.05s call     tests/test_bremen_auth_activation_readiness.py::TestTokenAccessesProtectedRoute::test_token_grants_external_report_access
0.05s call     tests/test_bremen_auth_activation_readiness.py::TestMissingInvalidToken401::test_401_no_secrets_in_response
0.05s call     tests/test_bremen_modeling.py::test_repeated_one_to_many_product_logistic_returns_specimen_predictions
0.05s call     tests/test_bremen_launch_flow.py::TestControlRoomLaunchFlow::test_js_parses_with_node
0.05s call     tests/test_bremen_api_skeleton.py::TestImportSafety::test_no_joblib_import
0.05s call     tests/test_bremen_auth_activation_readiness.py::TestTokenIssuance::test_authenticate_credentials_returns_token_pair
0.05s call     tests/test_bremen_api_skeleton.py::TestImportSafety::test_no_boto3_or_requests
0.05s call     tests/test_bremen_js_parse.py::TestControlRoomJavaScriptParse::test_js_parses_with_node
0.04s call     tests/test_bremen_auth_activation_readiness.py::TestPublicPagesStillPublic::test_public_routes_no_auth_required
0.04s call     tests/test_aramina_v0213_package.py::test_direct_package_prediction_matches_provider_route
0.04s call     tests/test_aramina_workflow_runtime.py::TestFastAPIAraminaRoutePlumbing::test_model_id_post_uses_real_provider_without_scaffold[False]
0.04s call     tests/test_bremen_auth.py::TestAuthenticateCredentials::test_valid_credentials_returns_token_pair
0.03s call     tests/test_bremen_preprocessing_one_to_one.py::test_one_to_one_pipeline_dataframe_and_joblib_contract
0.03s call     tests/test_bremen_auth_activation_readiness.py::TestFailClosedMissingConfig::test_missing_jwt_secret_fails_closed
0.03s call     tests/test_bremen_pipeline_config.py::test_preprocess_cli_can_write_minimal_output_columns
0.03s call     tests/test_bremen_preprocessing_one_to_many.py::test_one_to_many_pipeline_dataframe_and_joblib_contract
0.03s call     tests/test_bremen_auth_activation_readiness.py::TestEnforcementScopePreserved::test_public_routes_no_token_needed
0.03s call     tests/test_bremen_fastapi_auth_enforcement.py::TestPublicRoutesAlwaysReachable::test_auth_routes_no_existing_token
0.03s call     tests/test_bremen_auth_activation_readiness.py::TestEnforcementScopePreserved::test_protected_routes_require_token
0.03s call     tests/test_bremen_preprocessing_one_to_many.py::test_one_to_many_biopsy_pipeline_keeps_only_biopsy_rows
0.03s call     tests/test_bremen_auth_activation_readiness.py::TestMissingInvalidToken401::test_401_no_traceback
0.03s call     tests/test_bremen_auth_activation_readiness.py::TestEnforcementScopePreserved::test_browser_nav_routes_redirect_to_login
0.03s call     tests/test_bremen_auth_activation_readiness.py::TestMissingInvalidToken401::test_401_shape_is_safe
0.03s call     tests/test_bremen_auth_activation_readiness.py::TestMissingInvalidToken401::test_missing_token_401
0.03s call     tests/test_bremen_auth_activation_readiness.py::TestEnforcementScopePreserved::test_report_bootstrap_route_returns_shell
0.03s call     tests/test_bremen_auth_activation_readiness.py::TestMissingInvalidToken401::test_malformed_token_401
0.03s call     tests/test_bremen_auth_activation_readiness.py::TestPublicPagesStillPublic::test_auth_token_disabled_returns_503
0.03s call     tests/test_bremen_auth.py::TestAuthenticateCredentials::test_wrong_password_returns_none
0.03s call     tests/test_bremen_modeling.py::test_summary_helpers_handle_named_product_results
0.03s call     tests/test_bremen_auth.py::TestPasswordVerification::test_valid_password_passes
0.03s call     tests/test_bremen_auth_activation_readiness.py::TestFailClosedMissingConfig::test_short_jwt_secret_fails_closed
0.03s call     tests/test_bremen_auth_activation_readiness.py::TestTokenIssuance::test_wrong_username_returns_none
4398 passed, 13 skipped, 1676 warnings in 52.84s

```
