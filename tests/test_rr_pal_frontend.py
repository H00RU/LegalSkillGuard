"""Offline compiler controls, never fresh model or research successes."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from jsonschema import ValidationError

from legal_skill_guard.rr.coverage import Unsupported
from legal_skill_guard.rr.pal_frontend import parse_pal,render_pal,pal_prompt,lower_pal
from legal_skill_guard.rr.source_program import compile_source,source_theory,residual_context_proof
from legal_skill_guard.rr.source_execution import assess_source
from legal_skill_guard.rr.compiler_templates import make_template,validate_template
from legal_skill_guard.rr.learning import SkillLibrary
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.source_validation import validation_feedback
from legal_skill_guard.rr.source_structure import explicit_query_target
from legal_skill_guard.rr.source_structure import inspect_source
from legal_skill_guard.rr.clause_scope import lower_clauses
from legal_skill_guard.rr.scoped_program import compile_query


@pytest.fixture
def control():
    return json.loads((Path(__file__).parent/'fixtures/rr_pal_teacher_control.json').read_text())


def test_paid_teacher_control_roundtrip_preserves_all_semantics(control):
    original = control['program']; restored = parse_pal(render_pal(original))
    assert restored == original
    before = compile_source(control['source'], original)
    after = compile_source(control['source'], restored)
    for observation in ({}, {'b_legally_separated':True}, {'b_legally_separated':False}):
        left = assess_source(before, observation); right = assess_source(after, observation)
        assert (left['status'], left['answer'], left['unknown_scope']) == (right['status'], right['answer'], right['unknown_scope'])


def test_native_literal_and_query_bypass_still_rejected(control):
    for query in ['Entailment', {'var':'b_legally_separated'}]:
        program = deepcopy(control['program']); program['query'] = query
        with pytest.raises(Unsupported):compile_source(control['source'], parse_pal(render_pal(program)))


def test_rule_disabled_value_must_be_model_supplied():
    with pytest.raises(Unsupported, match='explicit otherwise'):
        parse_pal('@rule("s3")\ndef decision():\n    return True\nquery = decision()')


def test_guessed_input_boolean_still_rejected(control):
    program = deepcopy(control['program'])
    program['bindings'].append({'name':'guessed','type':'scalar','sources':['s10'],'value':True})
    with pytest.raises((Unsupported, ValidationError)):
        compile_source(control['source'], parse_pal(render_pal(program)))


def test_missing_legal_unit_remains_unknown(control):
    program = deepcopy(control['program']); program['clauses'] = program['clauses'][1:]
    program['observations'] = [r for r in program['observations'] if r['name']!='b_spouse_dies_during_taxable_year']
    result = assess_source(compile_source(control['source'], parse_pal(render_pal(program))))
    assert 's2' in result['unknown_scope']
    assert result['status'] != 'completion_stable'


def test_unconditional_operative_scope_still_rejected(control):
    program = deepcopy(control['program'])
    program['scopes'].append({'name':'invented_scope','source':'s3','condition':True})
    with pytest.raises(Unsupported, match='structural title'):
        compile_source(control['source'], parse_pal(render_pal(program)))


@pytest.mark.parametrize('code', [
    'import os\nquery = 1',
    'query = __import__("os").system("false")',
    'x = 2017 # s10\nx = 2018 # s11\nquery = x',
    'x = 2017\nquery = x',
    'while True: pass',
])
def test_unsafe_ambiguous_or_missing_evidence_programs_rejected(code):
    with pytest.raises(Unsupported):parse_pal(code)


def test_self_template_rejected_before_dispatch(control):
    with pytest.raises(ValueError, match='current source'):
        pal_prompt(control['source'], {'compiler_examples':[control['example']]})


def test_function_calls_and_comparisons_preserve_meaning(control):
    original = render_pal(control['program'])
    code = original.replace('lt(v_separation_year, v_query_year)',
        '(v_query_year > v_separation_year)').replace('if c_a2_applies else', 'if c_a2_applies() else')
    assert 'c_a2_applies()' in code and '> v_separation_year' in code and code != original
    assert parse_pal(code) == control['program']


def test_full_and_partial_material_persist_but_partial_coverage_is_not_certified(control,tmp_path):
    origin={'role':'teacher','call_id':'offline_control_only','request_hash':'offline_control_only'}
    template=make_template(control['source'],render_pal(control['program']),origin)
    assert validate_template(template)['program']==control['program']
    library=SkillLibrary();library.add_compiler_template(template)
    path=tmp_path/'library.json';library.freeze(path)
    assert SkillLibrary.restore(path).export()==library.export()
    incomplete=deepcopy(control['program']);incomplete['clauses']=incomplete['clauses'][1:]
    partial=make_template(control['source'],render_pal(incomplete),origin)
    checked=validate_template(partial)
    assert assess_source(checked)['status']=='translation_unresolved'
    assert assess_source(checked)['unknown_scope']


def test_actual_pal_scope_failures_have_exact_source_paths_without_repair():
    root=Path(__file__).resolve().parents[1]
    stage=root/'artifacts/rr_method_runtime_20261107/reference_pal_sara79_v1_20261108'
    seal=json.loads((stage/'seal.json').read_text());source=seal['source']
    for step in range(2):
        paid=json.loads((stage/'calls'/digest(stage.name+':parse:'+str(step))/'result.json').read_text())
        program=parse_pal(json.loads(paid['content'])['code']);before=digest(program)
        result=validation_feedback(source,program)
        errors=[i for i in result['issues'] if i['expected'].startswith('executable source condition;')]
        assert errors and all(i['path'].startswith('scopes[') and i['actual']['source_text'] for i in errors)
        with pytest.raises(Unsupported,match='structural title'):compile_source(source,program)
        assert digest(program)==before and not result['candidate_modified']


def test_prompt_and_render_expose_parameter_roles_and_actual_title_ids(control):
    code=render_pal(control['program'])
    assert "observation(entity='Alice', entity_source='s10'" in code
    messages=pal_prompt(control['source'])
    public=json.loads(messages[1]['content'])['CURRENT']
    assert public['structural_title_sources']==['s0','s1','s4']
    assert 's5' not in public['structural_title_sources']


def test_actual_wrong_legal_target_is_diagnosed_without_narrowing_residuals():
    root=Path(__file__).resolve().parents[1]
    stage=root/'artifacts/rr_method_runtime_20261107/reference_pal_sara79_v1_20261108'
    source=json.loads((stage/'seal.json').read_text())['source']
    assert explicit_query_target(source)['unit_ids']==['s37']
    for step in range(2):
        paid=json.loads((stage/'calls'/digest(stage.name+':parse:'+str(step))/'result.json').read_text())
        program=parse_pal(json.loads(paid['content'])['code']);before=digest(program)
        errors=[i for i in validation_feedback(source,program)['issues'] if i['expected'].startswith('root rule dependencies')]
        assert len(errors)==1 and errors[0]['actual']['target']['reference']=='3306(c)(2)'
        assert 's37' not in errors[0]['actual']['reachable_rule_context']
        assert digest(program)==before


def test_real_partial_teacher_task_is_not_reported_as_full_template_or_core():
    root=Path(__file__).resolve().parents[1]
    stage=root/'artifacts/rr_method_runtime_20261107/reference_pal_teacher_sara3_v2_20261108'
    source=json.loads((stage/'seal.json').read_text())['source']
    paid=json.loads((stage/'calls'/digest(stage.name+':compile')/'result.json').read_text())
    program=parse_pal(paid['value']['code']);compiled=compile_source(source,program)
    result=assess_source(compiled)
    assert explicit_query_target(source)['unit_ids']==['s23']
    assert not any(i['expected'].startswith('root rule dependencies') for i in validation_feedback(source,program)['issues'])
    assert result['status']=='translation_unresolved' and len(result['unknown_scope'])==50
    partial=make_template(source,paid['value']['code'],{'role':'teacher','call_id':'offline_control','request_hash':'offline_control'})
    assert assess_source(validate_template(partial))==result


def test_teacher_full_source_task_differs_explicitly_from_executor_request(control):
    ordinary=pal_prompt(control['source']);template=pal_prompt(control['source'],full_template=True)
    assert ordinary!=template and 'FULL-SOURCE TRAIN compiler template' in template[0]['content']
    assert json.loads(ordinary[1]['content'])['CURRENT']['explicit_query_target']['unit_ids']==['s3']


def full_paid_teacher():
    root=Path(__file__).resolve().parents[1]
    stage=root/'artifacts/rr_method_runtime_20261107/reference_pal_teacher_sara3_full_v3_20261108'
    source=json.loads((stage/'seal.json').read_text())['source']
    paid=json.loads((stage/'calls'/digest(stage.name+':compile')/'result.json').read_text())
    return source,paid['value']['code']


def test_actual_full_teacher_normalization_preserves_every_symbolic_execution_and_unknown():
    source,code=full_paid_teacher();raw=parse_pal(code);program,audit=lower_pal(source,code)
    assert len([a for a in audit if 'already_declared_fact_evidence' in a])==26
    moved=[a for a in audit if a.get('kind')=='citation_qualified_predicate_retained_as_legal_unknown']
    assert len(moved)==3 and all(a['domain_before']==a['domain_after']==[False,True] for a in moved)
    assert all(raw[k]==program[k] for k in ('bindings','nodes','scopes','query'))
    assert all(a['value']==b['value'] and a['otherwise']==b['otherwise'] and a['name']==b['name']
        for a,b in zip(raw['clauses'],program['clauses']))
    for prior,actual in zip(raw['clauses'],program['clauses']):
        assert actual['sources']==[u for u in prior['sources'] if u!='s52']
    domains=lambda p:{o['name']:(False,True) for o in p['observations']+p['rule_residuals']}
    assert domains(raw)==domains(program) and len(domains(program))==51
    assert {o['entity_source'] for o in raw['observations']}=={o['entity_source'] for o in program['observations']}
    lowered=lower_clauses(inspect_source(source),program)
    symbolic=compile_query(lowered['nodes'],program['query'],{},domains=domains(raw),boolean_nodes=lowered['scope_names'])
    compiled=compile_source(source,program)
    assert symbolic.__rr_state__()==compiled['query'].__rr_state__()
    result=assess_source(compiled)
    assert result['unknown_scope']==[] and result['status']=='translation_unresolved' and result['answer'] is None
    assert len(compiled['observations'])==30 and len(compiled['rule_residuals'])==21
    assert all(o['name'] not in compiled['observations'] for o in (a['original_observation'] for a in moved))
    canonical=render_pal(program);restored,again=lower_pal(source,canonical)
    assert restored==program and again==[]


def test_whole_list_fragment_needs_actual_enclosing_conditional_AST():
    source,code=full_paid_teacher();program,_=lower_pal(source,code);structure=inspect_source(source)
    hole=next(r for r in program['rule_residuals'] if r['source']=='s46')
    proof=residual_context_proof(structure,program,hole)
    assert proof['parent_source']=='s44' and proof['parent_declaration']=='school_service_exclusion'
    assert proof['residual_domain_unchanged']==[False,True]
    missing=deepcopy(program);missing['clauses']=[c for c in missing['clauses'] if c['name']!='school_service_exclusion']
    assert residual_context_proof(structure,missing,hole) is None
    trivial=deepcopy(program)
    next(c for c in trivial['clauses'] if c['name']=='school_service_exclusion')['value']={'var':hole['name']}
    assert residual_context_proof(structure,trivial,hole) is None
    wrong_parent=deepcopy(program)
    next(c for c in wrong_parent['clauses'] if c['name']=='school_service_exclusion')['sources']=['s42']
    assert residual_context_proof(structure,wrong_parent,hole) is None


def test_annotations_cannot_create_factual_coverage_or_own_queries(control):
    for code in [
        '@rule("s3", "s10", otherwise=False)\ndef result():\n    return False\nquery = result()',
        '@rule("s3", "s11", otherwise=False)\ndef result():\n    return False\nquery = result()',
        '@rule("s10", otherwise=False)\ndef result():\n    return False\nquery = result()',
    ]:
        with pytest.raises(Unsupported):lower_pal(control['source'],code)


def test_qualified_predicates_cannot_hide_a_whole_untranslated_rule_or_a_missing_fact(control):
    source,code=full_paid_teacher();original=parse_pal(code);program,_=lower_pal(source,code)
    observed=next(o for o in original['observations'] if o['name']=='b_domestic_services')
    raw={'bindings':[],'nodes':[],'scopes':[], 'clauses':[{'name':'only_rule','sources':['s23'],
        'value':{'var':observed['name']},'otherwise':False}], 'observations':[deepcopy(observed)],
        'rule_residuals':[], 'query':{'op':'if','args':[{'var':'only_rule'},'Entailment','Contradiction']}}
    # No independent fact witness remains: an observation is never removed
    # merely to make a previously unseen fact disappear from the ledger.
    text=render_pal(raw);normalized,_=lower_pal(source,text)
    assert normalized['observations']==raw['observations']
    with pytest.raises(Unsupported,match='Compile legal effects'):compile_source(source,normalized)
    # Even with an independent fact witness, a whole operative rule cannot
    # become one free Boolean by the qualified-predicate normalization.
    structure=inspect_source(source);clause=next(c for c in structure.ledger.clauses if c.id=='s14')
    raw['observations'][0]['predicate_source']='s14'
    raw['observations'][0]['predicate']=structure.ledger.text[clause.start:clause.end]
    raw['observations'].append(deepcopy(next(o for o in program['observations'] if o['predicate_source']=='s23')))
    normalized,_=lower_pal(source,render_pal(raw))
    assert len(normalized['observations'])==2 and normalized['rule_residuals']==[]
    # The old standalone whole-rule ban also remains in force.
    wrong=deepcopy(control['program']);unit=inspect_source(control['source']).ledger
    s3=next(c for c in unit.clauses if c.id=='s3')
    wrong['rule_residuals'].append({'name':'b_whole_rule','source':'s3','quote':unit.text[s3.start:s3.end]})
    assert residual_context_proof(inspect_source(control['source']),wrong,wrong['rule_residuals'][-1]) is None
