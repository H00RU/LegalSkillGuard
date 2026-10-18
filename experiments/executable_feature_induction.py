"""Bounded teacher induction of executable source features.

Keeps the legal task and final-lawyer authority unchanged. This is a fixed-history
development check, not online learning completion or a formal TEST experiment.
The declared semantic protocol counts its SAME-8B predicate execution as native
generation; historical pure-code protocols still require zero native calls.
"""

from __future__ import annotations

import argparse
import fcntl
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
    ATTRIBUTES, BUILTINS, EXECUTABLE_GUIDANCE_SCHEMA, FEATURE_PROTOCOL,
    GUIDANCE_SCHEMA, SEMANTIC_EXECUTION_PROTOCOL, SEMANTIC_SYSTEM,
    anchored_probability, fit_feature_model, publish,
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
    "to a source-scoped log-odds correction of an ordinary supervised membership "
    "scorer. The word scorer and its calibration are not refitted around your "
    "features; correction weights use contract-held-out ordinary predictions and "
    "proper Bernoulli loss, without a global intercept. Zero features imply the "
    "exact ordinary score, not a failure fallback or an efficacy decision. Features "
    "do not directly become evidence sets or legal verdicts. The "
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
SEMANTIC_METHOD = "same_8b_semantic_feature_feedback"
SEMANTIC_WRITER = (
    "Revise the EXACT supplied executable feature parent using ONLY the complete "
    "already-seen18 TRAIN contracts, original annotations and actual component "
    "diagnostics supplied here. No tools, outside law, future sources/results, "
    "private reasoning or invented lawyer rollouts. This is label-assisted external "
    "skill learning, not parameter training or TF-GRPO. The task, original labels "
    "and original SPAN metrics remain unchanged. The frozen8B lawyer still decides "
    "every final label and citation; feature activations are not final answers. "
    "The unchanged ordinary scorer and its source-held-out log-odds correction "
    "are as described in the supplied current-parent diagnostics. No score gating, "
    "selected bank, clipping, retries or rollback. Every valid CRUD/NOOP publishes. "
    "The runtime NOW supports two explicit feature representations. Existing "
    "guidance.feature_names/python_source functions retain their exact documented "
    "pure CPU behavior; they cannot call a model. Alternatively guidance contains "
    "feature_names/source_predicates, equal-length arrays in corresponding order. "
    "Each predicate is a concise reusable source-observable semantic condition. "
    "All semantic predicates are executed together in ONE whole-contract call to "
    "the SAME frozen8B, not another teacher/judge or per-span calls. It returns "
    "original indices where each condition is established. The learned scorer "
    "calibrates these fallible binary features using already-seen TRAIN membership; "
    "a nonzero activation does not force a citation and zero does not imply NM. "
    "Use this capability where regex cannot preserve actor/action/object, modality, "
    "conditional or cross-clause scope. Predicates should be operationally narrow "
    "enough for the8B to execute, not just renamed target NLI questions, expected "
    "answers, vague 'relevant evidence' instructions or whole-section catch-alls. "
    "Respect each condition's own source membership versus merely useful context. "
    "No parties, dates, document IDs/fingerprints, span integers, answer tables or "
    "memorized quotations in runtime guidance. Unannotated spans are benchmark "
    "nonmembers, not universal semantic negatives. Inspect complete TRAIN successes "
    "and failures rather than adding synonyms. You may UPDATE/DELETE/MERGE current "
    "skills, CREATE justified skills, or NOOP; no forced count, type, growth or "
    "conversion. Unmentioned parent records remain verbatim. UPDATE preserves its "
    "target ID, targets are unconsumed original parent IDs; only DELETE has null "
    "skill. Cite only supplied source_case_ids in audit rationale, never runtime. "
    "Return the requested differential JSON. Aim<=3200 serialized library tokens "
    "under the4096 hard budget with complete predicates, no truncation."
)


def author_train(cfg):
    assert sha(ROOT / cfg["source_archive"]) == cfg["source_archive_sha256"]
    with zipfile.ZipFile(ROOT / cfg["source_archive"]) as archive:
        return json.loads(archive.read("contract-nli/train.json"))


