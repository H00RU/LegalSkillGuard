"""Small synthetic checks for the new IID stage; no packet or model access."""

import copy

import numpy as np
import pytest

import experiments.openexempt_frozen_eval as frozen
from legal_skill_guard.learning.task_scoped_skills import validate_scoped_bank


def plan():
    cfg = {
        "run_id": "synthetic_plan_only_no_actual_run",
        "evaluation_stage": frozen.SOURCE_DISJOINT_STAGE,
        "protocol": frozen.SOURCE_DISJOINT_PROTOCOL,
        "statistics_plan": frozen.SOURCE_DISJOINT_PROTOCOL,
        "evaluation_role": "sealed_frozen_comparison",
        "final_matrix_frozen": True,
        "no_validation_set": True,
        "benchmark_development_status": "source_disjoint_IID_frozen_bank_confirmation",
        "independent_learning_repetitions": "user_deferred",
        "external_text_adaptation": "trace2skill_text_offline_v1",
        "reference_arm": "empty",
        "execution_contract": "direct_statutory_claims",
        "execution_contract_version": 14,
        "library_token_hard_cap": 4096,
        "input_packet": frozen.SOURCE_DISJOINT_PACKET + "/inputs.json",
        "grading_directory": frozen.SOURCE_DISJOINT_PACKET + "/grading_only",
        "input_packet_sha256": frozen.SOURCE_DISJOINT_PACKET_SHA256,
        "source_cases": 128,
        "training_source_cases": 128,
        "training_batch_source_cases": 16,
        "generation": dict(frozen.FINAL_DECODING),
        "inference_request_workers": 4,
        "inference_dispatch_protocol": frozen.DISPATCH_PROTOCOL,
        "inference_dispatch_policy": "four_workers_one_instance_exact_wire_lock_no_retry",
        "inference_environment": "artifacts/live_8b_environment_phase_dispatch_20261025.json",
        "arms": [],
        "secondary_contrasts": [],
    }
    # Syntax-only synthetic hashes. Provenance loading must still verify bytes.
    for name, (role, backend, source) in frozen.SOURCE_DISJOINT_ARMS.items():
        arm = {"name": name, "role": role, "backend": backend}
        if source is not None:
            arm.update(source_config=source)
            for field in ("source_config_sha256", "source_frozen_sha256", "source_completion_sha256",
                          "source_publication_sha256", "source_terminal_preservation_sha256", "bank_sha256"):
                arm[field] = "0" * 64
        if name == "ACE_common45":
            arm.update(representation_artifact="synthetic-only-not-a-real-bank.json",
                       representation_sha256="0" * 64)
        cfg["arms"].append(arm)
    cfg["primary_contrasts"] = [
        {"name": "vs_" + name, "after": ["native_claim45"], "before": [name]}
        for name in frozen.SOURCE_DISJOINT_ARMS if name != "native_claim45"
    ]
    return cfg


