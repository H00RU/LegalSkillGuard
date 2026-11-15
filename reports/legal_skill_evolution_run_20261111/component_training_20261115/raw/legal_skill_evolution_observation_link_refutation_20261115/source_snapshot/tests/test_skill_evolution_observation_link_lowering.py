import ast

import pytest

from experiments import legal_skill_evolution_observation_link_runtime as runtime
from legal_skill_guard.skill_evolution.case_observation_contract import validate_adapter
from legal_skill_guard.skill_evolution.span_compiler import execute_json


def test_actual_closure_lowering_preserves_each_paid_input_probe_in_worker():
    receipts=runtime.generation.stage.read(runtime.OUT/'offline_lowering_evidence.json')
    assert len(receipts)==4
    for row in receipts:
        program=row['lowered_program']
        if not program:continue
        validate_adapter(program)
        tree=ast.parse(program)
        assert sum(isinstance(n,ast.FunctionDef)for n in ast.walk(tree))==len(tree.body)
        actual=[execute_json(program,probe,{},allow_helpers=True)for probe in row['actual_input_probes']]
        assert actual==row['identical_original_and_lowered_outputs']


def test_actual_learned_medium_and_source_link_are_not_label_defaults():
    receipts=runtime.generation.stage.read(runtime.OUT/'offline_lowering_evidence.json')
    outputs=[]
    for row in receipts:
        if row['arm']=='Method'and row['component']=='source_payment_relations':
            for probe,value in zip(row['actual_input_probes'],row['identical_original_and_lowered_outputs']):
                if 'in hay'not in probe['facts']:continue
                outputs.append((probe['requested_relation'],value))
    medium=next(v for name,v in outputs if name=='payment_terms__medium')
    linked=next(v for name,v in outputs if name=='payment_terms__service_event_id')
    assert medium['domains']==[{'field':'medium','values':['hay']}]
    assert linked['status']=='constrained'and all(v is not None for v in linked['domains'][0]['values'])
    assert medium['witnesses']and linked['witnesses']


def test_pure_float_and_exception_support_does_not_enable_io_or_recursion():
    code='''def apply(inputs,premises):
    try:
        value=float(inputs['amount'])
        return {'integral':value.is_integer()}
    except Exception:
        return {'integral':None}
'''
    assert execute_json(code,{'amount':'2325'},{},allow_helpers=True)=={'integral':True}
    assert execute_json(code,{'amount':'not a number'},{},allow_helpers=True)=={'integral':None}
    with pytest.raises(ValueError):validate_adapter('def apply(inputs,premises):\n    return open(inputs["path"]).read()')
    with pytest.raises(ValueError):validate_adapter('def apply(inputs,premises):\n    return apply(inputs,premises)')
