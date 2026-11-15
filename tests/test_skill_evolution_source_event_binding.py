from copy import deepcopy

from experiments import legal_skill_evolution_service_observer_update as acquired
from legal_skill_guard.skill_evolution.source_event_binding import bind
from legal_skill_guard.skill_evolution.observation_scope_normalization import normalize
from legal_skill_guard.skill_evolution.observation_source_review import review


def test_real_public_remuneration_ABI_binds_payment_from_observed_roles_only():
    k = kernel('d5e113')
    before = part('agricultural labor')
    before['facts'] += [
        {'predicate':'payment_', 'arguments':['observed_payment_0']},
        {'predicate':'agent_', 'arguments':['observed_payment_0','Alice']},
        {'predicate':'patient_', 'arguments':['observed_payment_0','Bob']},
        {'predicate':'purpose_', 'arguments':['observed_payment_0','fresh_event']},
    ]
    result, receipt = bind(k, before)
    assert result['complete']
    assert {'source_event':'observed_payment_0','native_event':'paid',
            'basis':'observed_roles','public_query':'s3306_b'} in receipt['bindings']
    assert {'predicate':'payment_', 'arguments':['paid']} in result['facts']
    ambiguous = deepcopy(before)
    ambiguous['facts'] += [
        {'predicate':'payment_', 'arguments':['observed_payment_1']},
        {'predicate':'agent_', 'arguments':['observed_payment_1','Alice']},
        {'predicate':'patient_', 'arguments':['observed_payment_1','Bob']},
    ]
    assert not bind(k, ambiguous)[0]['complete']


def kernel(prefix):
    _,kernels=acquired.data()
    return next(k for s,k in kernels.items()if ':'+prefix in s)


def part(kind='domestic service',worker='Bob',employer='Alice'):
    facts=[{'predicate':p,'arguments':args}for p,args in (
        ('service_',['fresh_event']),('agent_',['fresh_event',worker]),('patient_',['fresh_event',employer]))]
    if kind is not None:facts.append({'predicate':'purpose_','arguments':['fresh_event',kind]})
    return {'facts':facts,'negative_givens':[],'witnesses':[{'field':'facts','quote':'unchanged quote'}],
        'complete':True,'reasons':[]}


def test_kind_only_native_call_renames_only_an_existing_unique_source_event():
    before=part();old=deepcopy(before)
    result,receipt=bind(kernel('bb6b0bc1'),before)
    assert result['complete'] and receipt['bindings'][0]['basis']=='literal_observed_kind'
    assert result['facts'][0]['arguments']==['domestic service']
    assert result['facts'][1]['arguments']==['domestic service','Bob']
    assert result['witnesses']==old['witnesses'] and before==old


def test_ambiguous_or_nonmatching_kind_cannot_be_completed_by_query():
    b=part();b['facts']+=deepcopy(b['facts'])
    for f in b['facts'][4:]:f['arguments']=['other'if a=='fresh_event'else a for a in f['arguments']]
    result,_=bind(kernel('bb6b0bc1'),b)
    assert not result['complete'] and len(result['facts'])==8
    result,_=bind(kernel('bb6b0bc1'),part('agricultural labor'))
    assert not result['complete'] and result['facts'][0]['arguments']==['fresh_event']


def test_role_binding_does_not_copy_query_workday_into_source():
    result,receipt=bind(kernel('250fc5'),part(None,'Alice','Johns Hopkins University'))
    assert result['complete'] and receipt['bindings'][0]['basis']=='observed_roles'
    assert result['facts'][0]['arguments']==['services']
    assert not any(f['predicate']in ('start_','end_')for f in result['facts'])
    bad,_=bind(kernel('250fc5'),part(None,'Bob','Johns Hopkins University'))
    assert not bad['complete']


def test_original_agricultural_payment_query_uses_service_role_positions():
    result,_=bind(kernel('d5e113'),part('agricultural labor'))
    assert result['complete'] and result['facts'][0]['arguments']==['agricultural labor']


def test_unread_source_encoder_is_not_repaired_by_identity_transport():
    b=part();b.update(complete=False,reasons=['source_role_unknown'])
    result,_=bind(kernel('bb6b0bc1'),b)
    assert result==b


def test_exact_date_transport_keeps_witness_and_rejects_conflicting_year():
    library={'components':[{'id':'reading','facts_only':True,'complete_native_families':['service_']}]}
    view={'extraction_status':'complete','period':{'status':'interval','start':'Feb 1st, 2017',
        'end':'Sep 2nd, 2017','year':2017},'witnesses':[{'field':'facts','quote':'Feb 1st, 2017'}]}
    source={'reading':{'views':[view]}}
    value,receipts=normalize(library,None,None,source)
    assert value['reading']['views'][0]['period']=={'status':'interval','start':'2017-02-01','end':'2017-09-02','year':None}
    assert value['reading']['views'][0]['witnesses']==view['witnesses'] and len(receipts)==3
    view['period']['year']=2018
    bad,_=normalize(library,None,None,source)
    assert bad['reading']['views'][0]['period']['year']==2018
    view['period']={'status':'year_only','start':'Feb 2017','end':None,'year':2017}
    assert normalize(library,None,None,source)[0]==source


def test_explicit_home_omission_cannot_make_native_negative_a_source_success():
    b=part();b['facts'] +=[{'predicate':'start_','arguments':['fresh_event','2017-02-01']},
        {'predicate':'end_','arguments':['fresh_event','2017-09-02']}]
    grounded={'bindings':[{'inputs':{'facts':b['facts'],'negative_givens':[]}}]}
    missing=review('SARA_v2_Binary:bb6b0bc1',grounded,complete_families=['service_'])
    assert missing['failures']==1 and not missing['native_answer_used']
    b['facts'].append({'predicate':'location_','arguments':['fresh_event','private home']})
    assert review('SARA_v2_Binary:bb6b0bc1',grounded,complete_families=['service_'])['failures']==0
