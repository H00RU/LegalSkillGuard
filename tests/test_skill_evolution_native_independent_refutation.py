from copy import deepcopy

from test_skill_evolution_partial_native_proof import kernel,binding
from legal_skill_guard.skill_evolution.partial_native_proof import execute
from legal_skill_guard.skill_evolution.sara_statute_kernel import execute as full_execute


def test_known_independent_exception_refutes_without_reading_irrelevant_date(tmp_path):
    k=kernel(tmp_path,'s9001 :- end_("svc",D), \\+ optional_("exception").','s9001')
    facts=binding(('service_',['svc']),('optional_',['exception']))
    result=execute(k,facts,{'optional_'},{'facts':'An actual exception, service date not observed.'})
    assert result['handled']and result['answer']=='Contradiction'
    assert result['proof_mode']=='independent_author_conjunct_refutation'
    assert result['independent_author_refutations']and not result['unread_factual_scopes']
    assert not any(r['predicate']=='end_'for r in result['factual_accesses'])
    # Date completions cannot change the blocking literal. No date is added to
    # the actual observation; completions here check the logical claim only.
    for completion in [[],[('end_',['svc','2017-01-01'])],[('end_',['svc','2018-12-31'])]]:
        closed=binding(('service_',['svc']),('optional_',['exception']),*completion)
        closed['extraction_status']='complete'
        assert full_execute(k,closed)['answer']=='Contradiction'


def test_shared_unbound_variables_prevent_false_global_refutation(tmp_path):
    k=kernel(tmp_path,'s9001 :- end_("svc",D), \\+ optional_(D).','s9001')
    facts=binding(('service_',['svc']),('optional_',['2017-01-01']))
    result=execute(k,facts,{'optional_'},{'facts':'One optional value; service date unknown.'})
    assert not result['handled']and not result['independent_author_refutations']


def test_a_second_viable_author_clause_is_not_discarded(tmp_path):
    k=kernel(tmp_path,'s9001 :- end_("svc",D), \\+ optional_("exception").\ns9001 :- true.','s9001')
    result=execute(k,binding(('optional_',['exception'])),{'optional_'},{'facts':'Known exception.'})
    assert result['answer']!='Contradiction'
    assert not result['independent_author_refutations']


def test_a_negative_inside_disjunction_does_not_refute_the_other_branch(tmp_path):
    k=kernel(tmp_path,'s9001 :- (end_("svc",D), \\+ optional_("exception"); true).','s9001')
    result=execute(k,binding(('optional_',['exception'])),{'optional_'},{'facts':'Known exception.'})
    assert result['answer']!='Contradiction'and not result['independent_author_refutations']


def test_unread_exception_is_a_read_demand_never_a_refutation(tmp_path):
    k=kernel(tmp_path,'s9001 :- end_("svc",D), \\+ optional_("exception").','s9001')
    result=execute(k,binding(),set(),{'facts':'Both date and exception unread.'})
    assert not result['handled']and not result['independent_author_refutations']
    assert any(r['predicate']=='optional_'for r in result['alternative_refutation_demands'])


def test_actual_source_correct_hay_case_uses_author_exception_without_dates():
    from experiments import legal_skill_evolution_observation_link_runtime as previous
    public,kernels=previous.generation.stage.acquired.runtime.previous.data()
    sid=next(s for s in public if ':d5e113'in s)
    row=next(previous.generation.stage.read(p)for p in(previous.OUT/'acquisition/FreeTeacher/Updated').glob('*.json')
        if previous.generation.stage.read(p)['source']==sid)
    world=row['execution']['binding_executions'][0]
    facts=deepcopy(world['inputs'])
    result=execute(kernels[sid],facts,world['complete_families'],public[sid]['views'][0]['public'],
        scope_contract=world['scope_contract'])
    assert result['answer']=='Contradiction'
    assert result['proof_mode']=='independent_author_conjunct_refutation'
    assert any('s3306_b_11' in r['known_blocking_goal']for r in result['independent_author_refutations'])
    assert not any(f['predicate']in ('start_','end_')for f in facts['facts'])
