"""Regression of the real B8 operation that reached the old NoModel client."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from experiments import legal_skill_evolution_source_batch_initial as initial


def test_real_learned_B8_reader_uses_explicit_client_and_preserves_unknown():
    t = initial.train
    library = t.read(t.OUT / 'B8/ConstraintAcquire/compiled_candidate.json')
    task = t.read(t.OUT / 'B8/teacher_task.json')
    sid = next(x['source_id'] for x in task['tasks'] if 'bc93d2a' in x['source_id'])
    calls = []
    class OfflineUnknown:
        config = t.prepare()['executor_profile']
        ledger = SimpleNamespace(run_id='offline_B8_regression')
        def tokenize(self, messages, **kwargs):
            calls.append(('tokenize', kwargs))
            return {'count': 1000}
        def generate(self, identity, **kwargs):
            # No model or fabricated positive/absence semantics: exercise the
            # real operation's unknown branch with no new physical request.
            assert identity.startswith(self.ledger.run_id + ':')
            assert kwargs['source'] == sid and kwargs['purpose'] == 'skill_replay'
            assert kwargs['thinking'] is False
            calls.append(('generate', identity))
            schema = kwargs['schema']
            keys = schema['properties']['answers']['properties']
            return {'content': json.dumps({'answers': {q: {'choice': 'unknown', 'evidence_unit_ids': []} for q in keys}}),
                'finish_reason': 'stop', 'cache_hit': True}
    with TemporaryDirectory() as directory:
        row = initial.evaluate(library, sid, 'ConstraintAcquire', 8, Path(directory)/'case.json', client=OfflineUnknown())
        assert 'error' not in row, row.get('error')
        assert row['observation']['execution']['new_physical_requests'] == 0
        answers = row['observation']['visible_inputs']['answers']
        assert answers and all(a['choice'] == 'unknown' for a in answers)
        assert list((Path(directory)/'case_read_events').glob('*.json'))
    assert [c[0] for c in calls] == ['tokenize', 'generate']
