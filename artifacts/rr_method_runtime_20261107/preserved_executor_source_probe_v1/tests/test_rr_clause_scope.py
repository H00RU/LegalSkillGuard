"""Guard ownership and actual original-response regression, no new labels."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from legal_skill_guard.rr.clause_scope import required_scope_sources
from legal_skill_guard.rr.coverage import Unsupported,complete
from legal_skill_guard.rr.source_structure import inspect_source
from legal_skill_guard.rr.source_program import compile_source,source_theory


def case():
    source={'key':'RuleArena_Airline:offline_scope','dataset':'RuleArena_Airline','public':{
        'rules':'# Bag fees\nFor purposes of the fee schedule, if-\n## Ordinary fee\nFee is 7 per parcel.',
        'prompt':'Alice has 2 parcels. Permit true.'}}
    program={'bindings':[{'name':'count','type':'integer','value':2,'sources':['s4']},
        {'name':'permit','type':'scalar','value':True,'sources':['s4']}],
        'observations':[],'rule_residuals':[],'nodes':[],
        'scopes':[{'name':'root','source':'s0','condition':True},
                  {'name':'permit_scope','source':'s1','condition':{'var':'permit'}},
                  {'name':'title','source':'s2','condition':True}],
        'clauses':[{'name':'fee','sources':['s3'],'value':{'op':'scale','args':[7,{'var':'count'}]},'otherwise':0}],
        'query':{'var':'fee'}}
    return source,program


def test_registered_context_automatically_enforces_the_scope():
    source,program=case();compiled=compile_source(source,program)
    assert complete(source_theory(compiled)).answer==14
    assert compiled['scope_bindings'][0]['enforced_scopes']==['permit_scope','root','title']
    source['public']['prompt']=source['public']['prompt'].replace('true','false')
    program['bindings'][1]['value']=False
    assert complete(source_theory(compile_source(source,program))).answer==0


def test_citation_or_unused_metadata_never_discharges_a_missing_scope():
    source,program=case()
    program['scopes']=[s for s in program['scopes'] if s['source']!='s1']
    # An ordinary expression claiming the preface is not an executable scope.
    program['clauses'].append({'name':'quoted','sources':['s1'],'value':{'var':'permit'},'otherwise':False})
    compiled=compile_source(source,program);result=complete(source_theory(compiled))
    assert compiled['missing_scope_sources']==['s1']
    assert result.status=='translation_unresolved' and result.worlds==[]


def test_scope_metadata_cannot_have_string_type():
    source,program=case()
    program['bindings'].append({'name':'policy','type':'scalar','sources':['s1'],'value':'For purposes of the fee schedule'})
    program['scopes'][1]['condition']={'var':'policy'}
    with pytest.raises(Unsupported,match='Boolean'):compile_source(source,program)


@pytest.mark.parametrize('value',[True,False])
def test_an_explicit_if_preface_cannot_be_declared_unconditional(value):
    source,program=case();program['scopes'][1]['condition']=value
    with pytest.raises(Unsupported,match='structural title'):compile_source(source,program)


def test_unknown_scope_expression_is_complete_boolean_residual_not_default():
    source,program=case();program['bindings'].pop()
    program['scopes'][1]['condition']={'var':'b_scope'}
    program['rule_residuals']=[{'name':'b_scope','source':'s1','quote':'purposes of the fee schedule'}]
    compiled=compile_source(source,program);result=complete(source_theory(compiled))
    assert result.status=='translation_unresolved'
    assert sorted(w.answer for w in result.worlds)==[0,14]


def test_native_query_cannot_bypass_a_guard_through_the_raw_local_value():
    source,program=case()
    program['nodes']=[{'name':'raw_fee','kind':'expression','body':deepcopy(program['clauses'][0]['value'])}]
    program['clauses'][0]['value']={'var':'raw_fee'}
    program['query']={'var':'raw_fee'}
    with pytest.raises(Unsupported,match='bypass'):compile_source(source,program)


def test_original_s5_is_registered_as_an_executable_scope_obligation():
    root=Path(__file__).resolve().parents[1]
    public=json.loads((root/'data/packets/rr_v2/public_train.json').read_text())
    source=next(s for s in public['sources'] if s['key']=='SARA_v2_Binary:743ac2e5258037a15b0e3549f47db2e50d051ec4449a3493120048fee188a814')
    assert required_scope_sources(inspect_source(source))==('s5',)
    raw=json.loads((root/'tests/fixtures/rr_actual_compiler_program_v3.json').read_text())
    binding=next(b for b in raw['bindings'] if b['name']=='v_subsection_scope')
    binding={k:v for k,v in binding.items() if k!='source'}|{'sources':[binding['source']]}
    # Exact failing field value/provenance, not a repaired source or label.
    program={'bindings':[binding],'observations':[],'rule_residuals':[],'nodes':[],
        'scopes':[{'name':'scope','source':'s5','condition':{'var':binding['name']}}],
        'clauses':[{'name':'consequence','sources':['s9'],'value':True,'otherwise':False}],
        'query':{'var':'consequence'}}
    with pytest.raises(Unsupported,match='Boolean'):compile_source(source,program)
