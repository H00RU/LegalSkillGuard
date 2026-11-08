"""Actual learned-statute reuse; controls are never paid model successes."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from legal_skill_guard.rr.coverage import digest,Unsupported
from jsonschema import ValidationError
from legal_skill_guard.rr.rule_templates import matching_rule_template,instance_request,instantiate_rule_template
from legal_skill_guard.rr.source_program import observation_request
from legal_skill_guard.rr.source_execution import assess_source

ROOT=Path(__file__).resolve().parents[1]

def material():
    library=json.loads((ROOT/'artifacts/rr_method_runtime_20261107/reference_frontend_prior_sara3_template_v8_20261108/library.frozen.json').read_text())['content']
    source=next(s for s in json.loads((ROOT/'data/packets/rr_v2/public_train.json').read_text())['sources']
        if s['key']=='SARA_v2_Binary:250fc5e766b40779976e11126e6d495d8606971c0e3287c28a0400fcc2683362')
    return library,source

def control():
    library,source=material();match=matching_rule_template(source,library)
    value={'entity_bindings':{'Alice':'Johns Hopkins University','Bob':'Alice'},
        'rule_outputs':['enrolled_student_condition'],'combine':'any','negated':False}
    program,compiled,audit=instantiate_rule_template(source,match,value)
    return source,match,value,program,compiled,audit

def test_only_identical_statutes_with_no_old_fact_binding_are_reused():
    library,source=material();match=matching_rule_template(source,library)
    assert match and match['template']['source']['key']!=source['key']
    changed=deepcopy(source);changed['public']['rules']=changed['public']['rules'].replace('$1,000','$1,001')
    changed['content_hash']=digest(changed['public'])
    assert matching_rule_template(changed,library) is None
    with pytest.raises(ValueError,match='own current program'):
        matching_rule_template(library['compiler_templates'][0]['source'],library)

def test_instantiation_changes_only_current_entities_fact_provenance_and_query():
    source,match,value,program,compiled,audit=control()
    for field in ('bindings','nodes','scopes','clauses','rule_residuals'):
        assert program[field]==match['program'][field]
    for before,after in zip(match['program']['observations'],program['observations']):
        assert after['entity']==value['entity_bindings'][before['entity']]
        assert after['predicate']==before['predicate'] and after['predicate_source']==before['predicate_source']
        assert after['entity_source']=='s52'
    result=assess_source(compiled)
    assert result['answer'] is None and result['projection']['active_slots']==['b_enrolled_student','b_school_service']
    assert result['unknown_scope']==[] and audit['old_factual_values_or_answer_reused'] is False
    assert audit['current_executor_authored_full_statute'] is False

@pytest.mark.parametrize('selection',[
    {'rule_outputs':['b_enrolled_student'],'combine':'any','negated':False},
    {'rule_outputs':['domestic_service_exclusion'],'combine':'any','negated':False},
    {'rule_outputs':[],'combine':'any','negated':False},
    {'rule_outputs':['enrolled_student_condition'],'combine':'exec','negated':False},
])
def test_default_bypassed_wrong_section_and_unsafe_queries_are_rejected(selection):
    library,source=material();match=matching_rule_template(source,library)
    value={'entity_bindings':{'Alice':'Johns Hopkins University','Bob':'Alice'},**selection}
    with pytest.raises((Unsupported,ValidationError)):instantiate_rule_template(source,match,value)


def test_absent_current_entities_are_not_filled_from_the_training_case():
    _,match,value,_,_,_=control();library,source=material()
    value['entity_bindings']['Bob']='Bob'
    with pytest.raises((Unsupported,ValidationError)):instantiate_rule_template(source,match,value)

def test_real_enclosing_scope_is_enforced_on_the_nested_student_condition():
    _,_,_,_,compiled,_=control();proof=compiled['derived_context_scopes'][0]
    assert proof['source']=='s44' and proof['new_model_conditions_or_values'] is False
    assert 'enrolled_student_condition' in proof['guarded_descendant_declarations']
    for school in (False,True):
        for student in (False,True):
            values={name:False for name in compiled['query'].input_names}
            values.update(b_school_service=school,b_enrolled_student=student)
            assert compiled['query'].evaluate(values)==('Entailment' if school and student else 'Contradiction')

def test_factual_scope_uses_the_current_public_year_without_a_legal_answer():
    _,_,_,_,compiled,_=control()
    messages,_=observation_request(compiled,['b_enrolled_student'])
    rows=json.loads(messages[1]['content'])
    assert rows[0]['public_reference_years']==[2017]
    assert '3306(c)(10)' not in messages[1]['content'] and 'Entailment' not in messages[1]['content']

def test_compiler_foundation_is_identical_when_only_B_patterns_are_masked():
    library,source=material();masked=deepcopy(library);masked['patterns']=[]
    assert instance_request(source,matching_rule_template(source,library))==instance_request(source,matching_rule_template(source,masked))


def test_actual_failed_instance_predicate_values_are_excluded_by_current_mentions():
    library,source=material();match=matching_rule_template(source,library)
    messages,schema=instance_request(source,match)
    assert schema['properties']['entity_bindings']['properties']['Alice']['enum']==['Alice','Johns Hopkins University']
    stage=ROOT/'artifacts/rr_method_runtime_20261107/reference_instance_sara77_v10_20261108'
    for step in range(2):
        paid=json.loads((stage/'calls'/digest(stage.name+':parse:'+str(step))/'result.json').read_text())
        with pytest.raises(ValidationError):instantiate_rule_template(source,match,json.loads(paid['content']))
    assert json.loads(messages[1]['content'])['training_parameter_roles']=={'Alice':'employer/payer','Bob':'employee performing the services'}
