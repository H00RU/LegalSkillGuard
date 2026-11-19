from experiments.convergence_revision5_cni_definition_binding import (
    NO,
    YES,
    Witness,
    apply_witness,
    source_projection,
    types_in_scope,
)


def test_named_business_category_requires_positive_definition_attachment():
    spans = [
        "WHEREAS the parties have discussed financial information;",
        '"Confidential Information" means all material transmitted in any form other than employee information.',
        "The parties may exchange their financial statements.",
    ]
    assert types_in_scope(spans) == []
    spans[1] = '"Confidential Information" means technical plans and financial information.'
    assert types_in_scope(spans) == [Witness("substance", (1,), (1,), "definition_clause")]


def test_source_list_stays_inside_the_definition():
    spans = [
        "The following are deemed Confidential Information:",
        "• human resources data;",
        "4. The Parties make the warranties specified below.",
        "• business plans;",
    ]
    assert types_in_scope(spans) == [Witness("substance", (0, 1), (1,), "defined_enumeration")]


def test_backward_reference_requires_the_intervening_scope():
    spans = [
        "1. Each party may be provided with access to selected information, including business plans.",
        "Some of the information in each of these categories is confidential in nature.",
        "This information received from a party shall be deemed to be confidential information.",
    ]
    assert types_in_scope(spans) == [Witness("substance", (0, 1, 2), (0,), "category_reference")]
    spans[1] = "Some unrelated transactions are confidential in nature."
    assert types_in_scope(spans) == []


def test_complete_member_and_whole_source_paths_have_distinct_requirements():
    current = {"answer": "NotMentioned", "evidence": []}
    paths = [Witness("substance", (1, 2, 3), (1,), "category_reference")]
    assert apply_witness("substance", current, [1], paths, "cited_complete") == current
    assert apply_witness("substance", current, [2], paths, "cited_member") == current
    resolved = {"answer": NO, "evidence": [1, 2, 3]}
    assert apply_witness("substance", current, [1], paths, "cited_member") == resolved
    assert apply_witness("substance", current, [], paths, "whole_source") == resolved
    assert source_projection("substance") == NO
    assert source_projection("carrier") == YES


def test_shared_head_and_clause_final_assignment_both_bind_a_category():
    spans = [
        "“Confidential Information” includes all business, financial, contractual, "
        "marketing and/or technical information.",
        "Recipient agrees that all information disclosed by the Company relating to business "
        "plans shall be considered Confidential Information.",
    ]
    assert types_in_scope(spans) == [
        Witness("substance", (0,), (0,), "definition_clause"),
        Witness("substance", (1,), (1,), "classifying_assignment"),
    ]


def test_defined_information_uses_the_duty_of_the_same_provider():
    spans = [
        "Information within the meaning of this Agreement shall include commercial information "
        "disclosed by ACME directly or indirectly to the recipient.",
        "The Receiving Party shall treat as strictly confidential any and all information disclosed to it by OTHER.",
        "The Receiving Party shall treat as strictly confidential any and all information disclosed to it by ACME.",
    ]
    assert types_in_scope(spans) == [Witness("substance", (0, 2), (0,), "same_provider_definition")]
    assert types_in_scope(spans[:2]) == []
