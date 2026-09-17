"""PR0161: additive metadata, truthful timestamps and safe failed reports."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import h5py
import pytest

from bremen.api import job_api_handler as jobs
from bremen.api.job_models import AnalysisJob, WorkflowRun
from bremen.api.model_result_mapper import build_standard_result, normalize_timestamp
from bremen.api.report_failures import build_failure_report
from bremen.model_runtime import SourceMetadata
from tests.test_bremen_standard_model_result_v1 import BREMEN_SUMMARY, ARAMINA_SUMMARY


@pytest.mark.parametrize('workflow,summary', [('bremen', BREMEN_SUMMARY), ('aramina', ARAMINA_SUMMARY)])
@pytest.mark.parametrize('physician,expected', [(None, ''), ('', ''), (' Dr Example ', 'Dr Example')])
def test_common_physician_and_missing_values(workflow, summary, physician, expected):
    source = SourceMetadata(referring_physician=physician).to_dict()
    result = build_standard_result(workflow, {**summary, 'source_metadata': source})
    assert result['referring_physician'] == expected
    keys = list(result)
    assert keys[keys.index('patient_age') + 1] == 'referring_physician'
    assert 'referring_physician' not in result['specific_output']
    assert result['eoscan_version'] is None
    assert result['patient_age'] is None
    old = build_standard_result(workflow, summary)
    for key in ('risk_probability', 'threshold_value', 'target_class_risk_level'):
        assert result[key] == old[key]


@pytest.mark.parametrize('workflow', ['bremen', 'aramina'])
def test_package_adapter_default_and_raw_timestamp(tmp_path, workflow):
    from importlib import import_module
    module = import_module('bremen.model_packages.' + (
        'bremen_v01' if workflow == 'bremen' else 'aramina_v0213') + '.source_metadata')
    path = tmp_path / 'metadata.h5'
    with h5py.File(path, 'w') as f:
        f.create_group('session').attrs['started_at'] = '2025-05-28 10:19:55'
        # Unsupported aliases must not get promoted into the canonical field.
        f['session'].attrs['doctor'] = 'unsupported physician alias'
    source = module.extract_source_metadata(str(path))
    assert source.referring_physician == ''
    assert source.scan_date_time == '2025-05-28 10:19:55'


@pytest.mark.parametrize('value,expected', [
    ('2025-05-28 10:19:55', '2025-05-28T10:19:55'),
    ('2025-05-14T12:55:46.123+00:00', '2025-05-14T12:55:46+00:00'),
    ('2025-05-14T12:55:46.123-05:30', '2025-05-14T12:55:46-05:30'),
    ('2025-05-14T12:55:46Z', '2025-05-14T12:55:46+00:00'),
    ('2025-05-14T12:55:46-00:00', '2025-05-14T12:55:46-00:00'),
    ('2025-05-28', ''), ('2025-02-30T10:00:00', ''), ('bad date', ''),
    (None, ''), ('', ''), ('2025-05-28T10:19:55+01:02:03', ''),
])
def test_shared_timestamp_policy(value, expected):
    assert normalize_timestamp(value) == expected
    assert normalize_timestamp(expected) == expected
    for workflow, summary in [('bremen', BREMEN_SUMMARY), ('aramina', ARAMINA_SUMMARY)]:
        result = build_standard_result(workflow, {**summary, 'source_metadata': {'scan_date_time': value}})
        assert result['scan_date_time'] == expected


def test_generic_mapping_has_no_source_aliases():
    for path in ('src/bremen/api/model_result_mapper.py', 'src/bremen/api/report_failures.py'):
        text = Path(path).read_text()
        for forbidden in ('h5py', '/session', 'operator_username', 'started_at', 'backfill_provenance'):
            assert forbidden not in text


@pytest.fixture
def job_store():
    jobs.reset_for_tests()
    yield
    jobs.reset_for_tests()


def _insert(workflow, failure, *, details=None, status='failed', overall='failed'):
    run = WorkflowRun(
        workflow_id=workflow, status=status, failure=failure,
        failure_details=details or {},
        model_identity={'model_id': workflow + '-test', 'model_version': 'test-version'},
    )
    job = AnalysisJob(
        job_id='test-job', request_id='test-request', created_at='2026-09-17T12:00:00Z',
        overall_status=overall, requested_workflows=(workflow,),
        input_summary={'patient_display_name': 'SYNTH-1', 'target_side': 'left',
                       'source_key': 's3://private/key'},
        workflow_runs={workflow: run},
    )
    jobs._jobs[job.job_id] = job
    return job, run


def test_failed_bremen_report_and_unchanged_job_diagnostics(job_store):
    job, run = _insert('bremen', 'Feature construction failed: raw_peak_gate_failed')
    before = copy.deepcopy(run.to_dict())
    report = jobs.get_job_report(job.job_id, 'bremen')['report']
    assert report['status'] == 'unavailable'
    assert report['reason_code'] == 'REPORT_NOT_AVAILABLE'
    assert report['failure_reason_code'] == 'raw_peak_gate_failed'
    assert report['failure_stage'] == 'features'
    assert report['model_id'] == 'bremen-test'
    assert report['patient_id'] == 'SYNTH-1'
    assert 'standard_result' not in report and 'payload' not in report
    assert run.to_dict() == before


def test_failed_aramina_preserves_safe_preprocessing_diagnostics(job_store):
    from bremen.api.aramina_api_errors import unsupported_input_details
    details = unsupported_input_details('SYNTH-1', 'left', 'test-version',
        stage='preprocessing_contract', model_id='aramina-test',
        requested_patient_id='SYNTH-1', preprocessing_release='v0.1.7-beta',
        preprocessing_diagnostic={'stage': 'worker_pipeline_execution',
                                  'exception_class': 'ValueError',
                                  'transformer': 'AzimuthalIntegration'})
    job, run = _insert('aramina', 'ARAMINA_UNSUPPORTED_INPUT', details=details)
    before = copy.deepcopy(run.to_dict())
    report = jobs.get_job_report(job.job_id, 'aramina')['report']
    for key in ('failure_stage', 'failure_reason_code', 'failure_detail', 'remediation', 'safe_details'):
        assert report[key] == details[key]
    assert report['target_side'] == 'left'
    assert 'standard_result' not in report
    assert run.to_dict() == before


@pytest.mark.parametrize('workflow', ['bremen', 'aramina'])
@pytest.mark.parametrize('malicious', ['/private/model.joblib', 's3://bucket/key',
                                     'Traceback token=secret', {'nested': 'private'}, ['private']])
def test_failure_report_never_echoes_raw_material(job_store, workflow, malicious):
    details = {'failure_stage': malicious, 'failure_detail': malicious,
               'remediation': malicious, 'failure_reason_code': malicious,
               'safe_details': {'preprocessing_stage': malicious, 'token': 'SECRET',
                                'preprocessing_exception_class': malicious,
                                'model_checksum': 'PRIVATE_CHECKSUM'}}
    job, run = _insert(workflow, 'ARAMINA_UNSUPPORTED_INPUT' if workflow == 'aramina' else malicious,
                       details=details)
    run.model_identity = {'model_id': '/private/model', 'model_version': 's3://bucket/key'}
    report = jobs.get_job_report(job.job_id, workflow)['report']
    text = json.dumps(report)
    for forbidden in ('/private', 's3://', 'Traceback', 'token', 'SECRET', 'PRIVATE_CHECKSUM', 'standard_result'):
        assert forbidden not in text
    assert report['model_id'] == ''


def test_configuration_failure_and_normalization_failure(job_store):
    job, run = _insert('bremen', 'Workflow configuration required for multi-position input',
                       overall='workflow_configuration_required')
    assert jobs.get_job_report(job.job_id, 'bremen')['report']['failure_reason_code'] == 'workflow_configuration_required'
    job.workflow_runs.clear()
    job.overall_status = 'normalization_failed'
    assert jobs.get_job_report(job.job_id, 'bremen')['report']['failure_reason_code'] == 'SOURCE_PREPARATION_FAILED'


@pytest.mark.parametrize('workflow,summary', [('bremen', BREMEN_SUMMARY), ('aramina', ARAMINA_SUMMARY)])
def test_successful_report_preserves_legacy_science_and_failed_sibling(job_store, workflow, summary):
    job, run = _insert(workflow, None, status='completed', overall='failed')
    run.result_summary = copy.deepcopy(summary)
    jobs._register_default_providers()
    jobs._generate_job_reports(job)
    report = jobs.get_job_report(job.job_id, workflow)['report']
    assert 'payload' in report
    standard = report['standard_result']
    assert standard['referring_physician'] == ''
    expected = build_standard_result(workflow, summary)
    for key in ('risk_probability', 'threshold_value', 'target_class_risk_level'):
        assert standard[key] == expected[key]
    assert run.result_summary == summary


def test_unknown_pending_and_absent_workflow_unchanged(job_store):
    assert jobs.get_job_report('missing', 'bremen')['report'] == {'status': 'job_not_found'}
    job, _ = _insert('bremen', None, status='running', overall='running')
    report = jobs.get_job_report(job.job_id, 'aramina')['report']
    assert report['reason_code'] == 'WORKFLOW_OR_REPORT_PROVIDER_NOT_CONFIGURED'
    assert 'failure' not in report


def test_unknown_failure_falls_back_without_echo():
    result = build_failure_report('aramina', failure='private exception token=SECRET')
    assert result['failure'] == 'WORKFLOW_EXECUTION_FAILED'
    assert 'SECRET' not in json.dumps(result)
