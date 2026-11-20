from legal_skill_guard.paired_interfaces import cni_candidate_portfolio as portfolio


def test_screen_falls_back_to_a_source_supported_reader():
    answer = {'answer': 'Entailment', 'evidence_sentence_ids': [3]}
    raw = {'first': {'nda-5': {**answer, 'evidence_sentence_ids': []}},
           'second': {'nda-5': answer}, 'third': {'nda-5': answer}}
    ranked = {'nda-5': ('first', 'second', 'third')}
    lost, recovered, disagreements = portfolio.group_evidence(raw, {'nda-5': answer}, ranked)
    site = {'position': [1, 1], 'losses': lost, 'recoveries': recovered,
            'disagreements': disagreements, 'proof_tasks': ['nda-5']}
    decisions = portfolio.select([site], ranked, physical_group_width=3)
    assert decisions['candidate_driven']['programs'] == {'nda-5': 'second'}
    assert decisions['answer_disagreement']['physical_screen_budget'] == 3
    assert decisions['native_fit_only']['programs'] == {'nda-5': 'first'}


def test_no_reader_is_refuted_when_the_group_supplies_no_matching_output():
    row = {'answer': 'NotMentioned', 'evidence_sentence_ids': []}
    proof = {'answer': 'Entailment', 'evidence_sentence_ids': [2]}
    loss, _, _ = portfolio.group_evidence(
        {role: {'nda-7': row} for role in ('one', 'two')},
        {'nda-7': proof}, {'nda-7': ('one', 'two')},
    )
    assert not loss
