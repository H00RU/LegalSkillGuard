import pytest

from experiments.convergence_revision5_cni_retention_controls import absence_applies


@pytest.mark.parametrize(
    "text",
    [
        "The Directors shall not disclose the existence of this Agreement.",
        "The parties shall make no press release about their commercial plans.",
        "The nature of the arrangement shall not be revealed to any third party.",
        "The Advisor undertakes:\n(a) to hold the material in confidence.\n(b) not to discuss the arrangement.",
        "Prior written consent is necessary to make a public statement.",
    ],
)
def test_possible_event_restriction_keeps_original_prediction(text):
    assert not absence_applies({"public": {"source_text": text}})


@pytest.mark.parametrize(
    "text",
    [
        "The Recipient shall use the Confidential Information only for due diligence.",
        "The Recipient must return all copies within ten days of request.",
        "No license to any patent is granted by this Agreement.",
    ],
)
def test_unrelated_use_copy_and_license_terms_do_not_protect_an_event_claim(text):
    assert absence_applies({"public": {"source_text": text}})


def test_agreement_itself_named_as_the_confidential_object():
    view = {"public": {"source_text": "This Agreement and each later instrument between the parties "
                      "shall be kept confidential and is not to be distributed."}}
    assert absence_applies(view)
    assert not absence_applies(view, protect_agreement_itself=True)


def test_generic_information_does_not_activate_agreement_subject_guard():
    view = {"public": {"source_text": "The Recipient shall keep the received information confidential. "
                      "The laws of Delaware govern this Agreement."}}
    assert absence_applies(view, protect_agreement_itself=True)
