"""Bounded teacher induction of source-code features; zero lawyer generation.

Keeps the legal task and final-lawyer authority unchanged. This is a fixed-history
development check, not online learning completion or a formal TEST experiment.
"""

from __future__ import annotations

import argparse
import json
import pickle
import signal
import time
import traceback
import zipfile
from pathlib import Path

import numpy as np
from threadpoolctl import threadpool_limits

from legal_skill_guard.data import source_components
from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.learning.executable_features import (
    ATTRIBUTES, BUILTINS, FEATURE_PROTOCOL, GUIDANCE_SCHEMA, fit_feature_model, publish,
)
from legal_skill_guard.learning.experiment import Comparison, ROOT, now, read, sha
from legal_skill_guard.learning.publication import differential_schema
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

WRITER = (
    "Learn compact executable SOURCE FEATURE skills from ONLY the supplied original "
    "already-seen TRAIN documents, their original benchmark annotations and actual "
    "historical observations. This is label-assisted external skill induction, not "
    "fine-tuning the frozen lawyer or canonical TF-GRPO. The final lawyer still "
    "decides every original NLI label and citation. Your functions supply features "
    "to a shared supervised word/feature LR and contract-OOF calibrated membership "
    "scorer; they do not directly become evidence sets or legal verdicts. The "
    "ordinary control fits the SAME sources and algorithm without these features. "
    "A feature name or nonzero value is not evidence of utility. "
    "Publish CREATE/UPDATE/DELETE/MERGE or an explicit NOOP against the exact parent. "
    "All structurally valid operations publish without efficacy admission, selection "
    "or rollback. No forced skill count, topics, growth or one-per-hypothesis rule. "
    "Each skill has guidance.feature_names and guidance.python_source. The code "
    "must define span_features(text, spans), taking the COMPLETE original contract "
    "string and its original [start,end] coordinates, returning a list of len(spans) "
    "rows, each containing exactly len(feature_names) booleans or finite numbers "
    "in [0,1]. Values are fallible factual features, NOT evidence probabilities. "
    "Feature names and order must remain stable across contracts. Do not use case "
    "IDs, parties, dates, document fingerprints, special lengths or hardcoded source "
    "span indices/answer tables. No runtime Gold is available. Learn source-observable "
    "regularities across contrasted cases; do not memorize quotations, arbitrarily "
    "expand an entire section, or infer absence of a legal topic from a failed match. "
    "You may express compositional actors/actions, explicit modalities/conditions, "
    "scope of definitions/lists and syntactic cross-span links instead of relying "
    "only on consecutive phrase matches plus fixed neighbour windows. These are "
    "possible computation patterns, not mandatory feature types or a legal oracle. "
    "All original text remains available. The model sees source-derived candidate "
    "scores/locations, NEVER your code or docstrings as legal advice. "
    "Code executes in a restricted resource-limited CPU child. No imports: re is "
    "already provided. Only function definitions and an optional module docstring "
    "are allowed at top level; put constants inside functions. Helpers may be "
    "defined normally. No classes, decorators, reflection, filesystem, network, "
    "dynamic exec/eval, other models or mutable external state. Use only the "
    "explicitly supplied builtins and text/container/regex attribute allowlist. "
    "Keep processing bounded and return [] for an empty spans list. Do not emit "
    "imports even for re. Do not print. Every failure stops the study without "
    "repair, substitute function, retries or a second teacher. "
    "Historical lawyer observations retain their actual old bank identities. They "
    "are NOT outcomes of the new empty-parent code learner; do not invent new "
    "rollouts, actions or successes. Unannotated spans are benchmark nonmembers, "
    "not universal legal-semantic negatives. Only the supplied TRAIN sources may "
    "support operation rationales. Aim <=3200 total serialized library tokens under "
    "the hard4096 budget, including IDs/scopes/names/source, with no truncation."
)


def author_train(cfg):
    assert sha(ROOT / cfg["source_archive"]) == cfg["source_archive_sha256"]
    with zipfile.ZipFile(ROOT / cfg["source_archive"]) as archive:
        return json.loads(archive.read("contract-nli/train.json"))


