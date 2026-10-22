"""Small durable scheduling/boundary contracts, without model or TEST access."""

import copy
import json

import pytest

import experiments.openexempt_fixed_train_control as control
from experiments.openexempt_online import Online
from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.learning.experiment import Comparison


def score(value):
    return {"precision": value, "recall": value, "f1": value, "exact_target": False,
            "invalid_format": 0, "officially_unscored_predicted_claims": 0,
            "full_output_f1": value, "negative_target_asset_predicted_claims": 0}


def fixture_control(tmp_path, monkeypatch):
    monkeypatch.setattr(control, "ROOT", tmp_path)
    study = control.FixedTrainControl.__new__(control.FixedTrainControl)
    study.rows = [{"case_id": i, "family": f, "batch": (i - 181) // 16 + 1}
                  for i in range(181, 309) for f in ("EC", "EV")]
    study.bank = [{"id": "synthetic_fixed_text"}]
    study.bank_hash = control.csha(study.bank)
    study.reference = {"run_id": "synthetic_reference"}
    study.out = tmp_path / "control"
    study.out.mkdir()
    study.teachers, study.teacher_attempts, study.summaries = [], 0, []
    calls = []
    for batch in range(1, 9):
        rows = [r for r in study.rows if r["batch"] == batch]
        RunStore.immutable_json(tmp_path / "runs/synthetic_reference/batches" /
                                f"b{batch}_prequential_records.json", {
            "skills": [{**r, "score": score(0.5)} for r in rows],
            "empty": [{**r, "score": score(0.25)} for r in rows]})

    def answer(row, bank, stage, arm):
        assert control.csha(bank) == study.bank_hash
        calls.append((row["case_id"], row["family"]))
        return {**row, "arm": arm, "stage": stage}

    def grade(records):
        assert len(calls) == len(records) == 256
        saved = json.loads((study.out / "predictions_before_labels.json").read_text())
        assert len(saved) == 256 and all("score" not in r for r in saved)
        files = list((study.out / "batches").glob("b*_predictions.json"))
        assert len(files) == 8
        for path in files:
            assert all("score" not in r for r in json.loads(path.read_text()))
        for record in records:
            record["score"] = score(0.75)

    study.answer, study.grade = answer, grade
    study.progress = lambda *args, **kwargs: None
    return study, calls


def test_complete256_before_grading_and_all_original_source_denominators(tmp_path, monkeypatch):
    study, calls = fixture_control(tmp_path, monkeypatch)
    result = study.execute()
    assert result["status"] == "completed_frozen_static_TRAIN_control"
    assert len(calls) == len(set(calls)) == 256
    assert len(study.summaries) == 8
    for key, n in (("B1_B8", 128), ("B2_B8", 112), ("B3_B8", 96)):
        phase = result["phase_summary"][key]
        assert phase["source_cases"] == n
        assert phase["static"]["EC"]["tasks"] == n
        assert phase["static"]["EV"]["tasks"] == n
        assert phase["static_minus_main"]["mean_f1_difference"] == 0.25
    assert control.csha(study.bank) == study.bank_hash
    assert study.teachers == [] and study.teacher_attempts == 0


def test_mutating_fixed_bank_stops_without_grading_or_rollback(tmp_path, monkeypatch):
    study, calls = fixture_control(tmp_path, monkeypatch)
    original = study.answer

    def mutated(row, bank, stage, arm):
        value = original(row, bank, stage, arm)
        bank.append({"id": "forbidden_update"})
        return value

    study.answer = mutated
    with pytest.raises(ValueError, match="cannot update"):
        study.execute()
    assert len(calls) == 1
    assert not (study.out / "predictions_before_labels.json").exists()


def test_unfinished_predecessor_refused_before_meter_or_run_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr(control, "ROOT", tmp_path)
    cfg = {"run_id": "synthetic_control", "required_completed_predecessors": ["main", "ace"]}
    path = tmp_path / "config.json"
    RunStore.immutable_json(path, cfg)
    RunStore.immutable_json(path.with_suffix(".frozen.json"), {
        "config_sha256": control.sha(path), "files": {}})
    monkeypatch.setattr(control, "validate_profile", lambda cfg: {"run_id": "main"})

    def forbidden_meter(*args, **kwargs):
        raise AssertionError("No model access before actual predecessor completion")

    monkeypatch.setattr(control, "WireClient", forbidden_meter)
    with pytest.raises(ValueError, match="not complete and preserved"):
        control.FixedTrainControl(path)
    assert not (tmp_path / "runs/synthetic_control").exists()


@pytest.mark.parametrize("change", [
    {"teacher": {}}, {"planned_new_teacher_calls": 1}, {"source_cases": 24},
    {"planned_native_calls_max": 512}, {"execution_contract_version": 13},
])
def test_nonfixed_or_teacher_profiles_rejected_before_any_reference_read(change, monkeypatch):
    cfg = {"learner": "frozen_case_free_static_TRAIN_control_v1",
        "execution_contract": "direct_statutory_claims", "execution_contract_version": 14,
        "source_cases": 128, "batch_source_cases": 16, "planned_batches": 8,
        "planned_native_calls_max": 256, "planned_new_teacher_calls": 0, "no_validation_set": True}
    cfg.update(copy.deepcopy(change))
    monkeypatch.setattr(control, "read", lambda *_: pytest.fail("Do not load a packet for a rejected profile"))
    with pytest.raises(ValueError, match="without a teacher"):
        control.validate_profile(cfg)


def test_actor_transport_and_grader_are_original_not_a_new_learning_layer():
    assert control.FixedTrainControl.answer is Online.answer
    assert control.FixedTrainControl.grade is Online.grade
    assert control.FixedTrainControl.call is Comparison.call
    assert not hasattr(control.FixedTrainControl, "teacher_call")
    assert not hasattr(control.FixedTrainControl, "update")
