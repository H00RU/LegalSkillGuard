"""Real v4 wrong-arity expressions and precise source-only repair feedback."""
import hashlib
import json
from pathlib import Path

import jsonschema
import pytest

from legal_skill_guard.rr.ir_types import check_expression
from legal_skill_guard.rr.source_program import program_schema
from legal_skill_guard.rr.source_validation import validation_feedback

ROOT=Path(__file__).resolve().parents[1]


def actual():
    fixture=json.loads((ROOT/'tests/fixtures/rr_actual_probe_v4_expressions.json').read_text())
    assert hashlib.sha256(fixture['raw_content'].encode()).hexdigest()==fixture['raw_content_sha256']
    source=next(s for s in json.loads((ROOT/'data/packets/rr_v2/public_train.json').read_text())['sources'] if s['key']==fixture['source'])
    schema=program_schema(source)
    return fixture,source,json.loads(fixture['raw_content']),{'$defs':schema['$defs'],**schema['$defs']['expr']}


def test_actual_bad_clause_arities_are_rejected_without_repairing_the_program():
    fixture,source,program,schema=actual();count=0
    for clause in program['clauses']:
        for field in ('value','otherwise'):
            expr=clause[field]
            if expr.get('op')=='if' and len(expr['args'])!=3:
                jsonschema.Draft202012Validator(fixture['old_expression_schema']).validate(expr)
                with pytest.raises(jsonschema.ValidationError):jsonschema.Draft202012Validator(schema).validate(expr)
                count+=1
    assert count==14
    assert program==json.loads(fixture['raw_content'])


def test_actual_feedback_reports_cells_unbound_names_and_clause_arity_without_labels():
    _,source,program,_=actual();before=json.dumps(program,sort_keys=True)
    feedback=validation_feedback(source,program)
    assert not feedback['candidate_modified'] and not feedback['grading_information_used']
    issues=feedback['issues']
    assert any(i['path']=='bindings[0].value.rows[0][2]' and i['actual']['cell']=='s10' for i in issues)
    assert any(i['path']=='clauses[0].value.args' and i['expected']=='arity 3' and i['actual']==5 for i in issues)
    assert any(i['expected']=='declared IR symbol' for i in issues)
    assert json.dumps(program,sort_keys=True)==before


def test_wire_and_expression_checker_agree_on_supported_operator_shapes():
    _,_,_,schema=actual();validator=jsonschema.Draft202012Validator(schema)
    cases={'if':[True,1,0],'not':[True],'xor':[True,False],'eq':[1,1],'ne':[1,2],
        'lt':[1,2],'le':[1,2],'sub':[2,1],'scale':[2,1],'divide_constant':[2,1],
        'ceil_divide_constant':[2,1],'number_at':[{'op':'array','args':[1]},0],
        'min':[1],'max':[1],'and':[],'or':[],'add':[],'array':[],
        'pair':['key',1],'object':[],'concat':[]}
    # Syntax/type witnesses only; no source-derived prediction is certified.
    for op,args in cases.items():
        expr={'op':op,'args':args};validator.validate(expr);check_expression({'query':expr},{})
    for expr in [{'op':'if','args':[True,1]}, {'op':'not','args':[]},
        {'op':'min','args':[]}, {'op':'divide_constant','args':[1,0]},
        {'op':'scale','args':[{'var':'n_scale'},1]},
        {'op':'number_at','args':[{'op':'array','args':[1]},{'var':'n_index'}]}]:
        with pytest.raises(jsonschema.ValidationError):validator.validate(expr)
