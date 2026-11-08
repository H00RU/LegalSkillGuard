"""Unknowns stay unknown when a supported Boolean fact decides the query."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from legal_skill_guard.rr.coverage import Unsupported,UnboundIRVariable,evaluate,digest
from legal_skill_guard.rr.scoped_program import compile_query
from legal_skill_guard.rr.source_program import compile_source
from legal_skill_guard.rr.source_execution import assess_source

ROOT=Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('op,known,answer',[('and',False,False),('or',True,True)])
@pytest.mark.parametrize('unknown_first',[False,True])
def test_known_decisive_operand_preserves_missing_boolean_domain(op,known,answer,unknown_first):
    args=[{'var':'unknown'},known] if unknown_first else [known,{'var':'unknown'}]
    inputs={}
    assert evaluate({'op':op,'args':args},inputs) is answer
    assert inputs=={}


@pytest.mark.parametrize('op,neutral',[('and',True),('or',False)])
def test_missing_required_boolean_is_not_given_a_default(op,neutral):
    with pytest.raises(UnboundIRVariable,match='Unbound IR variable'):
        evaluate({'op':op,'args':[{'var':'missing'},neutral]}, {})


@pytest.mark.parametrize('bad',[3,{'op':'unsupported','args':[]}])
def test_decisive_boolean_does_not_hide_nonboolean_or_invalid_operator(bad):
    with pytest.raises(Unsupported):
        evaluate({'op':'and','args':[False,{'var':'missing'},bad]}, {})


def test_deferred_derived_unknown_can_be_read_twice_without_a_false_cycle():
    var=lambda name:{'var':name}
    op=lambda name,*args:{'op':name,'args':list(args)}
    nodes=[{'name':'maybe','kind':'expression','body':op('not',var('unknown'))},
        {'name':'left','kind':'expression','body':op('and',var('maybe'),False)},
        {'name':'right','kind':'expression','body':op('or',var('maybe'),True)}]
    query=compile_query(nodes,op('and',var('left'),var('right')),{},domains={'unknown':(False,True)})
    result=query.execute({},return_environment=True)
    assert result['answer'] is False
    assert result['environment']=={'left':False,'right':True}
    assert result['executed_nodes']==['left','right']


def test_actual_saved_legal_query_executes_the_sparse_state_its_proof_certifies():
    stage=ROOT/'artifacts/rr_method_runtime_20261107/method_runtime_reference_v9_20261109'
    sid='SARA_v2_Binary:be5c71e70a4f8c272f0386786be696054da21713a709f57db5c0b9300976a4f0'
    source=next(s for s in json.loads((ROOT/'data/packets/rr_v2/public_dev.json').read_text())['sources'] if s['key']==sid)
    saved=json.loads((stage/'dev/predictions/M10'/f'{digest(sid)}.json').read_text())['prediction']
    library=json.loads((stage/'build/B8.frozen.json').read_text())['content']
    compiled=compile_source(source,saved['program'],library=library)
    before=deepcopy(compiled['program']);known={'b_within_united_states':False}
    result=assess_source(compiled,known)
    assert result['status']=='completion_stable' and result['answer']=='Contradiction'
    assert 'b_employee_service' in result['unresolved']
    assert result['projection']['inactive_values_resolved'] is False
    execution=compiled['query'].execute(known,return_environment=True)
    assert execution['answer']=='Contradiction'
    assert 'b_employee_service' not in execution['environment']
    assert compiled['program']==before and known=={'b_within_united_states':False}
    assert result['certificate']['natural_language_faithfulness_proven'] is False
