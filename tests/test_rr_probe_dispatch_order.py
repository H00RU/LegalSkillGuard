"""Actual sealed-probe ordering defect, exercised through its run dispatcher."""
import hashlib
import json
from pathlib import Path

import pytest

import experiments.rr_v2_source_probe as probe
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.source_program import compiler_prompt, program_schema
from legal_skill_guard.rr.source_code import compiler_response_schema


@pytest.mark.parametrize('tamper', [False, True])
def test_probe_dispatch_reconstructs_and_verifies_production_schema_order(tmp_path, monkeypatch, tamper):
    root = Path(__file__).resolve().parents[1]
    public = json.loads((root / 'data/packets/rr_v2/public_train.json').read_text())['sources']
    source = next(s for s in public if s['key'] == 'SARA_v2_Binary:743ac2e5258037a15b0e3549f47db2e50d051ec4449a3493120048fee188a814')
    schema = compiler_response_schema()
    system, user = compiler_prompt(source)
    config = {'library': None, 'source_selection': 'sealed public source', 'compiler_role': 'executor',
              'teacher': {}, 'executor': {'enable_thinking': False}}
    stage = tmp_path / 'artifacts/rr_method_runtime_20261107/order_probe'
    seal = {'source': source, 'config': config, 'files': {}, 'library_path': None, 'compiler_origin': None,
            'binding': {}, 'authorization_hash': 'offline', 'system': system, 'user': user, 'schema': schema,
            'schema_order_sha256': 'tampered' if tamper else hashlib.sha256(json.dumps(schema, ensure_ascii=False).encode()).hexdigest()}
    immutable_json(stage / 'seal.json', seal)
    persisted = json.loads((stage / 'seal.json').read_text())
    assert persisted['schema'] == schema
    assert list(persisted['schema']['properties']) == ['code']
    internal = program_schema(source)
    assert list(json.loads(json.dumps(internal, sort_keys=True))['properties']) != list(internal['properties'])
    captured = []
    class Ledger:
        def __init__(self, *args, **kwargs): pass
        def export(self): return {'executor_used': 0, 'teacher_used': 0, 'calls': []}
    class Executor:
        def __init__(self, *args, **kwargs): pass
        def generate(self, *args, **kwargs):
            captured.append(kwargs['schema'])
            raise RuntimeError('offline dispatch sentinel; no model call')
    monkeypatch.setattr(probe, 'load', lambda *a, **k: ({'ledger_path': 'unused'}, {}, source, config, {}, stage))
    monkeypatch.setattr(probe, 'science_files', lambda root: {})
    monkeypatch.setattr(probe, 'MethodLedger', Ledger)
    monkeypatch.setattr(probe, 'MethodTeacher', lambda *a, **k: None)
    monkeypatch.setattr(probe, 'MethodExecutor', Executor)
    if tamper:
        with pytest.raises(ValueError, match='Ordered compiler schema'):
            probe.run(tmp_path, 'order_probe')
        assert captured == []
    else:
        result = probe.run(tmp_path, 'order_probe')
        assert result['status'] == 'component_probe_unresolved'
        assert len(captured) == 1
        assert json.dumps(captured[0], ensure_ascii=False) == json.dumps(schema, ensure_ascii=False)
        assert list(captured[0]['properties']) == ['code']
