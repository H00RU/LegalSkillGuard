"""Current canonical AST wire: real paid-program equivalence and strict rejects."""
from copy import deepcopy
import json
from pathlib import Path

from jsonschema import ValidationError
import pytest

from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues
from legal_skill_guard.rr.compiler_contract import (
    compiler_response_schema, decode_compiler_response, encode_compiler_program,
)
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.source_execution import assess_source, prepare_followup
from legal_skill_guard.rr.source_program import compile_source, source_theory


ROOT=Path(__file__).resolve().parents[1]


def actual():
    return json.loads((ROOT/'tests/fixtures/rr_scope_v5_binding_projection.json').read_text())


def test_actual_paid_IR_full_theory_and_A_selection_are_identical():
    case=actual();source=case['source'];original=case['canonical_program']
    wire=encode_compiler_program(original,source)
    assert isinstance(wire['scopes'],dict) and None in wire['scopes'].values()
    assert not strict_output_schema_issues(compiler_response_schema(source))
    restored=decode_compiler_response(wire,source)
    assert restored==original
    before=compile_source(source,original);after=compile_source(source,restored)
    assert digest(source_theory(before,case['observed']))==digest(source_theory(after,case['observed']))
    assert assess_source(before,case['observed'])==assess_source(after,case['observed'])
    request=prepare_followup(after,compilation='answer_separating',tokenize=lambda *a,**k:{'count':100},
        request_config={'context_tokens':32768,'max_tokens':8192},thinking=False)
    assert request['selected']==['s10'] and request['names']==['b_legally_separated']


def test_null_scope_is_absent_and_retains_unknown_scope_in_the_actual_theory():
    case=actual();source=case['source'];original=deepcopy(case['canonical_program'])
    from legal_skill_guard.rr.scoped_program import expression_reads
    removed_reads=set().union(*(expression_reads(row['condition']) for row in original['scopes']))
    original['scopes']=[]
    # Removing a containing AST must also remove its proper-subexpression
    # declarations; otherwise the existing compiler correctly rejects them.
    original['rule_residuals']=[row for row in original['rule_residuals'] if row['name'] not in removed_reads]
    wire=encode_compiler_program(original,source)
    assert all(v is None for v in wire['scopes'].values())
    restored=decode_compiler_response(wire,source);assert restored==original
    before=compile_source(source,original);after=compile_source(source,restored)
    a=assess_source(before,case['observed']);b=assess_source(after,case['observed'])
    assert a==b and b['certificate'] is None and b['unknown_scope']


def test_fixed_rule_keys_cannot_omit_invent_or_use_factual_scope_sources():
    case=actual();source=case['source'];wire=encode_compiler_program(case['canonical_program'],source)
    for bad in ({k:v for k,v in wire['scopes'].items() if k!='s5'},
                {**wire['scopes'],'s10':None},{**wire['scopes'],'invented':None}):
        with pytest.raises(ValidationError):decode_compiler_response({**wire,'scopes':bad},source)
    duplicate=deepcopy(case['canonical_program']);duplicate['scopes']*=2
    with pytest.raises(ValueError,match='One accepted scope'):encode_compiler_program(duplicate,source)


@pytest.mark.parametrize('bad_condition',[
    'True', 'eq(year, 2018)', {'op':'and','args':[{'op':'array','args':[True]}]},
    {'op':'if','args':[True,True]}, {'op':'getitem','args':[{'var':'items'},'value']},
])
def test_expression_text_and_recorded_API_misuses_are_not_in_the_bool_AST_grammar(bad_condition):
    case=actual();wire=encode_compiler_program(case['canonical_program'],case['source'])
    wire['scopes']['s5']['condition']=bad_condition
    with pytest.raises(ValidationError):decode_compiler_response(wire,case['source'])


def test_legacy_array_code_and_side_answers_cannot_enter_the_current_path():
    case=actual();source=case['source'];wire=encode_compiler_program(case['canonical_program'],source)
    for bad in (case['canonical_program'],{'code':'query = True'},{**wire,'answer':'Entailment'}):
        with pytest.raises(ValidationError):decode_compiler_response(bad,source)


def test_actual_B1_graph_reference_and_execution_trace_survive_current_wire():
    from legal_skill_guard.rr.interfaces import Relation
    from legal_skill_guard.rr.scoped_program import compile_query
    library=json.loads((ROOT/'artifacts/rr_v2_formal_build_20261106/run_citation_fix/B1.frozen.json').read_text())['content']
    item=library['patterns'][0]
    source=next(s for s in json.loads((ROOT/'data/packets/rr_v2/public_train.json').read_text())['sources']
        if s['key']=='ProofWriter_OWA_depth5:43ec41194db931b0e509a68dddf476b80e9edb3c5b98cdc6ce889b19314ba096')
    graph={'op':'project_exists','params':{},'inputs':[{'pattern':item['pattern_hash'],'variant':0,
        'slots':{'slot0':'left','slot1':'right'},'columns':{'column0':'person'}}]}
    program={k:[] for k in ('bindings','observations','rule_residuals','nodes','scopes','clauses')}
    program['nodes']=[{'name':'joined','kind':'connector','body':{'graph':graph,'project':'identity'}}]
    program['query']={'var':'joined'}
    restored=decode_compiler_response(encode_compiler_program(program,source),source,library)
    assert restored==program
    for name in ('Dave','Harry'):
        inputs={'left':Relation(('person',),(('Dave',),)),'right':Relation(('person',),((name,),))}
        before=compile_query(program['nodes'],program['query'],inputs,library=library).execute(inputs)
        after=compile_query(restored['nodes'],restored['query'],inputs,library=library).execute(inputs)
        assert before==after and len(after['pattern_uses'])==1
        assert after['pattern_uses'][0]['pattern_hash']==item['pattern_hash']