def prepare(config):
    cfg = read(config)
    assert not Path(config).with_suffix(".frozen.json").exists()
    assert not (ROOT / "runs" / cfg["run_id"]).exists()
    author = author_train(cfg)
    original = {r["id"]: r for r in author["documents"]}
    train, future = cfg["training_ids"], cfg["development_ids"]
    assert len(train) == len(set(train)) == 18 and len(future) == len(set(future)) == 16
    assert not any(set(g) & set(train) and set(g) & set(future)
                   for g in source_components(author["documents"]))
    reference = ROOT / cfg["historical_query_run"]
    manifest = read(reference / "evidence_models/evolving_memory_M3.manifest.json")
    assert train == manifest["seen_original_source_ids"]
    observations, observation_files = [], []
    for path in sorted(reference.glob("batch*_*/evolving_memory/*.public.json")):
        unit = read(path)
        if unit["document_id"] not in train:
            continue
        response = unit["response"]
        observations.append({"actual_public_unit_path": str(path), "sha256": sha(path),
            "document_id": unit["document_id"], "actual_recorded_metadata": {
                k: unit[k] for k in ("stage", "arm", "public_valid", "program_library_sha256",
                    "published_library_sha256", "published_library") if k in unit},
            "actual_public_response": {k: response[k] for k in ("raw_id", "finish_reason", "content")},
            "historical_not_new_code_learner_rollout": True})
        observation_files.append(path)
    body = {"public_hypotheses": author["labels"], "current_parent_library": [],
        "complete_original_already_seen_TRAIN": [{"source_case_id": d,
            "text": original[d]["text"], "spans": original[d]["spans"],
            "original_annotations": original[d]["annotation_sets"][0]["annotations"]} for d in train],
        "actual_historical_own_public_observations": observations,
        "historical_query_libraries_not_seeded_as_current_parent": {
            str(b): read(reference / f"update_transactions/b{b}.json")["publication"] for b in (1, 2, 3)},
        "allowed_builtins": list(BUILTINS), "allowed_attributes": sorted(ATTRIBUTES),
        "no_new_case_or_development_outcome_or_private_reasoning_supplied": True,
        "new_learner_has_no_actual_rollouts_yet": True}
    body_path = ROOT / cfg["teacher_body"]
    RunStore.immutable_json(body_path, body)
    files = [p for p in (ROOT / "legal_skill_guard").rglob("*.py") if p.is_file()]
    files += [Path(__file__).resolve(), Path(config).resolve(), body_path,
              ROOT / cfg["source_archive"], ROOT / cfg["method_protocol"],
              ROOT / cfg["teacher_profile_reference"], ROOT / cfg["inference_profile_reference"],
              ROOT / cfg["inference_environment"], reference / "evidence_models/base_memory_M3.manifest.json"]
    files += observation_files
    files += [reference / f"update_transactions/b{b}.json" for b in (1, 2, 3)]
    RunStore.immutable_json(Path(config).with_suffix(".frozen.json"), {
        "config_sha256": sha(config), "files": {str(p.resolve()): sha(p) for p in files},
        "teacher_only_original18_sources_and_actual_public_observations": True,
        "new16_are_developer_exposed_TRAIN_not_held_out_or_official_TEST": True})
    print(json.dumps({"prepared": cfg["run_id"], "historical_public_observations": len(observations),
                      "planned_new_native_teacher_CPU_fits": [0, 1, 2]}), flush=True)


