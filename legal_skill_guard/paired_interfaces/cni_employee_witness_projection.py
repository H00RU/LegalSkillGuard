"""Recover a unique employee-access proof from the existing source paths."""

def project(native, verified_paths):
    """Repair absence and misplaced citations when one permission is proved."""
    if len(verified_paths) != 1 or native['answer'] not in ('NotMentioned', 'Entailment'):
        return native
    (operative, evidence), = verified_paths.items()
    if native['answer'] == 'Entailment' and int(operative) in native['evidence_sentence_ids']:
        return native
    return {**native, 'answer': 'Entailment', 'evidence_sentence_ids': evidence}
