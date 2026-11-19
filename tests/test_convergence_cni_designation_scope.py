from experiments import convergence_revision5_cni_designation_scope as marking


def test_copy_and_retention_cues_do_not_establish_original_qualification():
    copy = 'The receiving Party will clearly label all copies of Confidential Information as confidential.'
    retained = 'The Recipient shall identify in writing the specific Confidential Information retained.'
    assert marking.role(copy) == 'copy_or_notice_preservation'
    assert marking.role(retained) == 'retention_or_release'


def test_unresolved_original_conditions_survive_known_copy_or_retention_cues():
    text = ('The Recipient shall identify in writing the specific Confidential Information retained; '
            'the Discloser must separately designate the information at disclosure.')
    assert marking.role(text) == 'potential_qualification'
    text = ('Each copy shall be marked Confidential, and original information shall be '
            'marked by the Discloser at disclosure.')
    assert marking.role(text) == 'potential_qualification'


def test_all_media_proof_requires_an_operative_conjunction_and_no_competing_cue(monkeypatch):
    monkeypatch.setattr(marking.prior, 'direct', lambda _: {'answer': None, 'evidence': []})
    definition = ('“Confidential Information”, whenever used in this Agreement, shall mean any material '
                  'disclosed in any form whatsoever, and that, at the time of disclosure, '
                  'is designated as confidential.')
    monkeypatch.setattr(marking.prior, 'spans_for', lambda _: [definition])
    assert marking.proof({})['answer'] == 'Entailment'
    monkeypatch.setattr(marking.prior, 'spans_for', lambda _: [
        definition, 'Protection applies whether or not it is marked confidential.'])
    assert marking.proof({})['answer'] is None
