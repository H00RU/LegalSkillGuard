from copy import deepcopy
import json

from experiments import legal_skill_evolution_mixed_component_training as training
from legal_skill_guard.inference.codex_cli_client import CodexInvocationError
from legal_skill_guard.skill_evolution.observation_training_history import completed_history


def test_failed_teacher_retains_library_and_is_not_implicitly_retried(tmp_path, monkeypatch):
    original = training.PREVIOUS_OUT
    task = training.read(original / 'B3/teacher_task.json')
    protocol = training.read(original / 'protocol.json')
    folder = tmp_path / 'B3'
    folder.mkdir()
    (folder / 'teacher_task.json').write_text(json.dumps(task))
    method = folder / 'CoverageRecombine'
    method.mkdir()
    (method / 'teacher.json').write_bytes((original / 'B3/CoverageRecombine/teacher.json').read_bytes())
    calls = []

    class FailedTeacher:
        def __init__(self, *args):
            pass

        def propose(self, call_id, **kwargs):
            calls.append(call_id)
            raise CodexInvocationError('offline fixture of the actual deadline failure')

    monkeypatch.setattr(training, 'OUT', tmp_path)
    monkeypatch.setattr(training, 'FrozenTeacher', FailedTeacher)
    libraries = task['current_libraries_both_available']
    kernels = {source: {} for source in protocol['sources'] if source.startswith('SARA_v2_Binary:')}
    before = deepcopy(libraries['FreeGlobalUpdate'])
    training.acquire(protocol, None, 3, libraries, [], {}, kernels, {})
    training.acquire(protocol, None, 3, libraries, [], {}, kernels, {})
    assert len(calls) == 1
    failure = training.read(folder / 'FreeGlobalUpdate/teacher_failure.json')
    assert failure['status'] == 'no_trustworthy_proposal'
    assert not (folder / 'FreeGlobalUpdate/teacher.json').exists()
    bank = training.candidates(before, None, 'FreeGlobalUpdate')
    assert bank == {'FreeGlobalUpdate/retained': before}


def test_completed_history_keeps_missing_proposal_distinct_from_empty_rules(tmp_path):
    original = training.PRIOR_OUT / 'B1'
    folder = tmp_path / 'B1'
    folder.mkdir()
    for name in ('checkpoint.json', 'teacher_task.json', 'initial_scored_results.json'):
        (folder / name).write_bytes((original / name).read_bytes())
    for arm in training.ARMS:
        (folder / arm).mkdir()
    (folder / 'CoverageRecombine/teacher.json').write_bytes((original / 'CoverageRecombine/teacher.json').read_bytes())
    (folder / 'FreeGlobalUpdate/teacher_failure.json').write_text(json.dumps(
        {'status': 'no_trustworthy_proposal', 'no_implicit_retry': True}))
    history = completed_history(tmp_path, 2, training.ARMS)
    assert history[0]['actual_teacher_proposals']['FreeGlobalUpdate'] is None
    assert history[0]['actual_teacher_failures']['FreeGlobalUpdate']['status'] == 'no_trustworthy_proposal'
