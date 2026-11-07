"""Source coverage and primitive evidence, using invented offline inputs."""
import pytest

from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues
from legal_skill_guard.rr.coverage import Unsupported,complete,plan_batch,certificate
from legal_skill_guard.rr.source_program import (
    accept_observations,compile_source,compiler_prompt,program_schema,source_theory)


def case(extra_rule=False):
    source={'key':'RuleArena_Airline:offline_fixture','dataset':'RuleArena_Airline','public':{
        'rules':'Fragile parcels cost 7 each.'+('\nAn unknown exception changes the fee.' if extra_rule else ''),
        'prompt':'Alice carries 2 parcels. The parcels are fragile.'}}
    fact='s2' if extra_rule else 's1'
    program={'rule_residuals':[],'bindings':[{'name':'n_count','type':'integer','value':2,'sources':[fact]}],
        'observations':[{'name':'b_fragile','entity':'parcels','entity_source':fact,
                         'predicate':'Fragile','predicate_source':'s0'}],
        'nodes':[],'scopes':[],
        'clauses':[{'name':'fee','sources':['s0'],'value':{'op':'if','args':[
            {'var':'b_fragile'},{'op':'scale','args':[7,{'var':'n_count'}]},0]},'otherwise':0}],
        'query':{'var':'fee'}}
    return source,program


def test_real_contract_can_declare_factual_condition_without_literal_true():
    source,program=case();compiled=compile_source(source,program)
    before=complete(source_theory(compiled))
    assert before.status=='translation_unresolved' and sorted(w.answer for w in before.worlds)==[0,14]
    plan=plan_batch(source_theory(compiled),lambda units:len(units)*10,100)
    assert plan.status=='separation_complete' and plan.selected==('s1',)
    observation=accept_observations(compiled,['b_fragile'],{'observations':[
        {'name':'b_fragile','value':True,'evidence':'The parcels are fragile.'}]})
    theory=source_theory(compiled,observation);result=complete(theory)
    proof=certificate(theory,result)
    assert result.answer==14 and proof['natural_language_faithfulness_proven'] is False


def test_an_untranslated_whole_rule_stays_unknown_scope():
    source,program=case(True);compiled=compile_source(source,program)
    theory=source_theory(compiled,{'b_fragile':True})
    assert any(r.source=='s1' and r.unknown_scope for r in theory.residuals)
    assert complete(theory).status=='translation_unresolved'


def test_quoting_a_rule_number_alone_does_not_translate_the_rule():
    source,program=case()
    program['bindings'].append({'name':'fee_literal','type':'integer','value':7,'sources':['s0']})
    program['clauses'][0]['sources']=[]
    theory=source_theory(compile_source(source,program))
    assert any(r.source=='s0' and r.unknown_scope for r in theory.residuals)


@pytest.mark.parametrize('change',['no_evidence','invented_evidence','absent_as_false','duplicate','missing'])
def test_observations_cannot_synthesize_evidence_or_drop_rows(change):
    source,program=case();compiled=compile_source(source,program)
    row={'name':'b_fragile','value':True,'evidence':'The parcels are fragile.'}
    rows=[row]
    if change=='no_evidence':row['evidence']=''
    if change=='invented_evidence':row['evidence']='Alice is exempt.'
    if change=='absent_as_false':row.update(value=False,evidence='')
    if change=='duplicate':rows.append(dict(row))
    if change=='missing':rows=[]
    with pytest.raises(Unsupported):accept_observations(compiled,['b_fragile'],{'observations':rows})


def test_unknown_observation_retains_both_values():
    source,program=case();compiled=compile_source(source,program)
    values=accept_observations(compiled,['b_fragile'],{'observations':[
        {'name':'b_fragile','value':None,'evidence':''}]})
    theory=source_theory(compiled,values)
    assert theory.domains=={'b_fragile':(False,True)}
    assert complete(theory).status=='translation_unresolved'


def test_native_answer_literal_is_not_an_executable_method():
    source,program=case();program['query']=14
    with pytest.raises(Unsupported,match='Native answer'):compile_source(source,program)


def test_derived_boolean_cannot_enter_literal_binding_path():
    from jsonschema import ValidationError
    source,program=case()
    program['bindings'].append({'name':'b_invented','type':'scalar','value':True,'sources':['s1']})
    with pytest.raises(ValidationError):compile_source(source,program)


def test_current_schema_and_prompt_are_strict_and_have_no_native_answer_field():
    source,_=case()
    schema=program_schema(source)
    assert strict_output_schema_issues(schema)==[]
    assert 'answer' not in schema['properties']
    system,user=compiler_prompt(source)
    assert 'You do not provide their truth values' in system
    assert source['public']['prompt'] in user