def test_complete_plan_is_checked_without_any_data_read(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Plan syntax must not read TRAIN, TEST, targets or models")
    monkeypatch.setattr(frozen, "read", forbidden)
    frozen.check_source_disjoint_plan(plan())


@pytest.mark.parametrize("mutation", [
    lambda c: c["arms"].pop(),
    lambda c: c["primary_contrasts"].pop(),
    lambda c: c.update(secondary_contrasts=[copy.deepcopy(c["primary_contrasts"][0])]),
    lambda c: c.update(input_packet="data/packets/already-inspected/inputs.json"),
    lambda c: c.update(teacher={"model": "not-permitted"}),
    lambda c: c.update(source_cases=True),
    lambda c: c["generation"].update(seed=145),
    lambda c: c.update(inference_request_workers=1),
    lambda c: c["arms"][1].update(bank_sha256="pending"),
    lambda c: next(a for a in c["arms"] if a["name"] == "whole_bank").update(
        source_config="configs/old-unmatched-control.json"),
    lambda c: c.update(initial_evaluation={"source_config": "old-predictions.json"}),
])
def test_plan_rejects_missing_conditions_renamed_controls_and_old_predictions(mutation, monkeypatch):
    cfg = plan()
    mutation(cfg)
    monkeypatch.setattr(frozen, "read", lambda *a, **k: pytest.fail("No data access before plan rejection"))
    with pytest.raises(ValueError):
        frozen.check_source_disjoint_plan(cfg)


def synthetic_records(cfg):
    main = np.asarray([[.55, .65], [.60, .60], [.65, .55], [.70, .50]])
    differences = np.asarray([[.20, -.10], [-.10, .20], [.00, .10], [.10, -.10]])
    return {arm["name"]: [
        {"source_key": f"synthetic-{i}", "case_id": i + 1, "family": family,
         "score": {"f1": float(main[i, k] - (0 if arm["name"] == "native_claim45"
                                             else differences[i, k]))}}
        for i in range(4) for k, family in enumerate(("EC", "EV"))]
        for arm in cfg["arms"]}


def test_sixteen_endpoint_statistics_use_the_prebound_paired_source_draws():
    cfg = plan()
    cfg["source_cases"] = 4  # Toy statistics, not an executable formal profile.
    records = synthetic_records(cfg)
    result = frozen.paired_source_statistics(cfg, records)
    assert result["bootstrap_seed"] == 2026102792
    assert result["bootstrap_draws"] == 20000
    assert result["primary_family_comparisons"] == 16
    assert result["secondary_family_comparisons"] == 0
    assert len(result["contrasts"]) == 8
    assert result["conditional_on_actual_learned_banks_and_fixed_decoding_not_algorithm_population"]
    assert result["source_disjoint_confirmation_for_actual_frozen_banks"]
    delta = np.asarray([[.20, -.10], [-.10, .20], [.00, .10], [.10, -.10]])
    indices = np.random.Generator(np.random.PCG64(2026102792)).integers(4, size=(20000, 4))
    draws = delta[indices].mean(axis=1)
    ordinary = np.quantile(draws, [.025, .975], axis=0, method="linear")
    adjusted = np.quantile(draws, [.025 / 16, 1 - .025 / 16], axis=0, method="linear")
    for contrast in result["contrasts"].values():
        assert len(contrast["per_learning_repeat"]["after_F1_percent"]) == 1
        assert len(contrast["per_learning_repeat"]["before_F1_percent"]) == 1
        assert len(contrast["per_learning_repeat"]["difference_pp"]) == 1
        for k, family in enumerate(("EC", "EV")):
            endpoint = contrast["endpoints"][family]
            assert endpoint["difference_pp"] == pytest.approx(100 * delta[:, k].mean())
            assert endpoint["conditional_95pct_interval_pp"] == pytest.approx(100 * ordinary[:, k])
            assert endpoint["conditional_Bonferroni_interval_pp"] == pytest.approx(100 * adjusted[:, k])


@pytest.mark.parametrize("mutation", [
    lambda r: r.pop("ACE_common45"),
    lambda r: r["static"].pop(),
    lambda r: r["whole_bank"][0].update(case_id=999),
])
def test_statistics_never_drop_a_condition_or_incomplete_source_pair(mutation):
    cfg = plan()
    cfg["source_cases"] = 4
    records = synthetic_records(cfg)
    mutation(records)
    with pytest.raises(ValueError):
        frozen.paired_source_statistics(cfg, records)


def test_common_ACE_interface_preserves_the_full_native_text_without_a_teacher():
    text = '## Native section\n[keep-1] helpful=2 harmful=1: “quoted” \\ value\n\nuntouched tail\n'
    bank = frozen.ace_common_direct_bank(text)
    validate_scoped_bank(bank)
    assert len(bank) == 1
    assert bank[0]["guidance"]["jurisdiction"] == "ALL"
    assert bank[0]["guidance"]["operators"] == []
    assert bank[0]["guidance"]["by_task"][0]["tasks"] == ["EC", "EV"]
    assert bank[0]["guidance"]["by_task"][0]["procedure"] == text


def continued_plan():
    cfg = plan()
    cfg.update(evaluation_stage=frozen.CONTINUED_SOURCE_DISJOINT_STAGE,
               protocol=frozen.CONTINUED_SOURCE_DISJOINT_PROTOCOL,
               statistics_plan=frozen.CONTINUED_SOURCE_DISJOINT_PROTOCOL)
    original = {a["name"]: a for a in cfg["arms"]}
    cfg["arms"] = []
    for name, (role, backend, source) in frozen.CONTINUED_SOURCE_DISJOINT_ARMS.items():
        arm = copy.deepcopy(original.get(name, original["native_claim45"]))
        arm.update(name=name, role=role, backend=backend)
        if source is not None:
            arm["source_config"] = source
        cfg["arms"].append(arm)
    cfg["primary_contrasts"] = [
        {"name": "vs_" + name, "after": ["task_consolidated45"], "before": [name]}
        for name in frozen.CONTINUED_SOURCE_DISJOINT_ARMS if name != "task_consolidated45"
    ]
    return cfg


def test_continued_complete_plan_is_checked_without_any_data_read(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("The continued plan must not read questions, targets or models")
    monkeypatch.setattr(frozen, "read", forbidden)
    cfg = continued_plan()
    frozen.check_source_disjoint_plan(cfg)
    assert len(cfg["arms"]) == 9
    assert {"whole_bank", "legal_scope"}.isdisjoint(a["name"] for a in cfg["arms"])
    for name in ("native_claim45", "task_consolidated45", "joint_consolidated45"):
        arm = next(a for a in cfg["arms"] if a["name"] == name)
        assert frozen.own_B1_reference(cfg, arm) == "native_claim_own_B1_45"


@pytest.mark.parametrize("mutation", [
    lambda c: c.update(evaluation_stage="unknown_continued_epoch"),
    lambda c: c.update(protocol=frozen.SOURCE_DISJOINT_PROTOCOL),
    lambda c: c["primary_contrasts"][0].update(after=["native_claim45"]),
    lambda c: next(a for a in c["arms"] if a["name"] == "joint_consolidated45").update(
        source_config=frozen.SOURCE_DISJOINT_ARMS["native_claim45"][2]),
    lambda c: c["arms"].pop(),
])
def test_continued_plan_rejects_wrong_epochs_sources_and_primary_targets(mutation, monkeypatch):
    cfg = continued_plan()
    mutation(cfg)
    monkeypatch.setattr(frozen, "read", lambda *a, **k: pytest.fail("No data before rejection"))
    with pytest.raises(ValueError):
        frozen.check_source_disjoint_plan(cfg)


def test_continued_B1_reference_never_uses_a_nonexistent_new_B1():
    cfg = continued_plan()
    arm = next(a for a in cfg["arms"] if a["name"] == "task_consolidated45")
    cfg["arms"] = [a for a in cfg["arms"] if a["role"] != "B1_frozen"]
    with pytest.raises(ValueError):
        frozen.own_B1_reference(cfg, arm)
    cfg = continued_plan()
    cfg["arms"].append(copy.deepcopy(next(a for a in cfg["arms"] if a["role"] == "B1_frozen")))
    with pytest.raises(ValueError):
        frozen.own_B1_reference(cfg, arm)
    with pytest.raises(ValueError):
        frozen.continued_source_snapshot("0" * 64)


def test_continued_sixteen_endpoints_keep_structurally_unchanged_EC_as_zero():
    cfg = continued_plan()
    cfg["source_cases"] = 4
    records = synthetic_records(cfg)
    records["task_consolidated45"], records["native_claim45"] = (
        records["native_claim45"], records["task_consolidated45"])
    for before, after in zip(records["native_claim45"], records["task_consolidated45"]):
        if before["family"] == "EC":
            before["score"] = copy.deepcopy(after["score"])
    result = frozen.paired_source_statistics(cfg, records)
    assert result["evaluation_stage"] == frozen.CONTINUED_SOURCE_DISJOINT_STAGE
    assert result["primary_family_comparisons"] == 16
    assert result["bootstrap_seed"] == 2026102792
    assert result["bootstrap_draws"] == 20000
    contrast = result["contrasts"]["vs_native_claim45"]
    assert contrast["after"] == ["task_consolidated45"]
    assert contrast["endpoints"]["EC"]["difference_pp"] == 0
    assert contrast["endpoints"]["EC"]["source_win_tie_loss"] == [0, 4, 0]
    assert contrast["endpoints"]["EC"]["conditional_Bonferroni_interval_pp"] == [0, 0]
    assert not result["all_primary_adjusted_lower_bounds_positive"]


def test_pooled_complete_claims_use_exact_original_totals_not_the_mean():
    rows = [
        {"case_id": 1, "family": "EC", "score": {
            "full_output_claim_tp": 2, "full_output_claim_fp": 1, "full_output_claim_fn": 3}},
        {"case_id": 2, "family": "EC", "score": {
            "full_output_claim_tp": 3, "full_output_claim_fp": 0, "full_output_claim_fn": 1}},
        {"case_id": 1, "family": "EV", "score": {
            "full_output_claim_tp": 4, "full_output_claim_fp": 2, "full_output_claim_fn": 2}},
    ]
    result = frozen.pooled_complete_claim_metrics(rows)
    assert result["EC"]["tasks"] == 2
    assert result["EC"]["correct_claims"] == 5
    assert result["EC"]["extra_or_incorrect_predictions"] == 1
    assert result["EC"]["missing_or_incorrect_targets"] == 4
    assert result["EC"]["f1"] == pytest.approx(2 / 3)
    assert result["EV"]["f1"] == pytest.approx(2 / 3)


def test_pooled_missing_original_counts_are_NA_without_dropping_failed_cases():
    rows = [
        {"case_id": 1, "family": "EC", "score": {
            "full_output_claim_tp": 2, "full_output_claim_fp": 0, "full_output_claim_fn": 0}},
        {"case_id": 2, "family": "EC", "score": {"f1": 0, "invalid_format": True}},
        {"case_id": 1, "family": "EV", "score": {
            "full_output_claim_tp": 2, "full_output_claim_fp": 0, "full_output_claim_fn": 0}},
    ]
    result = frozen.pooled_complete_claim_metrics(rows)
    assert result["EC"]["available"] is False
    assert result["EC"]["tasks"] == 2
    assert result["EC"]["f1"] is None
    assert result["EC"]["missing_original_count_case_ids"] == [2]
    assert result["EV"]["available"] is True
    assert result["EV"]["f1"] == 1


@pytest.mark.parametrize("count", [True, -1, 1.5, None])
def test_pooled_counts_reject_invented_or_invalid_values(count):
    rows = [{"case_id": 1, "family": "EC", "score": {
        "full_output_claim_tp": count, "full_output_claim_fp": 0, "full_output_claim_fn": 0}}]
    with pytest.raises(ValueError):
        frozen.pooled_complete_claim_metrics(rows)


def test_pooled_zero_counts_do_not_invent_perfect_performance():
    rows = [{"case_id": 1, "family": "EC", "score": {
        "full_output_claim_tp": 0, "full_output_claim_fp": 0, "full_output_claim_fn": 0}}]
    result = frozen.pooled_complete_claim_metrics(rows)
    assert result["EC"]["available"] is False
    assert result["EC"]["f1"] is None
    assert result["EV"]["tasks"] == 0
    assert result["EV"]["f1"] is None

