import json
from pathlib import Path

import pytest

from legal_skill_guard.rr.controls import (
    ARMS,
    PredictionBudget,
    SharedMaterial,
    dry_run_matrix,
    project_material,
)
from legal_skill_guard.rr.ledger import DATASETS
from legal_skill_guard.rr.scoring import aggregate, task_score


def test_all_arms_share_acquisition_tools_call_cap_but_activate_different_mechanisms():
    material = SharedMaterial("source", [{"metadata": "same extraction"}], {"answer": True},
                              [{"public": "variant", "label": False}], {"summary": "same"},
                              [{"fields": ["entity_equality"]}])
    outputs = [project_material(material, arm) for arm in ARMS]
    assert len({o["shared_material_hash"] for o in outputs}) == 1
    assert len({str(o["profile"]["tools"]) for o in outputs}) == 1
    assert all(o["profile"]["max_model_calls"] == 3 for o in outputs)
    assert all(o["extra_paid_preparation_calls"] == 0 for o in outputs)
    for name in ("M00", "M10", "MB"):
        assert project_material(material, name)["active_learned_patterns"] == []
    for name in ("M01", "M11", "MA"):
        assert project_material(material, name)["active_learned_patterns"]
    assert project_material(material, "MB")["full_metadata_source"] == "same_model_proposals_only"


@pytest.mark.parametrize("first_two", [("parse", "parse"), ("parse", "repair"), ("repair", "repair")])
def test_three_requests_are_entire_prediction_limit_including_fixed_fallback(first_two):
    budget = PredictionBudget()
    for purpose in first_two:
        budget.reserve(purpose)
    with pytest.raises(RuntimeError, match="reserved"):
        budget.reserve("repair")
    budget.reserve("fallback")
    with pytest.raises(RuntimeError, match="cap"):
        budget.reserve("fallback")


def test_formal_matrix_only_dry_run():
    p = json.loads((Path(__file__).resolve().parents[1] /
                    "reports/legalskillguard_rule_reasoning_protocol_v2.json").read_text())
    result = dry_run_matrix(p)
    assert not result["executed"] and result["model_calls"] == 0
    assert result["shared_training_builds"] == 1
    assert result["dev_outputs_per_arm"] == 48 and result["test_outputs_per_arm"] == 192
    p["run_enabled"] = True
    with pytest.raises(ValueError, match="disabled"):
        dry_run_matrix(p)


def test_task_unknown_and_system_failure_have_different_scoring():
    assert task_score("ProofWriter_OWA_depth5", "Unknown", "Unknown")["correct"]
    assert not task_score("ProofWriter_OWA_depth5", None, "Unknown")["correct"]
    assert not task_score("RuleArena_Airline", True, 1)["valid"]
    assert task_score("ContractNLI", "NotMentioned", "NotMentioned")["correct"]
    assert task_score("SARA_v2_Binary", "Entailment", "Entailment")["correct"]


def test_source_average_then_equal_benchmark_macro_and_failure_denominator():
    records = []
    for dataset in DATASETS:
        views = ["EC", "EV"] if dataset == "OpenExempt" else ["main"]
        for view in views:
            correct = view != "EV"
            records.append({"dataset": dataset, "source": dataset + ":1", "view": view,
                            "correct": correct, "answered": correct,
                            "certificate_status": "completion_stable" if correct else "budget_exhausted"})
    expected = {(r["dataset"], r["source"], r["view"]) for r in records}
    scores = aggregate(records, expected_outputs=expected)
    assert scores["by_dataset"]["OpenExempt"] == .5
    assert scores["five_benchmark_macro"] == .9
    assert scores["outputs"] == 6 and scores["answer_coverage"] == 5 / 6
    with pytest.raises(ValueError, match="dropped"):
        aggregate(records[:-1], expected_outputs=expected)
    records[-1]["certificate_status"] = "completion_stable"
    records[-1]["correct"] = False
    assert aggregate(records, expected_outputs=expected)["stable_but_wrong_rate"] == 1 / 5


def test_oe_native_format_order_and_duplicate_preserving_exact_mapping():
    target = {'lamp': [{'citation':'Rule §1','claim_value':1}, {'citation':'Rule §2','claim_value':2}]}
    reordered = {'lamp': [{'citation':'Rule §2','claim_value':2.0}, {'citation':'Rule §1','claim_value':1.0}]}
    assert task_score('OpenExempt',reordered,target,family='EV')['correct']
    wrong = {'lamp': [{'citation':'Rule §2','claim_value':2}, {'citation':'Rule §1','claim_value':True}]}
    assert not task_score('OpenExempt',wrong,target,family='EV')['valid']
    assert not task_score('OpenExempt',{'lamp':[]},target,family='EV')['correct']
    assert not task_score('OpenExempt',{'lamp':['Rule §1','Rule §1']},{'lamp':['Rule §1']},family='EC')['correct']
    assert not task_score('OpenExempt',{}, {'lamp':[]},family='EC')['correct']
