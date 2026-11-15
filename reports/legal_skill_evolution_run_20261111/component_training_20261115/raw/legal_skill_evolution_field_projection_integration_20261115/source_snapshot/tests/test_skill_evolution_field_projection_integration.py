"""Regressions for actual partial-role failures, not evidence of method gains."""
from copy import deepcopy
import json

from legal_skill_guard.skill_evolution.observation_field_projection import compile_library
from legal_skill_guard.skill_evolution.observation_source_review import review
from legal_skill_guard.skill_evolution.partial_native_proof import execute
from legal_skill_guard.skill_evolution.source_event_binding import bind
from test_skill_evolution_source_event_binding import kernel as real_kernel,part
from test_skill_evolution_partial_native_proof import kernel,binding
from test_skill_evolution_relation_native_integration import library


def scope(event,*predicates):
    return {'family_scans':['service_'],'event_properties':[
        {'event':event,'predicate':p}for p in predicates]}


def test_real_university_missing_employer_returns_source_only_read_demand():
    raw=part(None,'Alice','Johns Hopkins University')
    raw['facts']=[f for f in raw['facts']if f['predicate']!='patient_']
    raw['scope_contract']=scope('fresh_event','agent_')
    value,receipt=bind(real_kernel('250fc5'),raw)
    assert not value['complete']and receipt['binding_demands']==[
        {'source_event':'fresh_event','predicate':'patient_','family':'service_'}]
    assert 'Johns Hopkins'not in json.dumps(receipt)
    raw['facts'].append({'predicate':'patient_','arguments':['fresh_event','Johns Hopkins University']})
    raw['scope_contract']['event_properties'].append({'event':'fresh_event','predicate':'patient_'})
    value,receipt=bind(real_kernel('250fc5'),raw)
    assert value['complete']and not receipt['binding_demands']
    assert receipt['bindings'][0]['native_event']=='services'


def test_one_known_match_cannot_hide_an_unread_competing_source_event():
    raw=part(None,'Alice','Johns Hopkins University')
    raw['facts']+=[{'predicate':'service_','arguments':['other']},
        {'predicate':'agent_','arguments':['other','Alice']}]
    raw['scope_contract']=scope('fresh_event','agent_','patient_')
    raw['scope_contract']['event_properties'].append({'event':'other','predicate':'agent_'})
    value,receipt=bind(real_kernel('250fc5'),raw)
    assert not value['complete']and receipt['binding_demands'][0]['source_event']=='other'
    raw['scope_contract']['event_properties'].append({'event':'other','predicate':'patient_'})
    value,receipt=bind(real_kernel('250fc5'),raw)
    assert value['complete']and not receipt['binding_demands']


def test_correct_single_role_and_date_remain_pending_but_wrong_positives_fail():
    facts=[{'predicate':'service_','arguments':['svc']},{'predicate':'agent_','arguments':['svc','Bob']},
        {'predicate':'start_','arguments':['svc','2017-02-01']}]
    grounded={'bindings':[{'inputs':{'facts':facts,'negative_givens':[]}}]}
    partial=scope('svc','agent_','start_')
    value=review('SARA_v2_Binary:bb6b0bc1',grounded,complete_families=[],scope_contract=partial)
    assert value['failures']==0
    assert any('worker Bob' in c['check']for c in value['pending_checks'])
    assert any('Service period' in c['check']for c in value['pending_checks'])
    facts[1]['arguments'][1]='Alice'
    assert review('SARA_v2_Binary:bb6b0bc1',grounded,complete_families=[],scope_contract=partial)['failures']>0
    facts[1]['arguments'][1]='Bob';facts[2]['arguments'][1]='2018-01-01'
    assert review('SARA_v2_Binary:bb6b0bc1',grounded,complete_families=[],scope_contract=partial)['failures']>0


def test_positive_witness_does_not_close_negative_or_aggregate_scope(tmp_path):
    facts=binding(('service_',['svc']),('agent_',['svc','worker']))
    public={'facts':'worker performs a service, remaining records not read.'}
    k=kernel(tmp_path,'s9001 :- agent_("svc","worker").','s9001')
    positive=execute(k,facts,set(),public,scope_contract=scope('svc'))
    assert positive['answer']=='Entailment'
    assert positive['factual_accesses'][0]['origin']=='observed_positive_fact'
    k=kernel(tmp_path,'s9001 :- \\+ agent_("svc","other").','s9001')
    assert execute(k,facts,set(),public,scope_contract=scope('svc'))['answer']is None
    k=kernel(tmp_path,'s9001 :- findall(X,agent_("svc",X),Xs),length(Xs,1).','s9001')
    assert execute(k,facts,set(),public,scope_contract=scope('svc'))['answer']is None
    assert execute(k,facts,set(),public,scope_contract=scope('svc','agent_'))['answer']=='Entailment'


