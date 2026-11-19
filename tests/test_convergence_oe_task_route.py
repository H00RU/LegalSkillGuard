from experiments.convergence_revision5_oe_task_route import OPTIONS, conflicts, route, select, source_checked_outputs


def test_task_route_can_preserve_the_incumbent_valuation():
    native = {'incumbent':{'EC':['old_ec'],'EV':['old_ev']}, 'proposal':{'EC':['new_ec'],'EV':['new_ev']}}
    assert route(native,'EC_only') == {'EC':['new_ec'],'EV':['old_ev']}


def test_selection_rejects_only_new_conflicts_and_preserves_entering_ties():
    scores = {mode:{'native_mean_F1':0.4} for mode in OPTIONS}
    source = {mode:frozenset({('old','citation')}) for mode in OPTIONS}
    assert select(scores,source) == 'incumbent'
    scores['EC_only']['native_mean_F1'] = 0.6
    scores['whole_proposal']['native_mean_F1'] = 0.5
    source['EC_only'] |= {('new','citation')}
    assert select(scores) == 'EC_only'
    assert select(scores,source) == 'whole_proposal'


def test_valuation_requires_aligned_title_before_implying_classification():
    native = {'EC':{'item':[]},'EV':{'item':[{'citation':'law','claim_value':100}]}}
    assert list(conflicts(native,{'item':(True,True)})) == [('item','law')]
    assert list(conflicts(native,{'item':(None,True)})) == []
    assert list(conflicts(native,{})) == []


def test_source_check_preserves_old_conflicts_and_rejects_new_ones_locally():
    bank = {'incumbent':{'a':'old a','b':'old b'},'EC_only':{'a':'new a','b':'new b'}}
    findings = {'incumbent':{(1,'asset','citation')},
                'EC_only':{(0,'asset','citation'), (1,'asset','citation')}}
    assert source_checked_outputs(bank,findings,['a','b'],'EC_only') == ({'a':'old a','b':'new b'},[1])
