from experiments.convergence_revision5_cni_agreement_event_attachment import list_duty, source_proof


def view(*sentences):
    start, spans = 0, []
    for s in sentences:
        spans.append((start, start + len(s)))
        start += len(s) + 1
    return {'public': {'source_text': ' '.join(sentences), 'sentence_spans': spans}}


def test_neither_party_bar_resolves_agreement_event():
    family, result = source_proof(view(
        'Neither party shall disclose the discussions that give rise to this Agreement.'), False)
    assert family == 'explicitly_bound_event'
    assert result == {'answer': 'Entailment', 'evidence_sentence_ids': [0]}
    assert source_proof(view('Neither party shall disclose information exchanged during negotiations.'), False)[1] is None
    assert source_proof(view('Neither party shall be required to disclose the existence of this agreement.'), False)[1] is None


def test_list_scope_requires_original_governing_clause():
    lines = ['Auditor affirms that it shall:',
             '(a) not to discuss with the media about the nature of arrangement entered between Auditor and Auditee.']
    assert list_duty(lines, 1) == (0, 1)
    assert list_duty([lines[0], lines[1].replace('(a)', '(b)')], 1) == ()
    assert source_proof(view(*lines), False)[1] is None
    assert source_proof(view(*lines), True)[1]['evidence_sentence_ids'] == [0, 1]


def test_passive_bar_and_separate_duty():
    assert source_proof(view('The existence of this Agreement must not be disclosed.'), False)[1]['answer'] == 'Entailment'
    assert source_proof(view('Neither party shall disclose trade secrets and must disclose the existence '
                             'of this Agreement to the regulator.'), False)[1] is None


def test_transaction_under_consideration_does_not_establish_a_negotiated_agreement():
    possible = view('The recipient will not disclose the fact that a possible transaction is being considered.')
    assert source_proof(possible, False)[0] != 'explicitly_bound_event'
    assert source_proof(possible, True)[0] == 'related_transaction_unconfirmed_scope'
