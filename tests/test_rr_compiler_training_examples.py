"""Real TRAIN compiler material stays an example, with prefix and arm isolation."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from legal_skill_guard.rr.compiler_contract import encode_compiler_program
from legal_skill_guard.rr.compiler_examples import compiler_examples_for_source, validate_compiler_example
from legal_skill_guard.rr.controls import ARMS
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.source_inference import predict_source
from legal_skill_guard.rr.source_program import compiler_prompt


ROOT = Path(__file__).resolve().parents[1]


def material():
    record = json.loads((ROOT / 'tests/fixtures/rr_scope_v5_binding_projection.json').read_text())
    item = {'source': record['source'],
        'program_json': json.dumps(encode_compiler_program(record['canonical_program'], record['source'])),
        'origin': {'role': 'teacher', 'call_id': record['paid_program_origin']}}
    return {**item, 'example_hash': digest(item)}


def target():
    sources = json.loads((ROOT / 'data/packets/rr_v2/public_train.json').read_text())['sources']
    return next(s for s in sources if s['key'] ==
        'SARA_v2_Binary:bb6b0bc1f7a04930f30caf8ca1a05613334ce26d79c0b11a3c6e1d25ef197aba')


def test_actual_example_keeps_exact_source_and_program_and_has_no_native_answer_field():
    item = material()
    previous, wire, compiled = validate_compiler_example(item)
    assert previous == item['source'] and wire == json.loads(item['program_json'])
    examples = compiler_examples_for_source({'compiler_examples': [item]}, target())
    assert len(examples) == 1 and examples[0]['program'] == wire
    assert 'answer' not in examples[0] and 'score' not in examples[0]
    assert compiled['source']['key'] != target()['key']


def test_self_example_and_tampered_material_are_rejected_before_generation():
    item = material()
    with pytest.raises(ValueError, match='current source'):
        compiler_examples_for_source({'compiler_examples': [item]}, item['source'])
    changed = deepcopy(item)
    changed['program_json'] += ' '
    with pytest.raises(ValueError, match='hash differs'):
        validate_compiler_example(changed)


def test_empty_examples_do_not_change_the_existing_compiler_request():
    source = target()
    assert compiler_prompt(source, None) == compiler_prompt(source, {'patterns': [], 'compiler_examples': []})


def test_native_contract_selects_examples_without_source_or_answer_routing():
    source = target()
    source = {**source, 'key': 'artificial:other_native_contract', 'dataset': 'ProofWriter_OWA_depth5'}
    assert compiler_examples_for_source({'compiler_examples': [material()]}, source) == []


class CapturedRequest(BaseException):
    pass


def test_all_six_arms_receive_identical_compiler_material_before_the_first_model_call():
    source = target()
    library = {'patterns': [], 'compiler_examples': [material()], 'frozen': True}
    payloads = []
    for arm in ARMS:
        def generate(messages, **kwargs):
            payloads.append(json.loads(messages[1]['content']))
            raise CapturedRequest()
        with pytest.raises(CapturedRequest):
            predict_source(source, arm=arm, library=library, generate=generate,
                tokenize=lambda *args, **kwargs: {'count': 1},
                request_config={'context_tokens': 32768, 'max_tokens': 8192}, thinking=False,
                partition='dev', example_model={'frozen': True}, controlled_shortcut=False)
    examples = [p['compiler_training_examples'] for p in payloads]
    assert all(e == examples[0] for e in examples)
    assert all(p['task_id'] == source['key'] for p in payloads)
    assert all(p['units'] == payloads[0]['units'] for p in payloads)
    assert all('accepted_program' in p and p['accepted_program'] is None for p in payloads)


def test_probe_refuses_a_current_or_future_compiler_example(tmp_path):
    from experiments.rr_v2_source_probe import load
    # Use the valid original example itself as the target: it is not earlier
    # than itself, independently of the full fixed TRAIN ordering.
    item = material()
    content = {'frozen': True, 'patterns': [], 'compiler_examples': [item]}
    path = tmp_path / 'library.json'
    path.write_text(json.dumps({'content': content, 'sha256': digest(content)}))
    manifest = json.loads((ROOT / 'reports/rr_v2_evidence/data_manifest.json').read_text())
    earlier = manifest['formal_train_order'][0]
    assert earlier != item['source']['key']
    for current in (item['source']['key'], earlier):
        with pytest.raises(ValueError, match='earlier original TRAIN'):
            load(ROOT, 'offline_example_prefix', source_id=current, library_path=path)
