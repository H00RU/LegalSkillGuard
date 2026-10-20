"""Synthetic protocol checks only; no held-out packet or model service is used."""

import copy
import json
import os
from pathlib import Path

import pytest
from jsonschema import validate

import experiments.openexempt_ace_online as ace
import experiments.openexempt_frozen_eval as frozen
import experiments.openexempt_online as common
import legal_skill_guard.learning.experiment as learning
from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.learning.experiment import INITIAL_PLAYBOOK, read, sha
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha


@pytest.fixture
def plan(tmp_path, monkeypatch):
    project = frozen.ROOT
    actor_files = frozen.SHARED_ACTOR_FILES + frozen.ACE_ACTOR_FILES
    for name in actor_files:
        dest = tmp_path / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.symlink_to(project / name)
    for module in (frozen, common, ace, learning):
        monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("legal_skill_guard.learning.legal_namespace.asset_description_lexicon",
                        lambda: ("watch",))
    monkeypatch.setattr(frozen.signal, "signal", lambda *args: None)
    monkeypatch.setattr(frozen, "preserve", lambda run, stage, names: {
        "files": len(names), "CPU_fixture_only_not_real_preservation": True})
    def put(name, data):
        return RunStore.immutable_json(tmp_path / name, data)

    generation = {"model": "Qwen/Qwen3-8B", "model_root": "/fixture/frozen8b",
                  "context_tokens": 32768, "max_tokens": 8192, "seed": 45}
    put("stats.json", {"fixture_only": True, "paired_unit": "source_case"})
    put("data/train/inputs.json", {"rows": [{"source_key": "TRAIN0"}, {"source_key": "TRAIN1"}]})
    train_sha = sha(tmp_path / "data/train/inputs.json")
    put("data/train/preselection.json", {"source_cases": 2, "source_keys": ["TRAIN0", "TRAIN1"],
                                         "input_packet_sha256": train_sha})
    arms = [{"name": "empty", "role": "strong_empty", "backend": "direct"}]
    for backend in ("direct", "ace"):
        config = {"run_id": "learn_" + backend, "generation": generation,
                  "execution_contract": "direct_statutory_claims", "execution_contract_version": 14,
                  "source_cases": 2, "batch_source_cases": 1, "planned_batches": 2,
                  "input_packet": "data/train/inputs.json"}
        config_name = f"configs/{backend}.json"
        config_path = put(config_name, config)
        bindings = {name: sha(tmp_path / name) for name in actor_files}
        bindings.update({"data/train/inputs.json": train_sha,
                         "data/train/preselection.json": sha(tmp_path / "data/train/preselection.json")})
        put(f"configs/{backend}.frozen.json", {"config_sha256": sha(config_path), "files": bindings})
        bank = [] if backend == "direct" else INITIAL_PLAYBOOK
        field = "bank" if backend == "direct" else "playbook"
        for batch in (1, 2):
            put(f"runs/learn_{backend}/publications/b{batch}.json", {field: bank})
        status = ("completed_bounded_mechanism_study" if backend == "direct" else
                  "completed_declared_ACE_adaptation_stream")
        put(f"runs/learn_{backend}/completion.json", {"status": status,
            "batch_summary": [{"batch": 1}, {"batch": 2}],
            "prequential_skills": {"EC": {"tasks": 2}, "EV": {"tasks": 2}},
            "prequential": {"ace": {"EC": {"tasks": 2}, "EV": {"tasks": 2}}},
            "bank" if backend == "direct" else "final_playbook": bank})
        for role, name in (("evolved", "ours"), ("B1_frozen", "B1")) if backend == "direct" else (
                ("experience", "ACE"),):
            arms.append({"name": name, "role": role, "backend": backend,
                         "source_config": config_name, "source_config_sha256": sha(config_path),
                         "bank_sha256": csha(bank)})
    source = {"case_id": 1000001, "source_key": "TEST", "prompt": "synthetic public prompt",
              "components": {"instruction": "Find all applicable exemptions.",
                "meta_instruction": "Only public law.",
                "statutes": "Ariz. Rev. Stat. § 33-1123\nHousehold property up to $15,000.",
                "solved_steps": "The Debtor may claim property exemptions under Arizona statutes.",
                "facts": "A (hereinafter the Debtor) owns a watch worth $40."}}
    put("data/test/inputs.json", {"rows": [{**source, "family": f} for f in ("EC", "EV")]})
    citation = "Ariz. Rev. Stat. § 33-1123"
    put("data/test/grading_only/1000001.json", {"targets": {
        "EC": {"watch": [citation]}, "EV": {"watch": [{"citation": citation, "claim_value": 40}]}}})
    proc = Path(f"/proc/{os.getpid()}")
    put("env.json", {"pid": os.getpid(),
        "actual_argv": [v.decode() for v in (proc / "cmdline").read_bytes().split(b"\0") if v],
        "process_start_ticks": (proc / "stat").read_text().rsplit(")", 1)[1].split()[19]})
    cfg = {"run_id": "synthetic_frozen", "evaluation_role": "sealed_frozen_comparison",
           "final_matrix_frozen": True, "no_validation_set": True, "generation": generation,
           "execution_contract": "direct_statutory_claims", "execution_contract_version": 14,
           "statistics_plan": "stats.json", "training_source_cases": 2, "training_batch_source_cases": 1,
           "training_packet_sha256": train_sha, "source_cases": 1, "reference_arm": "empty",
           "input_packet": "data/test/inputs.json", "grading_directory": "data/test/grading_only",
           "inference_environment": "env.json", "arms": arms}
    config_path = tmp_path / "configs/evaluation.json"

    def seal():
        RunStore.atomic_json(config_path, cfg)
        names = ["env.json", "data/test/inputs.json", "data/test/grading_only/1000001.json"]
        RunStore.atomic_json(config_path.with_suffix(".frozen.json"), {
            "config_sha256": sha(config_path), "files": {name: sha(tmp_path / name) for name in names}})
        return config_path

    return cfg, seal, tmp_path