def prepare(config):
    cfg = read(config)
    semantic = cfg["method"] == SEMANTIC_METHOD
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
    parent = [] if not cfg.get("parent_publication") else read(ROOT / cfg["parent_publication"])["publication"]
    body = {"public_hypotheses": author["labels"], "current_parent_library": parent,
        "complete_original_already_seen_TRAIN": [{"source_case_id": d,
            "text": original[d]["text"], "spans": original[d]["spans"],
            "original_annotations": original[d]["annotation_sets"][0]["annotations"]} for d in train],
        "actual_historical_own_public_observations": observations,
        "historical_query_libraries_not_seeded_as_current_parent": {
            str(b): read(reference / f"update_transactions/b{b}.json")["publication"] for b in (1, 2, 3)},
        "allowed_builtins": list(BUILTINS), "allowed_attributes": sorted(ATTRIBUTES),
        "no_new_case_or_development_outcome_or_private_reasoning_supplied": True,
        "new_learner_has_no_actual_rollouts_yet": True}
    parent_files = []
    if parent:
        parent_result = read(ROOT / cfg["parent_training_result"])
        model_info = (parent_result["model_artifacts"][cfg["parent_model_arm"]]
                      if semantic else parent_result["model"])
        assert sha(model_info["path"]) == model_info["sha256"]
        with Path(model_info["path"]).open("rb") as stream:
            model = pickle.load(stream)
        assert model.library == parent and model.feature_protocol == FEATURE_PROTOCOL
        assert set(model.corpus_.doc_ids) == {str(d) for d in train}
        assert set(model.actual_held_source_base_probabilities) == {str(d)+"::"+h for d in train for h in author["labels"]}
        from legal_skill_guard._vendor.scienceclaw_contracts import _Corpus
        documents = [{"doc_id": str(d), "text": original[d]["text"], "spans": original[d]["spans"]} for d in train]
        items = [{"doc_id": str(d), "hypothesis_key": h, "n_spans": len(original[d]["spans"])} for d in train for h in author["labels"]]
        with threadpool_limits(limits=2):
            actual_scores = model.predict_scores(items, documents)
        corpus = _Corpus(documents)
        matrices = {h: model.source_features(corpus, h) for h in author["labels"]}
        raw_features = np.maximum.reduce(list(matrices.values()))
        diagnostics = []
        for d in train:
            rows = corpus.rows(str(d))
            nonzero = np.argwhere(raw_features[rows] != 0)
            entry = {"source_case_id": d, "n_original_spans": len(rows),
                "lossless_feature_nonzero_triplets": [[int(i), int(j), float(raw_features[rows][i,j])] for i,j in nonzero],
                "all_omitted_feature_entries_are_exact_zero": True, "hypotheses": {}}
            for h in author["labels"]:
                base = np.asarray(model.actual_held_source_base_probabilities[str(d)+"::"+h])
                scores = anchored_probability(base, matrices[h][rows], model.residual_coefficients[h])
                index = next(i for i,it in enumerate(items) if it["doc_id"] == str(d) and it["hypothesis_key"] == h)
                entry["hypotheses"][h] = {"actual_source_held_out_ordinary_scores": base.tolist(),
                    "anchored_training_diagnostic_candidate_indices": np.flatnonzero(scores > .5).tolist(),
                    "actual_full_parent_model_candidate_indices": np.flatnonzero(actual_scores[index] > .5).tolist()}
            diagnostics.append(entry)
        body.pop("actual_historical_own_public_observations")
        body.pop("historical_query_libraries_not_seeded_as_current_parent")
        body.pop("new_learner_has_no_actual_rollouts_yet")
        body["native_lawyer_rollouts_for_this_code_learner"] = 0
        body["actual_current_parent_has_CPU_component_observations_only"] = True
        body["actual_current_parent_auxiliary_diagnostics"] = diagnostics
        body["actual_feature_columns"] = [{"skill_id": s["id"], "feature_name": name} for s in parent for name in s["guidance"]["feature_names"]]
        body["actual_current_parent_coefficients_by_hypothesis"] = {h: v.tolist() for h,v in model.residual_coefficients.items()}
        body["actual_training_feedback_interpretation"] = (
            "All original18 sources, all17 queries and every source feature/ordinary held-source score are present. "
            "Feature triplets plus dimensions/default zero are lossless. Apply public skill scopes before the dot product. "
            "The coefficients were fit using all18 TRAIN: the corrected held-base diagnostics are NOT independently held-out "
            "predictions of the whole feature learner. Actual full-parent candidate sets are in-sample runtime predictions. "
            "These are actual CPU evidence-operator outputs, NOT native-lawyer rollouts or group-relative rewards. "
            "Use both missing and excess original members and preserved successes to revise coherent source computations; "
            "do not merely reverse a coefficient or add synonyms without checking complete conditions. "
            "No new16 source, label, result, selected failure subset or private reasoning is supplied.")
        parent_files = [ROOT/cfg["parent_publication"], ROOT/cfg["parent_training_result"], Path(model_info["path"])]
    if semantic:
        assert cfg["generation"]["model"] == "Qwen/Qwen3-8B"
        assert cfg["generation"]["disable_thinking"] is True
        assert cfg["planned_new_native_calls"] == len(train) + len(future)
        body["explicit_same_8B_semantic_execution"] = {
            "protocol": SEMANTIC_EXECUTION_PROTOCOL,
            "actual_executor_system": SEMANTIC_SYSTEM,
            "runtime_inputs": "complete public original text/spans and predicates ONLY",
            "output": "one original-index list per predicate, fallible binary features",
            "final_lawyer_authority_unchanged": True,
            "no_semantic_execution_outcomes_exist_yet": True}
    body_path = ROOT / cfg["teacher_body"]
    RunStore.immutable_json(body_path, body)
    files = [p for p in (ROOT / "legal_skill_guard").rglob("*.py") if p.is_file()]
    files += [Path(__file__).resolve(), Path(config).resolve(), body_path,
              ROOT / cfg["source_archive"], ROOT / cfg["method_protocol"],
              ROOT / cfg["teacher_profile_reference"], ROOT / cfg["inference_profile_reference"],
              ROOT / cfg["inference_environment"], reference / "evidence_models/base_memory_M3.manifest.json"]
    files += observation_files
    files += parent_files
    files += [reference / f"update_transactions/b{b}.json" for b in (1, 2, 3)]
    RunStore.immutable_json(Path(config).with_suffix(".frozen.json"), {
        "config_sha256": sha(config), "files": {str(p.resolve()): sha(p) for p in files},
        "teacher_only_original18_sources_and_actual_public_observations": True,
        "new16_are_developer_exposed_TRAIN_not_held_out_or_official_TEST": True})
    print(json.dumps({"prepared": cfg["run_id"], "parent_skills": len(parent),
                      "historical_public_observations": 0 if parent else len(observations),
                      "planned_model_factory_calls": 2,
                      "planned_new_native_teacher_CPU_fits": [cfg["planned_new_native_calls"], 1,
                                                               cfg["planned_new_CPU_fits"]]}), flush=True)