def test_legal_subexpression_residual_is_not_a_factual_observation():
    source,program=case()
    source['public']['rules']+='\nA deduction is allowed if an external section permits it.'
    # Adding a rule line moves only the original factual source unit.
    program['bindings'][0]['sources']=['s2']
    program['observations'][0]['entity_source']='s2'
    program['rule_residuals']=[{'name':'b_external','source':'s1','quote':'an external section permits it'}]
    program['clauses'].append({'name':'deduction','sources':['s1'],
        'value':{'op':'if','args':[{'var':'b_external'},1,0]},'otherwise':0})
    compiled=compile_source(source,program)
    theory=source_theory(compiled,{'b_fragile':True});result=complete(theory)
    assert result.status=='completion_stable' and result.answer==14
    assert theory.domains['b_external']==(False,True)
    with pytest.raises(Unsupported):accept_observations(compiled,['b_external'],{})
    with pytest.raises(Unsupported):source_theory(compiled,{'b_external':True})
    program['query']={'var':'deduction'}
    compiled=compile_source(source,program)
    assert complete(source_theory(compiled,{'b_fragile':True})).status=='translation_unresolved'


def test_whole_rule_or_free_footprint_cannot_be_replaced_by_one_hole():
    source,program=case()
    program['rule_residuals']=[{'name':'b_external','source':'s0','quote':source['public']['rules']}]
    with pytest.raises(Unsupported,match='whole untranslated'):compile_source(source,program)
    program['rule_residuals'][0]['quote']='parcels'
    with pytest.raises(Unsupported,match='containing rule'):compile_source(source,program)


def test_real_compiler_failure_is_rejected_by_wire_schema_before_dispatch():
    import json
    from pathlib import Path
    import jsonschema
    from legal_skill_guard.rr.wire_validation import validate_wire
    root=Path(__file__).resolve().parents[1]
    raw=json.loads((root/'tests/fixtures/rr_actual_compiler_program_v2.json').read_text())
    public=json.loads((root/'data/packets/rr_v2/public_train.json').read_text())
    source=next(s for s in public['sources'] if s['key']=='SARA_v2_Binary:743ac2e5258037a15b0e3549f47db2e50d051ec4449a3493120048fee188a814')
    schema=program_schema(source)
    with pytest.raises(jsonschema.ValidationError):validate_wire(raw,schema)
    # Adding an empty residual list preserves all original semantics. The
    # actual observation names still fail the now-explicit wire constraint.
    with pytest.raises(jsonschema.ValidationError,match='b_'):
        validate_wire(raw['observations'],schema['properties']['observations'])


def test_variable_names_cannot_supply_missing_temporal_semantics():
    source,program=case()
    program['observations'].append({**program['observations'][0],'name':'b_fragile_different_year'})
    with pytest.raises(Unsupported,match='variable names'):compile_source(source,program)


def test_private_record_keys_do_not_relax_native_output_or_value_grounding():
    source,program=case()
    private={'name':'private','kind':'expression',
        'body':{'op':'object','args':[{'op':'pair','args':['private_schema_key',{'var':'n_count'}]}]}}
    program['nodes'].append(private)
    compiled=compile_source(source,program)
    assert any(c.get('internal_noninterfering_record_symbols') for c in compiled['grounding'])
    original=program['clauses'][0]['value']
    program['clauses'][0]['value']={'var':'private'}
    with pytest.raises(Unsupported,match='literal grounding'):compile_source(source,program)
    program['clauses'][0]['value']=original
    private['body']['args'][0]['args'][1]='invented_legal_fact'
    with pytest.raises(Unsupported,match='literal grounding'):compile_source(source,program)


def test_actual_second_response_cannot_supply_missing_executable_scope_ownership():
    import json
    from pathlib import Path
    from legal_skill_guard.rr.coverage import digest
    root=Path(__file__).resolve().parents[1]
    raw=json.loads((root/'tests/fixtures/rr_actual_compiler_program_v3.json').read_text())
    original=digest(raw)
    public=json.loads((root/'data/packets/rr_v2/public_train.json').read_text())
    source=next(s for s in public['sources'] if s['key']=='SARA_v2_Binary:743ac2e5258037a15b0e3549f47db2e50d051ec4449a3493120048fee188a814')
    import jsonschema
    with pytest.raises(jsonschema.ValidationError):compile_source(source,raw)
    assert digest(raw)==original


def test_format_example_is_executable_but_is_not_benchmark_evidence():
    from legal_skill_guard.rr.source_format import FORMAT_EXAMPLE
    from copy import deepcopy
    source={'key':'SARA_v2_Binary:invented_format_only','dataset':'SARA_v2_Binary','public':deepcopy(FORMAT_EXAMPLE['public'])}
    compiled=compile_source(source,deepcopy(FORMAT_EXAMPLE['program']))
    assert complete(source_theory(compiled)).status=='translation_unresolved'
    assert compiled['scope_bindings'][0]['enforced_scopes']==['scope_plan','scope_title']
