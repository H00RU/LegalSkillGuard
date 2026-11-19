import pytest

from experiments.convergence_revision5_maud_adoption_scope import received_notice


ANCHOR = (
    '“Knowledge” shall mean those facts that are known by the named individuals, '
    'and in each case shall include any facts, matters or circumstances set forth in '
    'any written notice from any Bank Regulator or any other material written notice received by such Person.'
)


def test_actual_written_notice_requires_the_same_closed_known_facts_definition():
    assert received_notice({"source_text": ANCHOR})


@pytest.mark.parametrize(
    "text",
    [
        ANCHOR.replace("received by", "sent to"),
        ANCHOR.replace("received by", "not received by"),
        ANCHOR.replace("those facts that are known by", "those facts that ought to be known by"),
        ANCHOR.replace("the named individuals,", "the named individuals after reasonable inquiry,"),
        ANCHOR.replace("and in each case", "<omitted> and in each case"),
        ANCHOR.rstrip("."),
        "The Seller shall mean those facts that are known by the listed individuals. " + ANCHOR.replace(
            "those facts that are known by", "those facts identified by"
        ),
    ],
)
def test_non_equivalent_notice_contexts_remain_unresolved(text):
    assert not received_notice({"source_text": text})