def test_projection_keeps_calendar_pairs_and_acquired_source_programs():
    original=library();contract=original['components'][0]['relation_contract']
    group=next(g for g in contract['relations']if g['name']=='kinship_roles')
    group['fields']+=[{'name':'start','type':'string','normalizer':'literal_date'},
        {'name':'end','type':'string','normalizer':'literal_date'}]
    for rule in contract['rules']:
        for atom in rule['body']:
            if atom['predicate']=='kinship_roles':atom['arguments']+=[{'var':'Start'},{'var':'End'}]
    projected,receipts=compile_library(original)
    groups=projected['components'][0]['relation_contract']['relations']
    assert any({f['name']for f in g['fields']}=={'key','start','end'}for g in groups)
    assert original['components'][0]['relation_contract']==contract
    original['components'][0]['relation_contract']['read_constraint_program']='acquired program'
    preserved,receipt=compile_library(original)
    assert preserved==original and receipt[0]['changed']is False


def test_current_native_entry_routes_missing_binding_role_before_retrying(tmp_path):
    from legal_skill_guard.skill_evolution.native_observation_execution import run
    from legal_skill_guard.skill_evolution.native import record_schema
    from legal_skill_guard.skill_evolution.relational_observation_contract import schema
    k=kernel(tmp_path,'s3306_c_10_A(Service,Employer,Employee,Workday) :- agent_(Service,Employee),patient_(Service,Employer).','s3306_c_10_A')
    (tmp_path/'section9001.pl').rename(tmp_path/'section3306.pl')
    k['statute_sha256']['section3306.pl']=k['statute_sha256'].pop('section9001.pl')
    k['native_query']=[{'predicate':'s3306_c_10_A','arguments':['services','employer','worker','2017-01-01']}]
    k['input_fields_json']=json.dumps({'facts':{'type':'array'},'negative_givens':{'type':'array'},'extraction_status':{'type':'string'}})
    def v(name):return {'var':name}
    fields=[{'name':n,'type':'string','copy':n!='key'}for n in ('key','worker','employer')]
    atom={'predicate':'roles','arguments':[v('K'),v('W'),v('P')],'sign':'positive'}
    c={'key_domain':'service','enumerator':'roles','constants':[],
        'relations':[{'name':'roles','key':'key','fields':fields,'prompt':'Read the source service roles.'}],
        'covered_families':['service_'],'covered_properties':['agent_','patient_'],
        'rules':[{'id':p,'cost':1,'head':{'predicate':p,'arguments':args,'sign':'positive'},'body':[deepcopy(atom)]}
            for p,args in [('service_',[v('K')]),('agent_',[v('K'),v('W')]),('patient_',[v('K'),v('P')])]]}
    shape=schema(c);shape['required']=[]
    lib={'shared_helpers':'','components':[{'id':'services','meaning':'source roles','prompt':'read',
        'relation_contract':c,'complete_native_families':[],
        'schema_json':json.dumps(record_schema({'views':{'type':'array','minItems':1,'items':shape}}))}]}
    public={'facts':'worker provides services to employer.'};calls=[]
    def read_group(component,name,prior):
        assert 'DesiredPerson'not in json.dumps(prior)
        calls.append(name);g=next(g for g in component['relation_contract']['relations']if g['name']==name)
        row={f['name']:('r0'if f['name']=='key'else f['name'])for f in g['fields']}
        return {name:{'status':'complete','records':[row],
            'witnesses':[{'field':'facts','quote':public['facts']}]}},{'offline_fixture':True}
    def no_legacy(_):raise AssertionError('No legacy provider required')
    result=run(lib,k,public,'fixture',no_legacy,read_relation=read_group,project_fields=True)
    assert result['execution']['answer']=='Entailment'and calls==['roles__worker','roles__employer']
    assert any(h['binding_demands'].get('services')for h in result['native_scope_history'])
