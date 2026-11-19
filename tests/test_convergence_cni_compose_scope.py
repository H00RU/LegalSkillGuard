from experiments.convergence_revision5_cni_compose_scope import apply_extensions


def test_signed_scopes_keep_existing_supported_citations_and_use_proven_ids_for_otherwise_missing_evidence():
    native = {
        'first': {'answer': 'Entailment', 'evidence_sentence_ids': [4, 8, 9]},
        'second': {'answer': 'NotMentioned', 'evidence_sentence_ids': []},
        'third': {'answer': 'Contradiction', 'evidence_sentence_ids': [1]},
    }
    scopes = {task: {'label': 'Entailment', 'witnesses': [[3, 4], [8, 9]]}
              for task in ('first', 'second')}
    result = apply_extensions(native, scopes)
    assert result == {**native, 'second': {'answer': 'Entailment', 'evidence_sentence_ids': [3, 4]}}
    assert native['second']['answer'] == 'NotMentioned'


def test_evidence_only_attachment_requires_a_supported_answer_and_continuation():
    native = {
        'yes': {'answer': 'Entailment', 'evidence_sentence_ids': [7]},
        'no': {'answer': 'NotMentioned', 'evidence_sentence_ids': [7]},
    }
    scopes = {task: {'evidence_continuations': {7: (6, 7)}} for task in native}
    result = apply_extensions(native, scopes)
    assert result['yes'] == {'answer': 'Entailment', 'evidence_sentence_ids': [6, 7]}
    assert result['no'] == native['no']