class FeatureInduction(Comparison):
    def __init__(self, config):
        self.cfg = read(config)
        self.semantic = self.cfg["method"] == SEMANTIC_METHOD
        self.cfg["teacher"] = read(ROOT / self.cfg["teacher_profile_reference"])["teacher"]
        if not self.semantic:
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
        if not self.semantic:
            raise AssertionError("Zero native generation in the pure-code feature induction")
        return Comparison.call(self, *args, **kwargs)

    def semantic_call(self, messages, schema, document):
        if len(self.native) >= self.cfg["planned_new_native_calls"]:
            raise ValueError("Declared semantic native-call bound exceeded")
        source = csha({"text": document["text"], "spans": document["spans"]})
        return self.call(self.out / "native_semantics" / self.feature_phase / (source+".json"),
            messages, schema, self.cfg["generation"]["max_tokens"], {
                "stage": self.feature_phase, "arm": "code_features",
                "document_id": document["doc_id"], "call_role": "source_predicates",
                "semantic_protocol": SEMANTIC_EXECUTION_PROTOCOL,
                "no_final_NLI_or_evidence_decision": True})

    def record(self, name, value):
        path = self.out / name
        RunStore.immutable_json(path, value)
        return path

    def execute(self):
        self.check()
        parent = [] if not self.cfg.get("parent_publication") else read(ROOT/self.cfg["parent_publication"])["publication"]
        self.record("declaration.json", {"at": now(), "config": self.cfg,
            "actual_initial_bank": parent, "frozen_bindings": self.bindings.copy(),
            "semantic_execution_uses_same_frozen_lawyer_counted_as_native": self.semantic,
            "final_lawyer_authority_unchanged_no_direct_evidence_reuse": True})
        author = author_train(self.cfg)
        original = {r["id"]: r for r in author["documents"]}
        labels, train = author["labels"], self.cfg["training_ids"]
        name = "current_parent_code_feature_update" if parent else "empty_parent_code_features"
        guidance = EXECUTABLE_GUIDANCE_SCHEMA if self.semantic else GUIDANCE_SCHEMA
        value = self.teacher_call(name, SEMANTIC_WRITER if self.semantic else WRITER,
            read(ROOT / self.cfg["teacher_body"]),
            differential_schema(labels, parent, train, guidance_schema=guidance))
        bank = publish(parent, value, labels, train, guidance_schema=guidance)
        tokens = self.meter.token_count(text=json.dumps(bank, ensure_ascii=False, separators=(",", ":")))
        assert tokens <= self.cfg["library_token_hard_cap"], "No clipping or substitute library"
        self.record("publication.json", {"at": now(), "parent": parent, "teacher_value": value,
            "publication": bank, "bank_sha256": csha(bank), "tokens": tokens,
            "all_structurally_valid_edits_published_no_efficacy_gate": True})
        models, usage = {}, {}
        for arm, library in (("ordinary", []), ("code_features", bank)):
            self.check()
            self.progress("CPU_fit", current_arm=arm)
            start = time.monotonic()
            self.cpu_fits += 1
            self.feature_phase = "training_source_features"
            model = fit_feature_model([original[d] for d in train], labels, library,
                semantic_caller=self.semantic_call if self.semantic else None)
            path = self.out / f"{arm}.pickle"
            with path.open("xb") as stream:
                pickle.dump(model, stream, protocol=5)
            models[arm] = model
            usage[arm] = {"fit_seconds": time.monotonic() - start, "path": str(path), "sha256": sha(path),
                "feature_protocol": FEATURE_PROTOCOL, "stage1_design_widths": model.stage1_design_widths_,
                "base_scorer_fit_count": model.base_fit_count,
                "outer_source_partitions": model.outer_source_partitions,
                "residual_fit_diagnostics": model.residual_fit_diagnostics,
                "contract_fold_source_partitions": model.stage1_oof_source_partitions_,
                "actual_training_execution_receipts": model.source_execution_receipts.copy()}
        ids = self.cfg["development_ids"]
        documents = [{"doc_id": str(d), "text": original[d]["text"], "spans": original[d]["spans"]} for d in ids]
        items = [{"doc_id": str(d), "hypothesis_key": h, "n_spans": len(original[d]["spans"])} for d in ids for h in labels]
        vectors = {}
        for arm, model in models.items():
            self.check()
            self.progress("CPU_predict_complete16", current_arm=arm)
            self.feature_phase = "development_source_features"
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
        result = {"at": now(), "run_id": self.run_id,
            "actual_native_teacher_CPU_fits": [len(self.native), len(self.teachers),
                                               sum(v["base_scorer_fit_count"] for v in usage.values())],
            "actual_model_factory_calls": self.cpu_fits,
            "actual_bank": bank, "metrics": metrics, "per_source_hypothesis": per, "model_artifacts": usage,
            "already_developer_exposed16_not_held_out_or_official_TEST": True,
            "no_end_to_end_lawyer_effect_or_online_learning_or_significance_claim": True,
            "all_valid_programs_used_no_bank_case_threshold_parameter_selection": True}
        self.record("completion.json", result)
        RunStore.atomic_json(self.out / "progress.json", {"state": "completed", **result})
        print(json.dumps({"completed": self.run_id, "metrics": metrics,
                          "actual_native_teacher_CPU_fits": result["actual_native_teacher_CPU_fits"]}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "run"))
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.config)
        return
    with (ROOT / "artifacts/gpu_generation.lock").open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        study = FeatureInduction(args.config)
        try:
            study.execute()
        except BaseException as exc:
            failure = {"at": now(), "error": repr(exc), "traceback": traceback.format_exc(),
                "stdout": str(getattr(exc, "stdout", "")), "stderr": str(getattr(exc, "stderr", "")),
                "actual_native_teacher_attempted_factory_calls": [len(study.native), len(study.teachers), study.cpu_fits],
                "failed_factory_internal_fit_count_not_inferred": True,
                "teacher_attempts": study.teacher_attempts, "no_retry_or_feature_or_answer_repair": True}
            study.record("failure.json", failure)
            RunStore.atomic_json(study.out / "progress.json", {"state": "failed", **failure})
            raise


if __name__ == "__main__":
    main()
