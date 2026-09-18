"""PR0163 orchestration contracts; fake package runtime, no scientific assertions."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from bremen.api.http.app import create_app
from bremen.api.model_requirements import run_model_pipeline_dry_run
from bremen.contracts.execution import WorkflowResult
from bremen.contracts.model_runtime import ModelValidation
from bremen.platform.jobs import service as jobs
from bremen.platform.runtime.registry import ModelDescriptor, RuntimeRegistry
from bremen.platform.events.trace import build_trace_from_events
from tests.test_bremen_standard_model_result_v1 import BREMEN_SUMMARY, ARAMINA_SUMMARY


class ManualExecutor:
    def __init__(self):
        self.tasks = []

    def submit(self, fn, *args, **kwargs):
        self.tasks.append((fn, args, kwargs))

    def run(self):
        fn, args, kwargs = self.tasks.pop(0)
        fn(*args, **kwargs)


@pytest.fixture
def setup(monkeypatch, tmp_path):
    jobs.reset_for_tests()
    executor = ManualExecutor()
    monkeypatch.setattr(jobs, '_executor', executor)
    path = tmp_path / 'input.h5'
    path.write_bytes(b'opaque test source')
    monkeypatch.setattr('bremen.platform.sources.service.extract_patient_display_name',
                        lambda path: 'Nova_257')
    monkeypatch.setattr('bremen.platform.sources.service.resolve_source',
                        lambda *args, **kwargs: str(path))
    monkeypatch.setattr('bremen.api.model_requirements._resolve_source_for_dry_run',
                        lambda source: str(path))
    monkeypatch.setattr('bremen.platform.models.registry.get_model_entry',
                        lambda model: SimpleNamespace(workflow_id='aramina' if 'aramina' in model else 'bremen',
                                                      model_version=model))
    monkeypatch.setattr('bremen.platform.models.registry.get_registry',
                        lambda: SimpleNamespace(catalog_status='not_configured', available_count=0))
    yield executor, path
    jobs.reset_for_tests()


def runtime_registry(monkeypatch, workflow, fail=False, entered=None, release=None):
    from bremen.model_packages.aramina_v0213.errors import AraminaWorkflowError
    from bremen.platform.reports.runtime_projection import aramina_failure, bremen_failure

    class Runtime:
        def validate_model_input(self, model_input):
            if workflow == 'aramina':
                assert model_input.patient_id == 'Nova_257'
                assert model_input.target_side in ('left', 'right')
            return ModelValidation(compatible=True)

        def predict_model(self, model_input, **kwargs):
            if entered:
                entered.set()
                assert release.wait(10)
            if fail:
                raise AraminaWorkflowError('ARAMINA_UNSUPPORTED_INPUT', 'preprocessing_contract')
            return None

    summary = ARAMINA_SUMMARY if workflow == 'aramina' else BREMEN_SUMMARY
    descriptor = ModelDescriptor(
        workflow, Runtime(),
        lambda *args: WorkflowResult(workflow, 'completed', payload=summary),
        aramina_failure if workflow == 'aramina' else bremen_failure,
        failure_event_reason=True,
    )
    registry = RuntimeRegistry()
    registry.register(descriptor)
    monkeypatch.setattr('bremen.platform.runtime.executor.get_default_registry', lambda: registry)
    monkeypatch.setattr('bremen.platform.runtime.registry.get_descriptor_for_model', lambda model: descriptor)
    return registry


def body(workflow='aramina', **overrides):
    return dict(workflow_id=workflow, model_id=workflow + '-test', source_id='opaque',
                patient_id='Nova_257', target_side='left', **overrides)


@pytest.mark.parametrize('workflow', ['bremen', 'aramina'])
def test_http_queued_completed_reuse_and_bare_report(setup, monkeypatch, workflow):
    executor, _ = setup
    runtime_registry(monkeypatch, workflow)
    with TestClient(create_app()) as client:
        request = body(workflow)
        first = client.post('/demo/api/jobs', json=request)
        assert first.status_code == 201, first.text
        jid = first.json()['job']['job_id']
        assert first.json()['job']['overall_status'] == 'queued'
        assert first.json()['reused_existing'] is False
        duplicate = client.post('/demo/api/jobs', json=request)
        assert duplicate.status_code == 200
        assert duplicate.json()['reused_existing'] is True
        assert duplicate.json()['job']['job_id'] == jid
        assert len(executor.tasks) == 1
        executor.run()
        completed = client.get('/demo/api/jobs/' + jid).json()
        assert completed['overall_status'] == 'completed'
        replay = client.post('/demo/api/jobs', json=request)
        assert replay.status_code == 200
        assert replay.json()['job']['job_id'] == jid
        assert not executor.tasks
        report = client.get(f'/demo/api/jobs/{jid}/reports/{workflow}').json()['report']
        standard = report['standard_result']
        assert isinstance(standard, dict)
        assert 'aramina' not in standard and 'bremen' not in standard
        if workflow == 'aramina':
            assert 'risk_score' in report['payload']
            assert 'technical_demo_only' in report['payload']
            assert standard['specific_output']['target_side'] == 'left'
            assert 'mammography_suspicious_field' in standard['specific_output']
        else:
            assert report['payload']['report_type'] == 'bremen_mri_triage'
            assert 'p_mri_needed' in report['payload']['score_and_threshold']
            assert standard['specific_output'] == {}
        trace = build_trace_from_events(jobs._event_store, jid, workflow)
        assert trace.status == 'completed'
        assert trace.completed_stage_count > 0
        assert trace.current_stage == 'report_completed'


def test_atomic_identity_and_dimensions(setup, monkeypatch):
    executor, path = setup
    runtime_registry(monkeypatch, 'aramina')
    from bremen.contracts.request import AnalysisParameters
    request = AnalysisParameters(container_id='', source_id='', patient_id='Nova_257', target_side='left')
    kwargs = dict(workflow_id='aramina', model_id='aramina-a', h5_path=str(path),
                  source_key='stable-version-1', aramina_request=request, target_side='left')
    with ThreadPoolExecutor(max_workers=8) as callers:
        results = list(callers.map(lambda _: jobs.submit_analysis_job(**kwargs), range(16)))
    assert len({job.job_id for job, _ in results}) == 1
    assert sum(not reused for _, reused in results) == 1
    assert len(executor.tasks) == 1
    original = results[0][0]
    for status in ('running', 'failed', 'completed'):
        original.overall_status = status
        same, reused = jobs.submit_analysis_job(**kwargs)
        assert reused and same.job_id == original.job_id
    for changed in (
        dict(model_id='aramina-b'), dict(source_key='stable-version-2'),
        dict(target_side='right', aramina_request=AnalysisParameters(
            container_id='', source_id='', patient_id='Nova_257', target_side='right')),
        dict(aramina_request=AnalysisParameters(
            container_id='', source_id='', patient_id='another-patient', target_side='left')),
    ):
        different, reused = jobs.submit_analysis_job(**{**kwargs, **changed})
        assert not reused and different.job_id != original.job_id
    assert len(executor.tasks) == 5


def test_http_returns_while_real_background_worker_blocked(setup, monkeypatch):
    entered, release = Event(), Event()
    runtime_registry(monkeypatch, 'bremen', entered=entered, release=release)
    with ThreadPoolExecutor(max_workers=1) as worker:
        monkeypatch.setattr(jobs, '_executor', worker)
        try:
            with TestClient(create_app()) as client:
                response = client.post('/demo/api/jobs', json=body('bremen'))
                assert response.status_code == 201
                assert entered.wait(5)
                assert not release.is_set()
                assert response.json()['job']['overall_status'] in ('queued', 'running')
                duplicate = client.post('/demo/api/jobs', json=body('bremen'))
                assert duplicate.status_code == 200
                assert duplicate.json()['job']['job_id'] == response.json()['job']['job_id']
                assert duplicate.json()['job']['overall_status'] == 'running'
        finally:
            release.set()


@pytest.mark.parametrize('version', ['0.2.12', '0.2.13'])
@pytest.mark.parametrize('fail', [False, True])
def test_aramina_preflight_execution_parity_without_persistence(setup, monkeypatch, version, fail):
    executor, path = setup
    registry = runtime_registry(monkeypatch, 'aramina', fail=fail)
    dry = run_model_pipeline_dry_run('aramina-' + version, 'display', 'opaque', 'aramina',
                                     patient_id='Nova_257', target_side='left')
    assert not jobs._jobs
    assert dry.ready_to_run is not fail
    from bremen.contracts.request import AnalysisParameters
    job = jobs.create_analysis_job(
        workflow_id='aramina', model_id='aramina-' + version, h5_path=str(path),
        registry=registry, aramina_request=AnalysisParameters(
            container_id='', source_id='', patient_id='Nova_257', target_side='left'),
    )
    assert job.overall_status == ('failed' if fail else 'completed')
    trace = build_trace_from_events(jobs._event_store, job.job_id, 'aramina')
    assert trace.status == job.overall_status
    if fail:
        assert dry.failure_stage == trace.current_stage == 'preprocessing_contract'
        assert dry.failure_reason_code == 'ARAMINA_UNSUPPORTED_INPUT'
        assert next(s for s in trace.stages if s.stage_id == trace.current_stage).status == 'failed'


def test_source_identity_stable_across_handles_but_versioned():
    from bremen.platform.sources.registry import register_source, get_stable_source_key
    def register(version):
        return register_source('bucket', 'key.h5', 'generic.h5', 12, '', source_version=version)
    a, b, c = register('v1'), register('v1'), register('v2')
    assert a != b
    assert get_stable_source_key(a) == get_stable_source_key(b)
    assert get_stable_source_key(a) != get_stable_source_key(c)


def test_scheduling_and_worker_failure_become_terminal(setup, monkeypatch):
    _, path = setup
    def broken(*args, **kwargs):
        raise RuntimeError('private detail')
    monkeypatch.setattr(jobs._executor, 'submit', broken)
    job, _ = jobs.submit_analysis_job(workflow_id='bremen', model_id='bremen-test',
                                      h5_path=str(path), source_key='stable')
    assert job.overall_status == 'failed'
    assert job.workflow_runs['bremen'].failure == 'JOB_EXECUTION_FAILED'
    assert 'private detail' not in str(job.to_dict())
    monkeypatch.setattr(jobs, '_run_analysis_job', broken)
    jobs._execute_analysis_job(job)
    assert job.overall_status == 'failed'
