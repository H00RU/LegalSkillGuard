from experiments.convergence_revision5_cni_disposition_events import N, source_proof
from experiments.convergence_revision5_cni_disposition_roles import administrative_role, revised_proof


def view(*sentences):
    offsets = []
    cursor = 0
    for text in sentences:
        offsets.append((cursor, cursor + len(text)))
        cursor += len(text) + 1
    return {'public': {'source_text': ' '.join(sentences), 'sentence_spans': offsets}}


def test_notice_delivery_does_not_obscure_actual_request_duty():
    notice = 'All notices and related documents shall be in writing and delivered by courier.'
    request = 'Upon written request the Receiving Party shall return all Confidential Information.'
    original = view(notice, request)
    old = source_proof(original)
    assert old['answer'] is None
    new = revised_proof(original, old, use_performative=False)
    assert new['answer'] == N
    assert new['excluded_span_roles'] == {0: 'delivery_of_notice'}
    assert new['source_request_witnesses'] == [(1,)]
    assert administrative_role(notice + ' The Receiving Party shall deliver protected information.') is None


def test_signature_contents_cannot_mask_real_disposition():
    signature = 'The executor shall execute and deliver any documents or legal instruments.'
    original = view(signature)
    assert revised_proof(original, source_proof(original), use_performative=False)['answer'] == N
    original = view(signature, 'Destruction of the confidential material is required at closing.')
    assert revised_proof(original, source_proof(original), use_performative=False)['answer'] is None


def test_request_must_explicitly_require_compliance_and_stand_apart_from_closure():
    original = view('The Disclosing Party may request in writing the return or destruction of Confidential '
                    'Information, and the Receiving Party will promptly comply with such request.')
    old = source_proof(original)
    assert revised_proof(original, old, use_performative=False)['answer'] is None
    assert revised_proof(original, old, use_performative=True)['answer'] == N
    original = view('Upon termination the Disclosing Party may request in writing the return or destruction of '
                    'Confidential Information, and the Receiving Party will promptly comply with such request.')
    assert revised_proof(original, source_proof(original), use_performative=True)['answer'] is None


def test_subsection_title_does_not_create_an_unscoped_duty():
    original = view('2.07 Return of Confidential Information',
                    'Upon written request the Receiving Party shall return all Confidential Information.')
    old = source_proof(original)
    assert old['answer'] is None
    new = revised_proof(original, old, use_performative=False)
    assert new['answer'] == N
    assert new['excluded_span_roles'] == {0: 'disposition_heading'}


def test_approved_removal_custody_does_not_mask_an_independent_return_duty():
    custody = ('Each Party agrees to comply with the conditions the disclosing party imposes upon approved '
               'removal of such items, including that the removed materials or items must be returned by a certain date.')
    assert administrative_role(custody) == 'return_of_item_removed_with_approval'
    assert administrative_role(custody + ' Upon termination the recipient must return all confidential files.') is None
