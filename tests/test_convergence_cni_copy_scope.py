from experiments.convergence_revision5_cni_copy_scope import (
    ABSENT, CONTRADICT, ENTAIL, collect, layouts, matched_direct,
)


def group(number, clause, lead=None):
    return {'clause_id':number,'span_ids':[number] if lead is None else [0, number],
            'source_spans':[clause] if lead is None else [lead,clause],'operative_text':clause}


def test_consumer_eliminates_only_irrelevant_coordinates():
    module, assets = layouts()
    assert len(module.states) == len(assets['fixed']['decoder']) == 27
    assert len(assets['synthesized']['decoder']) == 9


def test_direct_creation_is_distinct_from_handling():
    rows = [group(1, 'Recipient may retain copies of Confidential Information for regulatory compliance.'),
            group(2, 'On termination the Recipient shall return all copies thereof.')]
    assert matched_direct(rows) == {'answer':ABSENT,'evidence_sentence_ids':[]}


def test_direct_use_of_purpose_exception_and_prior_approval():
    bars = [group(2, '(c) Not to make or retain copy of details of products supplied.',
                  'For all Confidential Information, Recipient affirms it shall:'),
            group(3, 'Provider will consider the possibility of granting prior written consent to reproduce information.')]
    assert matched_direct(bars) == {'answer':CONTRADICT,'evidence_sentence_ids':[0,2]}
    permitted = group(4,'Not to reproduce or copy Confidential Information except to the extent necessary to further the Purpose.')
    assert matched_direct([*bars,permitted]) == {'answer':ENTAIL,'evidence_sentence_ids':[4]}


def test_unresolved_permission_is_not_treated_as_absence_or_prohibition():
    rows = [group(2, 'Clause 2'), group(3, 'Clause 3')]
    ports = [{'direct_permission':None,'creation_bar':True}, {'direct_permission':False,'creation_bar':True}]
    assert collect(ports,rows) == {'answer':None, 'evidence_sentence_ids':[]}
