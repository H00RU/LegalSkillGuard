from experiments.convergence_revision5_cni_compelled_notice import answer, proof
from experiments.convergence_revision5_cni_notice_coverage import guarded, possibly_compelled


def contract(*spans):
    ranges = []
    begin = 0
    for span in spans:
        end = begin+len(span)
        ranges.append([begin,end])
        begin = end+1
    return {'public':{'source_text':'\n'.join(spans),'sentence_spans':ranges}}


def test_notice_follows_only_the_exact_compulsion_reference():
    lead = 'Receiving Party may disclose Confidential Information:'
    contents = (lead, '3.1.1 as required by any order of any court of competent jurisdiction.',
                '3.1.2 to permitted employees.',
                '3.2 Prior to disclosure under Clause 3.1.1, the Receiving Party shall inform the Disclosing Party.')
    linked = proof(contract(*contents))
    assert linked['same_clause'] == [] and linked['linked'] == [[0,1,3]]
    invalid = proof(contract(*contents[:3],contents[3].replace('Clause 3.1.1','Clause 3.1.2')))
    assert invalid['linked'] == [] and invalid['unresolved_notice'] == [3]
    distant_invalid = proof(contract(lead, contents[2], contents[1],
        '3.2 Under Clause 3.1.2, the Receiving Party shall notify the Disclosing Party of the required disclosure.'))
    assert distant_invalid['linked'] == []


def test_linked_notice_and_disclosure_can_be_split_by_empty_indexed_span():
    selected = proof(contract(
        'The Receiving Party is required by applicable law to disclose Confidential Information.',
        '', 'The Receiving Party shall notify the Disclosing Party of the required disclosure.'))
    assert selected['linked'] == [[0,2]]


def test_unauthorized_use_and_notice_to_the_court_are_not_notice_to_discloser():
    selected = proof(contract(
        'The Receiving Party shall notify the Disclosing Party of any unauthorized use.',
        'If required by applicable law to disclose any Confidential Information, the Receiving Party shall notify the court that it was obtained from the Disclosing Party.'))
    assert not (selected['same_clause'] or selected['linked'])
    incumbent = {'answer':'NotMentioned','evidence_sentence_ids':[]}
    assert answer(incumbent,selected,use_links=True) == incumbent


def test_possible_compulsion_does_not_establish_notice_but_blocks_absence():
    view = contract('Information may be disclosed by operation of law, if required.',
                    'The Recipient shall take reasonable protective measures.')
    possible = possibly_compelled(view)
    assert possible
    original = {'answer':'Entailment','evidence_sentence_ids':[2]}
    missing = {'answer':'NotMentioned','evidence_sentence_ids':[]}
    evidence = {'linked':[],'same_clause':[]}
    modes = {'original':original,'linked':missing}
    assert guarded(modes,evidence,possible)['coverage_guarded'] == original
    assert guarded(modes,evidence,False)['coverage_guarded'] == missing
    assert not possibly_compelled(contract('Customer inquiries should be handled with care.',
                                           'This Agreement is governed by applicable law.'))
