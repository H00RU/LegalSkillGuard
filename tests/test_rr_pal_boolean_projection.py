"""The documented Boolean projection must preserve type checks and unknowns."""
import pytest
from legal_skill_guard.rr.coverage import Unsupported
from legal_skill_guard.rr.ir_types import IRTypeError
from legal_skill_guard.rr.pal_frontend import parse_pal
from legal_skill_guard.rr.scoped_program import compile_query


@pytest.mark.parametrize('value',[True,False])
def test_ordinary_boolean_comparison_projects_exact_labels(value):
    p=parse_pal('query = entailment_label(x == True)')
    q=compile_query(p['nodes'],p['query'],{'x':value})
    assert q.evaluate({'x':value})==('Entailment' if value else 'Contradiction')


def test_unknown_boolean_keeps_both_native_outcomes():
    p=parse_pal('query = entailment_label(not unresolved)')
    q=compile_query(p['nodes'],p['query'],{},domains={'unresolved':(False,True)})
    assert {q.evaluate({'unresolved':v}) for v in [False,True]}=={'Entailment','Contradiction'}
    assert q.completion_dependencies()=={'unresolved'}


def test_nonboolean_projection_still_fails_type_check():
    p=parse_pal('query = entailment_label("Entailment")')
    with pytest.raises(IRTypeError) as error:compile_query(p['nodes'],p['query'],{})
    assert error.value.diagnostics[0]['expected']=='boolean'


def test_declared_rule_call_can_be_projected_without_graph_fabrication():
    p=parse_pal('@rule("s1", otherwise=False)\ndef decision():\n    return flag\nquery = entailment_label(decision())')
    assert p['query']=={'op':'if','args':[{'var':'decision'},'Entailment','Contradiction']}
    assert p['nodes']==[] and p['clauses'][0]['value']=={'var':'flag'}


def test_actual_finite_graph_projection_path_preserved():
    p=parse_pal('query = entailment_label(project_exists(rows))')
    assert p['nodes'][0]['kind']=='connector'
    assert p['nodes'][0]['body']['project']=='entailment_label'


def test_arbitrary_calls_not_executed_by_projection():
    with pytest.raises(Unsupported):parse_pal('query = entailment_label(__import__("os"))')
