"""Real provenance repetition; wire bounds equal the existing engine's domain."""
from copy import deepcopy
import hashlib
from itertools import product
import json
from pathlib import Path
import sqlite3

from jsonschema import ValidationError
import pytest

from legal_skill_guard.rr.clause_scope import lower_clauses
from legal_skill_guard.rr.coverage import Unsupported
from legal_skill_guard.rr.source_program import program_schema
from legal_skill_guard.rr.source_structure import inspect_source
from legal_skill_guard.rr.wire_validation import validate_wire


ROOT=Path(__file__).resolve().parents[1]


def actual():
    raw=json.loads((ROOT/'tests/fixtures/rr_actual_ast_scope_v1.json').read_text())
    source=next(s for s in json.loads((ROOT/'data/packets/rr_v2/public_train.json').read_text())['sources']
                if s['key']==raw['source'])
    return raw,source


def test_actual_incomplete_sources_loop_is_not_completed_and_exceeds_existing_finite_domain():
    raw,source=actual();text=raw['raw_content']
    assert hashlib.sha256(text.encode()).hexdigest()==raw['raw_sha256']
    with pytest.raises(json.JSONDecodeError):json.loads(text)
    schema=program_schema(source)['properties']['clauses']['items']['properties']['sources']
    start=text.rfind('"sources"')
    assert '"clauses"' in text[:start] and text[start:].count('"s1"')>schema['maxItems']
    with pytest.raises(ValidationError):validate_wire(['s1']*(schema['maxItems']+1),schema)


def test_clause_source_wire_is_necessary_for_the_actual_engine_unique_rule_contract():
    _,source=actual();structure=inspect_source(source)
    rules=[key for key,v in structure.roles.items() if v['role']=='rule']
    fact=next(key for key,v in structure.roles.items() if v['role']=='fact')
    field=program_schema(source)['properties']['clauses']['items']['properties']['sources']
    assert field['maxItems']==len(rules)
    for length in range(4):
        for items in product([*rules[:2],fact],repeat=length):
            program={'nodes':[],'scopes':[],'clauses':[{'name':'c_check','sources':list(items),
                'value':True,'otherwise':False}],'query':{'var':'c_check'}}
            try:lower_clauses(structure,program);engine_accepts=True
            except Unsupported:engine_accepts=False
            try:validate_wire(list(items),field);wire_accepts=True
            except ValidationError:wire_accepts=False
            assert not engine_accepts or wire_accepts,(items,engine_accepts,wire_accepts)
            assert engine_accepts==(len(items)==len(set(items)) and set(items)<=set(rules))


def test_binding_evidence_bound_and_unique_match_existing_decoder_requirements():
    _,source=actual();structure=inspect_source(source)
    schema=program_schema(source)
    for option in schema['$defs']['binding']['anyOf']:
        field=option['properties']['sources']
        assert field['minItems']==1 and field['maxItems']==len(structure.ledger.clauses)
    from legal_skill_guard.rr.source_bindings import decode_source_bindings
    units={c.id:structure.ledger.text[c.start:c.end] for c in structure.ledger.clauses}
    with pytest.raises(Unsupported,match='distinct actual source units'):
        decode_source_bindings([{'name':'duplicate_evidence','type':'scalar','value':'Alice','sources':['s1','s1']}],units)


def test_charged_incomplete_AST_supplies_diagnosis_after_a_schema_fix_without_fabricated_IR(tmp_path):
    from experiments.rr_v2_source_probe import executor_candidate
    from legal_skill_guard.rr.compiler_contract import compiler_response_schema
    raw,source=actual();origin='executor_ast_scope_v1_20261107'
    cfg={'compiler_role':'executor','executor':{'enable_thinking':False}}
    path=tmp_path/'artifacts/rr_method_runtime_20261107'/origin;path.mkdir(parents=True)
    (tmp_path/'configs').mkdir();(tmp_path/'configs/rr_v2_preflight.json').write_text(json.dumps({'ledger_path':'book.sqlite3'}))
    old_schema=deepcopy(compiler_response_schema(source))
    old_schema['properties']['clauses']['items']['properties']['sources'].pop('maxItems')
    seal={'run_id':origin,'source':source,'config':cfg,'schema':old_schema,'binding':{'code_hash':'paid-old'}}
    (path/'seal.json').write_text(json.dumps(seal))
    with sqlite3.connect(tmp_path/'book.sqlite3') as db:
        db.execute('create table calls (id,role,purpose,source,status,result)')
        db.execute('insert into calls values (?,?,?,?,?,?)',(raw['call_id'],'executor','method_train_synthesis',
            source['key'],'completed',json.dumps({'content':raw['raw_content'],'request_hash':'paid-request'})))
    _,program,proof=executor_candidate(tmp_path,origin,source,cfg)
    assert program is None and not (path/'program.json').exists()
    assert proof['parse_error']['type']=='JSONDecodeError' and proof['parse_error']['position']>0
    assert proof['diagnosis_only_no_IR_reused'] and proof['new_model_calls']==0