def test_frozen_matrix_answers_every_arm_before_any_gold_read_and_reports_real_reuse(plan, monkeypatch):
    cfg, seal, root = plan
    grade_reads, calls = [], []

    def grading_read(path):
        if path.parent.name == "grading_only":
            assert len(list((root / "runs/synthetic_frozen/native").rglob("*.answer.json"))) == 8
            assert (root / "runs/synthetic_frozen/predictions_before_any_grading.json").is_file()
            grade_reads.append(str(path))
        return read(path)

    def call(self, dest, messages, schema, max_tokens, metadata):
        assert not grade_reads
        calls.append(metadata)
        ref = "Ariz. Rev. Stat. section 33-1123"
        value = {"A001": [ref] if metadata["family"] == "EC" else
                 [{"citation_ref": ref, "claim_value": 40}]}
        if metadata["arm"] == "ace":
            value = {"reasoning": "synthetic public finding", "bullet_ids": [], "final_answer": value}
        validate(value, schema)
        response = {"content": json.dumps(value), "finish_reason": "stop",
                    "prompt_tokens": 13, "completion_tokens": 17}
        raw = {"response": response, **metadata}
        RunStore.immutable_json(dest, raw)
        self.native.append(raw)
        return response

    monkeypatch.setattr(common, "read", grading_read)
    monkeypatch.setattr(frozen.FrozenEvaluation, "call", call)
    study = frozen.FrozenEvaluation(seal())
    study.run()
    result = read(study.out / "completion.json")
    assert len(calls) == 4 and len(grade_reads) == 8
    assert len(result["exact_wire_reuses_not_independent_draws"]) == 4
    assert result["teacher_calls"] == 0
    assert result["native_prompt_tokens"] == 52 and result["native_completion_tokens"] == 68
    assert all(v["EC"]["f1"] == v["EV"]["f1"] == 1 for v in result["metrics"].values())
    assert result["paired_vs_own_B1_frozen"]["ours"]["mean_f1_difference"] == 0