class FeatureInduction(Comparison):
    def __init__(self, config):
        self.cfg = read(config)
        self.cfg["teacher"] = read(ROOT / self.cfg["teacher_profile_reference"])["teacher"]
        self.cfg["generation"] = read(ROOT / self.cfg["inference_profile_reference"])["generation"]
        frozen = Path(config).with_suffix(".frozen.json")
        binding = read(frozen)
        assert binding["config_sha256"] == sha(config)
        self.bindings = {**binding["files"], str(frozen.resolve()): sha(frozen)}
        self.run_id, self.out = self.cfg["run_id"], ROOT / "runs" / self.cfg["run_id"]
        assert not self.out.exists(), "New Run ID; never restart, overwrite or retry"
        self.native, self.teachers, self.teacher_attempts = [], [], 0
        self.stop, self.current_batch, self.cpu_fits = False, 0, 0
        self.meter = WireClient(self.cfg["generation"])
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: setattr(self, "stop", True))

    def call(self, *args, **kwargs):
        raise AssertionError("Zero native generation in this finite feature induction")

    def record(self, name, value):
        path = self.out / name
        RunStore.immutable_json(path, value)
        return path

    def execute(self):
        self.check()
        self.record("declaration.json", {"at": now(), "config": self.cfg,
            "actual_initial_bank": [], "frozen_bindings": self.bindings.copy(),
            "final_lawyer_authority_unchanged_no_direct_evidence_reuse": True})
        author = author_train(self.cfg)
        original = {r["id"]: r for r in author["documents"]}
        labels, train = author["labels"], self.cfg["training_ids"]
        value = self.teacher_call("empty_parent_code_features", WRITER,
            read(ROOT / self.cfg["teacher_body"]),
            differential_schema(labels, [], train, guidance_schema=GUIDANCE_SCHEMA))
        bank = publish([], value, labels, train)
        tokens = self.meter.token_count(text=json.dumps(bank, ensure_ascii=False, separators=(",", ":")))
        assert tokens <= self.cfg["library_token_hard_cap"], "No clipping or substitute library"
        self.record("publication.json", {"at": now(), "parent": [], "teacher_value": value,
            "publication": bank, "bank_sha256": csha(bank), "tokens": tokens,
            "all_structurally_valid_edits_published_no_efficacy_gate": True})
        models, usage = {}, {}
        for arm, library in (("ordinary", []), ("code_features", bank)):
            self.check()
            self.progress("CPU_fit", current_arm=arm)
            start = time.monotonic()
            self.cpu_fits += 1
            model = fit_feature_model([original[d] for d in train], labels, library)
            path = self.out / f"{arm}.pickle"
            with path.open("xb") as stream:
                pickle.dump(model, stream, protocol=5)
            models[arm] = model
            usage[arm] = {"fit_seconds": time.monotonic() - start, "path": str(path), "sha256": sha(path),
                "feature_protocol": FEATURE_PROTOCOL, "stage1_design_widths": model.stage1_design_widths_,
                "contract_fold_source_partitions": model.stage1_oof_source_partitions_,
                "actual_training_execution_receipts": model.source_execution_receipts.copy()}
        ids = self.cfg["development_ids"]
        documents = [{"doc_id": str(d), "text": original[d]["text"], "spans": original[d]["spans"]} for d in ids]
        items = [{"doc_id": str(d), "hypothesis_key": h, "n_spans": len(original[d]["spans"])} for d in ids for h in labels]
        vectors = {}
        for arm, model in models.items():
            self.check()
            self.progress("CPU_predict_complete16", current_arm=arm)
            with threadpool_limits(limits=2):
                values = model.predict_scores(items, documents)
            assert len(values) == len(items)
            for item, vector in zip(items, values, strict=True):
                assert len(vector) == item["n_spans"] and np.isfinite(vector).all()
            vectors[arm] = [v.tolist() for v in values]
            self.record(f"{arm}_all16_raw_scores_before_unified_grading.json", {"items": items,
                "raw_scores": vectors[arm], "actual_execution_receipts": model.source_execution_receipts})
        # All predictions now exist. The original annotations never enter the
        # executable functions or current-case classifier prediction inputs.
        counts = {arm: np.zeros(3, dtype=int) for arm in models}
        per = []
        for i, item in enumerate(items):
            d, h = int(item["doc_id"]), item["hypothesis_key"]
            gold = original[d]["annotation_sets"][0]["annotations"][h]
            row = {"document_id": d, "hypothesis_id": h, "Gold": gold, "arms": {}}
            for arm in models:
                ps, gs = set(np.flatnonzero(np.asarray(vectors[arm][i]) > .5).tolist()), set(gold["spans"])
                tally = np.array([len(ps & gs), len(ps - gs), len(gs - ps)], dtype=int)
                if gold["choice"] != "NotMentioned":
                    counts[arm] += tally
                row["arms"][arm] = {"predicted_original_members": sorted(ps), "tp_fp_fn": tally.tolist()}
            per.append(row)
        metrics = {arm: {"TP": int(c[0]), "FP": int(c[1]), "FN": int(c[2]),
            "Gold_NN_hard_micro_F1": float(2*c[0]/(2*c[0]+c[1]+c[2]))} for arm, c in counts.items()}
        self.check()
        result = {"at": now(), "run_id": self.run_id, "actual_native_teacher_CPU_fits": [0, 1, self.cpu_fits],
            "actual_bank": bank, "metrics": metrics, "per_source_hypothesis": per, "model_artifacts": usage,
            "already_developer_exposed16_not_held_out_or_official_TEST": True,
            "no_end_to_end_lawyer_effect_or_online_learning_or_significance_claim": True,
            "all_valid_programs_used_no_bank_case_threshold_parameter_selection": True}
        self.record("completion.json", result)
        RunStore.atomic_json(self.out / "progress.json", {"state": "completed", **result})
        print(json.dumps({"completed": self.run_id, "metrics": metrics,
                          "actual_native_teacher_CPU_fits": [0, 1, self.cpu_fits]}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "run"))
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.config)
        return
    study = FeatureInduction(args.config)
    try:
        study.execute()
    except BaseException as exc:
        failure = {"at": now(), "error": repr(exc), "traceback": traceback.format_exc(),
            "stdout": str(getattr(exc, "stdout", "")), "stderr": str(getattr(exc, "stderr", "")),
            "actual_native_teacher_CPU_fits": [0, len(study.teachers), study.cpu_fits],
            "teacher_attempts": study.teacher_attempts, "no_retry_or_feature_or_answer_repair": True}
        study.record("failure.json", failure)
        RunStore.atomic_json(study.out / "progress.json", {"state": "failed", **failure})
        raise


if __name__ == "__main__":
    main()
