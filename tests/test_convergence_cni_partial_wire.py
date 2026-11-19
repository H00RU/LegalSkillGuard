import json

from jsonschema import ValidationError
import pytest

from experiments.convergence_revision5_cni_partial_wire import completed_members, recover
from legal_skill_guard.skill_evolution.native import answer_wire_schema, record_schema


NATIVE_RECORD = '{"answer":"Entailment","evidence_sentence_ids":[0]}'
LEAD = '{"value":{"nda-4":' + NATIVE_RECORD


@pytest.mark.parametrize("tail", ["", " ,", ', "nda-', ', "nda-15"', ', "nda-15":',
                                  ', "nda-15": {', ', "nda-15": {"answer":"Entailment"'])
def test_preserves_only_complete_records(tail):
    assert completed_members(LEAD + tail, {"nda-4", "nda-15"}) == {
        "nda-4": json.loads(NATIVE_RECORD)
    }


@pytest.mark.parametrize("tail", [', "nda-4":', ', "unknown":', ',}}', "} garbage"])
def test_ambiguous_members_are_rejected(tail):
    with pytest.raises(ValueError):
        completed_members(LEAD + tail, {"nda-4", "nda-15"})


def test_duplicate_nested_keys_are_rejected():
    with pytest.raises(ValueError, match="Duplicate"):
        completed_members('{"value":{"nda-4":{"answer":"x","answer":"y"}', {"nda-4"})


def test_recovery_validates_public_spans_and_preserves_unhandled_tasks():
    views = {
        name: {
            "id": name,
            "answer_schema": {"type": "string", "enum": ["Entailment"]},
            "public": {"sentence_spans": [[0, 1]]},
        }
        for name in ("nda-4", "nda-15")
    }
    schema = record_schema({"value": record_schema({
        name: answer_wire_schema("ContractNLI", view) for name, view in views.items()
    })})
    payload = {"response_format": {"json_schema": {"schema": schema}}}
    missing = {"handled": False, "answer": None, "evidence_sentence_ids": [], "reason": "length"}
    native = dict.fromkeys(views, missing)
    raw = {"finish_reason": "length", "content": LEAD + ","}
    updated = recover(raw, payload, views, native)
    assert updated["nda-4"] == {
        "handled": True, "answer": "Entailment", "evidence_sentence_ids": [0], "reason": None
    }
    assert updated["nda-15"] == missing
    assert recover({**raw, "finish_reason": "stop"}, payload, views, native) == native
    assert not native["nda-4"]["handled"]
    with pytest.raises(ValidationError):
        recover({**raw, "content": LEAD.replace("[0]", "[1]")}, payload, views, native)