@pytest.mark.parametrize("mutation", ["teacher", "not_frozen", "missing_B1", "failed_learning", "zero_cases"])
def test_reject_invalid_final_matrix_before_test_packet_read(plan, monkeypatch, mutation):
    cfg, _, root = plan
    if mutation == "teacher":
        cfg["teacher"] = {"model": "not_allowed"}
    elif mutation == "not_frozen":
        cfg["final_matrix_frozen"] = False
    elif mutation == "missing_B1":
        cfg["arms"] = [a for a in cfg["arms"] if a["role"] != "B1_frozen"]
    elif mutation == "zero_cases":
        cfg["source_cases"] = 0
    else:
        path = root / "runs/learn_direct/completion.json"
        RunStore.atomic_json(path, {**read(path), "status": "failed"})

    def guarded(path):
        assert str(path) != str(root / cfg["input_packet"])
        return read(path)

    monkeypatch.setattr(frozen, "read", guarded)
    with pytest.raises(ValueError):
        frozen.fixed_banks(cfg)


def test_test_overlap_is_retained_as_failure_without_inference_or_resampling(plan, monkeypatch):
    cfg, seal, root = plan
    packet = root / cfg["input_packet"]
    rows = copy.deepcopy(read(packet)["rows"])
    for row in rows:
        row["source_key"] = "TRAIN0"
    RunStore.atomic_json(packet, {"rows": rows})
    monkeypatch.setattr(frozen.FrozenEvaluation, "call", lambda *args: pytest.fail("No model call allowed"))
    study = frozen.FrozenEvaluation(seal())
    with pytest.raises(ValueError, match="overlaps"):
        study.run()
    assert (study.out / "failure.json").is_file()
    assert not (study.out / "completion.json").exists()
    assert read(packet)["rows"] == rows


def test_native_failure_is_preserved_without_retry_or_partial_scoring(plan, monkeypatch):
    _, seal, _ = plan
    calls = []

    def failed_call(*args):
        calls.append(1)
        raise RuntimeError("synthetic transport failure")

    monkeypatch.setattr(frozen.FrozenEvaluation, "call", failed_call)
    monkeypatch.setattr(frozen.FrozenEvaluation, "grade", lambda *args: pytest.fail("No partial scoring"))
    study = frozen.FrozenEvaluation(seal())
    with pytest.raises(RuntimeError, match="synthetic transport failure"):
        study.run()
    assert calls == [1]
    assert (study.out / "failure.json").is_file()
    assert not (study.out / "completion.json").exists()


def test_changed_ACE_inference_adapter_cannot_be_used_with_a_differently_trained_bank(plan):
    cfg, _, root = plan
    path = root / "configs/ace.frozen.json"
    changed = read(path)
    changed["files"][frozen.ACE_ACTOR_FILES[-1]] = "not-the-trained-adapter"
    RunStore.atomic_json(path, changed)
    with pytest.raises(ValueError, match="Shared task actor/scorer changed"):
        frozen.fixed_banks(cfg)


def test_completed_flag_cannot_hide_missing_training_sources(plan):
    cfg, _, root = plan
    path = root / "runs/learn_direct/completion.json"
    changed = read(path)
    changed["prequential_skills"]["EV"]["tasks"] = 1
    RunStore.atomic_json(path, changed)
    with pytest.raises(ValueError, match="every declared source"):
        frozen.fixed_banks(cfg)


def test_same_learned_bank_cannot_be_renamed_as_two_learning_repeats(plan):
    cfg, _, _ = plan
    ours = next(a for a in cfg["arms"] if a["role"] == "evolved")
    cfg["arms"].append({**ours, "name": "not_an_independent_repeat"})
    with pytest.raises(ValueError, match="not independent repeats"):
        frozen.fixed_banks(cfg)
