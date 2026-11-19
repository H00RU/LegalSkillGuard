from experiments.convergence_revision5_cni_nonsolicitation import choices, provision


def view(*sentences):
    start, spans = 0, []
    for s in sentences:
        spans.append((start, start + len(s)))
        start += len(s) + 1
    return {'public': {'source_text': '\n'.join(sentences), 'sentence_spans': spans}}


def test_personnel_definition_and_numbered_parent_are_used_by_only_their_child():
    definition = '"Restricted Person" means an employee, director or officer.'
    prohibition = '6.3 Neither party shall, without written consent:'
    sibling = '6.3.1 solicit proxies to vote at a shareholders meeting; or'
    clause = '6.3.2 solicit or employ any Restricted Person of the other Party.'
    proof = provision(view(definition, prohibition, sibling, clause))
    assert proof['direct'] == []
    assert proof['linked'] == [[0, 1, 3]]
    assert proof['votes'] == [2]
    mismatch = provision(view(definition, prohibition, sibling, clause.replace('6.3.2', '6.4.2')))
    assert mismatch['linked'] == []
    assert mismatch['unresolved'] == [3]


def test_literal_and_decoy_provisions_remain_distinct():
    bar = 'Auditor shall not solicit any employee of Auditee without consent.'
    heading = 'Non-solicitation.'
    decoy = 'Neither party shall solicit proxies or votes of shareholders.'
    original = {'answer': 'Entailment', 'evidence_sentence_ids': [0]}
    assert choices(provision(view(heading, bar, decoy)), original)['linked'] == {
        'answer': 'Entailment', 'evidence_sentence_ids': [1],
    }
    assert choices(provision(view(decoy)), original)['linked']['answer'] == 'NotMentioned'
    assert choices(provision(view(heading, decoy)), original)['linked'] == original
