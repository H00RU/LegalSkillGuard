"""Actual truncated output supplies diagnostics, never an adapted program."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from legal_skill_guard.rr.compiler_contract import compiler_response_schema,encode_compiler_program
from legal_skill_guard.rr.source_program import compiler_prompt
from legal_skill_guard.rr.source_validation import incomplete_feedback


ROOT=Path(__file__).resolve().parents[1]


def actual():
    return json.loads((ROOT/'tests/fixtures/rr_actual_ast_scope_v2.json').read_text())


def test_actual_paid_truncation_exposes_duplicate_names_and_numeric_type_errors():
    case=actual();raw=case['raw_content']
    assert hashlib.sha256(raw.encode()).hexdigest()==case['raw_sha256']
    result=incomplete_feedback(raw)
    assert result['candidate_reconstructed'] is False and result['prefix_only']
    assert result['complete_declaration_count']==34
    duplicate=next(d for d in result['issues'] if d['expected']=='unique symbol name' and d['actual']['name']=='s11')
    assert duplicate['actual']['name']=='s11' and duplicate['occurrences']==12
    assert any(d['expected']=='numbers' and d['actual']==['array'] for d in result['issues'])
    assert not any(k in result for k in ('program','answer','observations','query'))
    assert case['raw_content']==raw


def test_incomplete_row_is_not_completed_or_used_as_declaration():
    raw='{"bindings":[{"name":"x","type":"integer","sources":["s0"],"value":1},{"name":"x"'
    result=incomplete_feedback(raw)
    assert result['complete_declaration_count']==1 and result['issues']==[]


def test_future_dependencies_do_not_get_invented_types_or_unbound_diagnoses():
    raw='{"nodes":[{"name":"test","kind":"expression","body":{"op":"number_at","args":[{"var":"future"},0]}}],"scopes":'
    assert incomplete_feedback(raw)['issues']==[]


def test_duplicate_JSON_keys_are_not_interpreted_as_a_unique_declaration():
    assert incomplete_feedback('{"bindings":[{"name":"x","name":"y"}],"scopes":') is None
    assert incomplete_feedback('{"bindings":[],"bindings":[]}') is None


def test_complete_JSON_still_uses_the_normal_full_validation_path():
    assert incomplete_feedback('{"bindings":[]}') is None


def test_current_schema_prompt_and_accepted_wire_share_input_first_field_order():
    case=json.loads((ROOT/'tests/fixtures/rr_scope_v5_binding_projection.json').read_text())
    schema=compiler_response_schema(case['source']);wire=encode_compiler_program(case['canonical_program'],case['source'])
    order=['bindings','observations','rule_residuals','nodes','scopes','clauses','query']
    system,user=compiler_prompt(case['source'],accepted_program=case['canonical_program'])
    assert list(schema['properties'])==schema['required']==list(wire)==order
    assert ', '.join(order) in system
    assert list(json.loads(user)['accepted_program'])==order


def test_production_train_retry_receives_actual_prefix_errors_without_candidate_reconstruction():
    from legal_skill_guard.rr.source_inference import predict_source
    case=actual();requests=[]
    def generate(messages,**kwargs):
        requests.append(deepcopy(messages))
        return {'content':case['raw_content'],'request_hash':case['raw_sha256']}
    result=predict_source(case['source'],arm='M11',library={'patterns':[]},generate=generate,
        tokenize=lambda *a,**k:{'count':100},request_config={'context_tokens':32768,'max_tokens':8192},
        thinking=False,partition='train',controlled_shortcut=False)
    assert len(requests)==2 and result['program'] is None
    feedback=json.loads(requests[1][1]['content'])['validation_feedback']['previous_error']['complete_prefix_diagnosis']
    assert feedback['candidate_reconstructed'] is False
    assert any(d['expected']=='unique symbol name' for d in feedback['issues'])
    assert not result['result']['structural_pass'] and result['result']['answer'] is None


def test_actual_typed_operand_failure_reports_known_relation_inputs_as_wrong_string_keys():
    case=json.loads((ROOT/'tests/fixtures/rr_actual_ast_typed_operands_v1.json').read_text())
    assert hashlib.sha256(case['raw_content'].encode()).hexdigest()==case['raw_sha256']
    result=incomplete_feedback(case['raw_content'])
    assert result['candidate_reconstructed'] is False
    assert any(d['expected']=='string' and d['actual']==['relation'] for d in result['issues'])
    assert any(d['expected']=='unique symbol name' for d in result['issues'])


def test_ambiguous_duplicate_declarations_do_not_supply_a_guessed_type():
    raw='{"bindings":[{"name":"x","type":"integer","value":1},{"name":"x","type":"scalar","value":"text"}],"nodes":[{"name":"n","kind":"expression","body":{"op":"pair","args":[{"var":"x"},1]}}],"query":'
    result=incomplete_feedback(raw)
    assert result['issues'] and all(d['expected']=='unique symbol name' for d in result['issues'])


def test_only_a_valid_complete_expression_node_supplies_a_later_type():
    raw='{"bindings":[{"name":"x","type":"integer","value":1}],"nodes":[{"name":"v","kind":"expression","body":{"op":"array","args":[{"var":"x"}]}},{"name":"n","kind":"expression","body":{"op":"pair","args":[{"var":"v"},1]}}],"query":'
    result=incomplete_feedback(raw)
    assert any(d['expected']=='string' and d['actual']==['numbers'] for d in result['issues'])
