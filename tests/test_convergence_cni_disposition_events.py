from experiments.convergence_revision5_cni_disposition_events import (
    attached_end,
    candidate,
    request_link,
)


def test_endpoint_is_bound_to_the_disposition_and_not_to_a_separate_duty():
    linked = ('The Receiving Party must, at the end of this Agreement or upon written request, '
              'return or destroy all Confidential Information.')
    unrelated = ('At the end of this Agreement the duty of confidentiality shall remain in force; '
                 'upon request the Receiving Party shall return all Confidential Information.')
    assert attached_end(linked)
    assert not attached_end(unrelated)
    assert candidate(unrelated)
    assert request_link([unrelated], 0) is None


def test_request_scopes_continuous_numbered_disposition_items():
    spans = ['If the Disclosing Party so requests in writing, the Receiving Party shall immediately:-',
             '5.2.1 return all Confidential Information including copies to the Disclosing Party; and',
             '5.2.2 destroy all copies made by the Receiving Party.']
    assert request_link(spans, 1) == (0, 1)
    assert request_link(spans, 2) == (0, 2)
    spans[1] = '6. This Agreement shall expire on December 31.'
    assert request_link(spans, 2) is None


def test_recognizes_request_possessive_on_same_operative_clause():
    span = ('Recipient agrees to return to the Company immediately upon the Company’s written request '
            'all Confidential Information, including copies.')
    assert candidate(span)
    assert request_link([span], 0) == (0,)


def test_copy_of_agreement_and_postal_receipt_do_not_create_disposal_candidates():
    assert not candidate('Please execute and return one copy of this letter agreement.')
    assert not candidate('Send any documents by Certified Mail, Return Receipt Requested.')
    assert candidate('After mailing a notice by Certified Mail, Return Receipt Requested, '
                     'the Recipient will return all Confidential Information upon request.')
