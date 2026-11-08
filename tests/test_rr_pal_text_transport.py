"""Direct program transport preserves syntax, witnesses and unresolved rules."""
from pathlib import Path
import json

import pytest

from legal_skill_guard.rr.coverage import Unsupported, digest
from legal_skill_guard.rr.learning import SkillLibrary
from legal_skill_guard.rr.method_client import MethodExecutor
from legal_skill_guard.rr.pal_frontend import decode_pal_text, parse_pal, render_pal, pal_prompt
from legal_skill_guard.rr.program_inference import predict_source
from legal_skill_guard.rr.rule_templates import matching_rule_template, instance_request, instantiate_rule_template
from legal_skill_guard.rr.source_execution import assess_source

ROOT = Path(__file__).resolve().parents[1]


def airline_material():
    seal = json.loads((ROOT / 'artifacts/rr_method_runtime_20261107/reference_case_airline7_v15_20261108/seal.json').read_text())
    source, library = seal['source'], seal['config']['library']
    return source, library, matching_rule_template(source, library)


def test_only_a_complete_optional_fence_is_removed_without_inventing_python_structure():
    code = 'x = 1 # s156\nquery = x'
    assert decode_pal_text(code) == code
    assert decode_pal_text('```python\n' + code + '\n```') == code
    assert parse_pal(decode_pal_text('```\n' + code + '\n```')) == parse_pal(code)
    for text in ['```python\nx=1', '```python\n' + code + '\n```\nextra prose',
                 'Here is code:\n```python\n' + code + '\n```']:
        with pytest.raises(Unsupported):
            parse_pal(decode_pal_text(text))


def test_real_paid_single_line_failure_is_not_repaired_by_guessing_newlines_or_rules():
    stage = ROOT / 'artifacts/rr_method_runtime_20261107/reference_case_airline7_v15_20261108'
    hashes = []
    for step in range(2):
        value = json.loads((stage / 'calls' / digest(stage.name + ':parse:' + str(step)) / 'result.json').read_text())
        code = json.loads(value['content'])['code']
        assert len(code.splitlines()) == 1 and decode_pal_text(code) == code
        with pytest.raises(Unsupported, match='exact trailing source IDs'):
            parse_pal(decode_pal_text(code))
        hashes.append(digest(value['content']))
    assert hashes[0] == hashes[1]


def test_direct_executor_request_removes_only_transport_schema_and_keeps_locked_sampling():
    source, library, match = airline_material()
    messages, schema = instance_request(source, match)
    assert set(schema['properties'])=={'current_item_source','program_lines'}
    assert 'Python line-list' in messages[0]['content']
    config = json.loads((ROOT / 'configs/rr_v2_preflight.json').read_text())['executor']
    payload = MethodExecutor(None, ROOT, config).payload(messages=messages, thinking=False, schema=schema)
    assert payload['response_format']['json_schema']['schema']==schema
    assert payload['chat_template_kwargs']['enable_thinking'] is False
    assert payload['max_tokens'] == 8192 and payload['temperature'] == .6 and payload['seed'] == 45
    ordinary = pal_prompt(source, library)
    teacher = pal_prompt(source, library, full_template=True)
    assert 'direct text' in ordinary[0]['content'] and 'code string' in teacher[0]['content']


def test_old_failed_program_does_not_get_a_guessed_current_item_selector():
    source,library,match=airline_material()
    stage=ROOT/'artifacts/rr_method_runtime_20261107/reference_text_airline7_v17_20261108'
    paid=json.loads((stage/'calls'/digest(stage.name+':parse:0')/'result.json').read_text())
    from jsonschema import ValidationError
    with pytest.raises(ValidationError):
        instantiate_rule_template(source,match,{'program_lines':paid['content'].splitlines()},library=library)
    messages,_=instance_request(source,match);payload=json.loads(messages[1]['content'])
    assert 'query =' in '\n'.join(payload['earlier_TRAIN_case_application']['program_lines'])
    assert 'one flat add' in messages[0]['content']


def test_real_invalid_query_keeps_its_syntax_error_and_exact_code_location():
    stage = ROOT / 'artifacts/rr_method_runtime_20261107/reference_text_airline7_v16_20261108'
    for step in range(2):
        paid = json.loads((stage / 'calls' / digest(stage.name + ':parse:' + str(step)) / 'result.json').read_text())
        with pytest.raises(Unsupported) as error:
            parse_pal(decode_pal_text(paid['content']))
        issue = error.value.diagnostics[0]
        assert issue['path'] == 'code' and issue['line'] == 128 and issue['column'] > 0
        assert "unmatched ')'" in issue['actual']


def test_actual_common_inference_entry_accepts_program_text_without_an_executor_json_wrapper(tmp_path):
    control = json.loads((ROOT / 'tests/fixtures/rr_pal_teacher_control.json').read_text())
    program = control['program']
    seen = []

    def generate(messages, *, purpose, step, schema):
        seen.append(schema)
        if step:
            raise KeyboardInterrupt
        assert schema is None
        return {'content': render_pal(program), 'finish_reason': 'stop', 'request_hash': 'offline_control'}

    with pytest.raises(KeyboardInterrupt):
        predict_source(control['source'], arm='M11', library=SkillLibrary(stage='formal_train').export(),
                       generate=generate, tokenize=lambda messages, thinking: {'count': 1000},
                       request_config={'max_tokens': 8192, 'context_tokens': 32768}, thinking=False,
                       partition='train', controlled_shortcut=False, journal=tmp_path / 'journal')
    state = json.loads(json.loads((tmp_path / 'journal/state0.json').read_text())['state_json'])
    assert state['compiled_valid'] is True and state['program'] == program
    assert seen[0] is None and seen[1] is not None
