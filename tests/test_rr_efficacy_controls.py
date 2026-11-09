"""Strong mechanism controls: no model calls, no deliberately damaged baseline."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

from legal_skill_guard.rr.horn import Atom, Rule, closure
from legal_skill_guard.rr.horn_connectors import execute_parsed_with_standard_connectors, execute_parsed_with_library
from legal_skill_guard.rr.source_program import compile_source, source_theory
from legal_skill_guard.rr.source_execution import prepare_followup, assess_source


def test_standard_connectors_preserve_shared_witness_without_any_learned_library():
    parsed=SimpleNamespace(facts={Atom('red',('alice',)),Atom('kind',('bob',))},
        rules=[Rule((Atom('red',('?x',)),Atom('kind',('?x',))),Atom('blue',('?x',)),'s0')],
        query=Atom('blue',('alice',)))
    result=execute_parsed_with_standard_connectors(parsed)
    assert result['answer']=='Unknown' and not result['pattern_uses']
    parsed.facts.add(Atom('kind',('alice',)))
    trace={};result=execute_parsed_with_standard_connectors(parsed,audit=trace)
    assert result['answer']=='True' and Atom('blue',('alice',)) in trace['closure_facts']
    ordinary=closure(parsed.facts,parsed.rules,parsed.query)
    assert ordinary['answer']==result['answer']


def test_standard_connectors_keep_negative_atoms_and_distinct_variables():
    parsed=SimpleNamespace(facts={Atom('red',('alice',),False),Atom('kind',('bob',))},
        rules=[Rule((Atom('red',('?x',),False),Atom('kind',('?y',))),Atom('sees',('?x','?y')),'s0')],
        query=Atom('sees',('alice','bob')))
    assert execute_parsed_with_standard_connectors(parsed)['answer']=='True'
    assert closure(parsed.facts,parsed.rules,parsed.query)['answer']=='True'


def fixture():
    p=Path(__file__).with_name('fixtures')/'rr_scope_v5_binding_projection.json'
    data=json.loads(p.read_text())
    return compile_source(data['source'],data['canonical_program'])


def test_static_dependency_selector_does_not_run_completion_or_drop_scope(monkeypatch):
    import legal_skill_guard.rr.source_execution as execution
    compiled=fixture();theory=source_theory(compiled)
    monkeypatch.setattr(execution,'complete',lambda *a,**kw:(_ for _ in ()).throw(AssertionError('static selector ran a solver')))
    result=prepare_followup(compiled,compilation='static_dependencies',thinking=False,
        tokenize=lambda messages,**kw:{'count':len(json.dumps(messages))},
        request_config={'context_tokens':1000000,'max_tokens':8192})
    assert {r.source for r in theory.residuals if r.unknown_scope}<=set(result['context_closure'])
    assert 'b_legally_separated' in result['names']
    assert not set(result['names'])&set(compiled['rule_residuals'])
    assert result['batch_plan'] is None and not result['joint_separation_complete']


def test_static_policy_uses_same_completion_gate_after_faithful_observation():
    compiled=fixture()
    observed={'b_legally_separated':True}
    a=assess_source(compiled,observed,compilation='answer_separating')
    b=assess_source(compiled,observed,compilation='static_dependencies')
    assert a['answer']==b['answer'] and a['status']==b['status']=='completion_stable'
    assert a['unresolved']==b['unresolved'] and a['unknown_scope']==b['unknown_scope']


def test_atomic_name_enum_is_teacher_strict_and_acceptance_set_is_unchanged():
    import jsonschema
    from legal_skill_guard.rr.source_program import observation_request
    from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues
    _,schema=observation_request(fixture(),['b_legally_separated'])
    assert strict_output_schema_issues(schema)==[]
    old=deepcopy(schema)
    old['properties']['observations']['items']['properties']['name'].pop('type')
    for name in ('b_legally_separated','different',None,1,False,[],{}):
        value={'observations':[{'name':name,'value':None,'evidence':''}]}
        assert jsonschema.Draft202012Validator(schema).is_valid(value)==jsonschema.Draft202012Validator(old).is_valid(value)
