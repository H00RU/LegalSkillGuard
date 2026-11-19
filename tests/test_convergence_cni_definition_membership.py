import json

from experiments.convergence_revision5_cni_definition_membership import (
    ABSENT,
    MEANINGS,
    NO,
    ROLES,
    YES,
    consume,
    decode,
    layouts,
    query,
)
from experiments.convergence_revision5_cni_definition_witness_replay import decode_from_witness


def test_oral_mode_alone_cannot_supply_a_nontechnical_type():
    data = dict.fromkeys(MEANINGS, False)
    data["stated_medium_in_protected_definition"] = True
    data["stated_medium_permits_oral"] = True
    assert consume(data, {}) == {"substance": ABSENT, "carrier": YES}


def test_nontechnical_example_requires_binding_to_the_definition():
    data = dict.fromkeys(MEANINGS, False)
    data["listed_type_is_nontechnical"] = True
    assert consume(data, {})["substance"] == ABSENT
    data["listed_type_in_protected_definition"] = None
    assert consume(data, {})["substance"] is None
    data["listed_type_in_protected_definition"] = True
    assert consume(data, {})["substance"] == NO


def test_compilation_preserves_the_shared_consumer_on_the_declared_domain():
    module, assets = layouts()
    assert len(module.states) == 729
    assert len(assets["fixed"]["features"]) == 6
    assert len(assets["synthesized"]["features"]) == 4


def test_direct_reader_uses_the_same_source_and_requires_real_evidence():
    case = {
        "user": "same bytes",
        "spans": ["Definition of the protected information.", "Oral information."],
    }
    assert {query(case, role)[0][-1]["content"] for role in ROLES} == {"same bytes"}
    raw = {
        "finish_reason": "stop",
        "content": json.dumps(
            {
                "answers": {"substance": NO, "carrier": YES},
                "evidence": {"substance": [], "carrier": [1]},
            }
        ),
    }
    output, error = decode(case, "direct_reader", raw)
    assert error is None
    assert output == {
        "substance": {"answer": None, "evidence": []},
        "carrier": {"answer": YES, "evidence": [1]},
    }


def test_witness_replay_requires_the_binding_and_the_substantive_member():
    case = {"position": [6, 1], "source_review": {"substance": {"answer": NO}}}
    output = {"answer": ABSENT, "evidence": []}
    assert decode_from_witness(case, "substance", output, [21]) == (output, False)
    assert decode_from_witness(case, "substance", output, [18, 21, 22]) == (
        {"answer": NO, "evidence": [18, 21]},
        True,
    )
