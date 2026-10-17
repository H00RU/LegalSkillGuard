"""Online executable source acquisition; no learned legal advice in inference.

One frozen lawyer makes every final decision. Reuses the existing attributed
literal matcher, explicit source windows, list introductions and atomic editor.
No learned scorer fit, model router, answer correction or performance gate.
"""

from __future__ import annotations

import copy
import hashlib
import io
import json
import pickle
import signal
import tarfile
import zipfile
from pathlib import Path

from jsonschema import validate

from legal_skill_guard.experiment.storage import RunStore, safe_component
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.task import coherent_native_schema, marked_text, output_schema
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

from .audit import original_score
from .clauses import (
    _SUFFIXES,
    _WORD,
    _tokens,
    context_original_clauses,
    find_original_clauses,
    original_clause_records,
)
from .conditioned import list_preamble_links
from .evidence_programs import evidence_proposals
from .experiment import ROOT, Comparison, now, points, read, sha
from .publication import (
    apply_differential_publication,
    differential_schema,
    publication_statistics,
    skill_record_schema,
)

TERMS = {"type": "array", "maxItems": 32,
    "items": {"type": "string", "minLength": 1, "maxLength": 256}}
QUERY_SCHEMA = {"type": "object", "additionalProperties": False,
    "required": ["all_phrases", "any_phrases", "none_phrases", "before", "after", "include_list_preamble"],
    "properties": {k: copy.deepcopy(TERMS) for k in ("all_phrases", "any_phrases", "none_phrases")}
    | {k: {"type": "integer", "minimum": 0, "maximum": 64} for k in ("before", "after")}
    | {"include_list_preamble": {"type": "boolean"}}}
GUIDANCE_SCHEMA = {"type": "object", "additionalProperties": False,
    "required": ["source_queries"], "properties": {"source_queries": {
        "type": "array", "minItems": 1, "maxItems": 8, "items": QUERY_SCHEMA}}}
NOTICE = (
    " The complete original NDA remains present and unchanged. Each hypothesis "
    "has fallible_evidence_candidates from a fixed ordinary retriever, plus "
    "additional_source_read_indices obtained by literal source access. Both "
    "resolve to exact original text in candidate_original_text. Additional "
    "indices omit duplicate ordinary candidates, not low-scoring facts. These "
    "are reading aids, never a verdict or mandatory evidence. Scores describe "
    "fallible evidence membership, not legal confidence. No skill code, identity, "
    "scope-control map, query counts or teacher advice is supplied. Empty leads "
    "never mean NotMentioned. Read the full source, reject irrelevant material "
    "and cite ANY original index as needed, including outside every lead. "
    "Decide the exact original hypothesis yourself; do not substitute another "
    "hypothesis. Return choice, spans and reason only."
)
TEACHER = (
    "Learn reusable executable SOURCE-ACQUISITION skills for original ContractNLI "
    "from ONLY these cumulative already-seen TRAIN sources, original annotations "
    "and actual own frozen-lawyer public answers. No tools/outside law/private "
    "reasoning, invented success, future data or other-arm answers. All supplied "
    "cumulative cases and successes/failures remain teaching evidence. Original "
    "Gold is benchmark supervision, not universal legal truth. The lawyer receives "
    "source locations only, NEVER your legal guidance, examples or rationale. "
    "You cannot repair its final labels directly. Acquire governing/definitional/"
    "exception/independently responsive evidence without turning retrieval into "
    "a verdict. Do not infer absence from no lexical hit. A Gold member need not "
    "independently prove the entire relation; do not delete known members merely "
    "because you consider them context, and do not mechanically add all logical "
    "premises to the original evidence target. Read complete sources for scope. "
    "Runtime skill=id,hypothesis_ids,guidance.source_queries ONLY. No inspection "
    "text, examples, labels, case IDs, parties, dates, source indices, fingerprints "
    "or answer lookup tables. No fixed topics/count, forced growth or deletion. "
    "Each query has all_phrases,any_phrases,none_phrases,before,after,"
    "include_list_preamble. The existing lightly suffix-stemmed lower-case word/"
    "number matcher requires every all phrase, one any phrase if nonempty, and "
    "no none phrase, contiguously WITHIN an original SPAN. At least one all/any "
    "phrase is mandatory, not an empty catch-all. Negation/modality are retained. "
    "before/after(0..64) return literal original neighbours around direct hits. "
    "The boolean adds existing fallible list-introduction locations, not semantic "
    "dependency. Direct/neighbor/preamble provenance stays distinct. Full original "
    "text is never paraphrased. No fallback queries or semantic classifier. "
    "The common ordinaryM2 stays fixed; current_parent_source_replay is a TRUE "
    "factual program execution on seen sources, not new lawyer responses. Actual "
    "observations name their earlier bank and native response; do not treat all "
    "as executions of the current parent. Receipt query arguments resolve from "
    "that complete observed bank and query_index; source indices resolve in the "
    "supplied full original text. Inspect all original evidence misses versus "
    "current acquisition, plus actual failure to use visible candidates and wrong "
    "relations. Reading nonGold conditions/context is not inherently an error; "
    "NM has no evidence annotation, not proof every context read is irrelevant. "
    "Prefer compact compositional searches warranted by several seen contexts; "
    "do not memorize long phrases, add broad catch-all noise, or merely recount "
    "missed Gold without publishing a reusable acquisition action. "
    "Publish atomic CREATE/UPDATE/DELETE/MERGE against exact parent IDs. "
    "CREATE has0 targets, UPDATE/DELETE1, MERGE>=2 distinct original IDs. UPDATE "
    "keeps its ID; MERGE may retain a consumed ID. No forward targets or duplicate "
    "consumption. Only DELETE has null skill. Unmentioned records stay VERBATIM. "
    "Cite supplied seen source_case_ids and an audit rationale per edit; neither "
    "is served to the lawyer. No operations requires a nonempty noop_reason, "
    "otherwise null. Every valid edit publishes without efficacy admission or "
    "rollback. Complete master AND master-plus-public-scope map must fit4096 "
    "actual8B tokens; aim<=2200 master to leave correction room. Never truncate "
    "knowledge or force expansion. Return exactly the differential schema."
)


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def execute_library(row, bank):
    """Source-only, deterministic, and incapable of emitting a legal label."""
    assert set(row) == {"id", "text", "spans"}
    records, executions = original_clause_records(row), {}
    for skill in bank:
        events = []
        for qi, query in enumerate(skill["guidance"]["source_queries"]):
            validate(query, QUERY_SCHEMA)
            hits = find_original_clauses(records, query["all_phrases"], query["any_phrases"], query["none_phrases"])
            context = context_original_clauses(records, hits, query["before"], query["after"])
            neighbours = sorted({r["original_span_index"] for r in context} - set(hits))
            links = list_preamble_links(row, hits) if query["include_list_preamble"] else []
            preambles = sorted({v["possible_preamble_span_index"] for v in links})
            events.append({"query_index": qi, "matched": hits, "neighbour": neighbours,
                "preamble": preambles, "possible_list_links": links})
        executions[skill["id"]] = events
    return executions


def source_messages(row, labels, system, bank, proposals):
    """Canonical source facts; equivalent read sets have identical actor input."""
    assert set(row) == {"id", "text", "spans"}
    public_schema = output_schema(row, list(labels), [], reporting=False)
    one = public_schema["properties"][next(iter(labels))]
    one["additionalProperties"] = False
    one["properties"]["reason"] = {"type": "string"}
    one["required"] = ["choice", "spans", "reason"]
    common = copy.deepcopy(one)
    common["properties"]["spans"]["items"] = {"type": "integer"}
    schema = coherent_native_schema(public_schema)
    executions = execute_library(row, bank)
    catalogue, hypotheses, reads, incremental = {}, {}, {}, {}
    for h, label in labels.items():
        candidates = copy.deepcopy(proposals["by_hypothesis"][h]["candidates"]) if proposals else []
        ordinary = {v["original_span_index"] for v in candidates}
        returned = {i for s in bank if h in s["hypothesis_ids"]
            for event in executions[s["id"]] for role in ("matched", "neighbour", "preamble")
            for i in event[role]}
        reads[h], incremental[h] = sorted(returned), sorted(returned - ordinary)
        for i in sorted(ordinary | returned):
            catalogue[str(i)] = row["text"][slice(*row["spans"][i])]
        hypotheses[h] = {"original_hypothesis": label["hypothesis"],
            "original_public_short_description": label["short_description"],
            "fallible_evidence_candidates": candidates,
            "additional_source_read_indices": incremental[h]}
    body = {"full_contract_with_original_span_markers": marked_text(row),
        "hypotheses": hypotheses,
        "candidate_original_text": {str(i): catalogue[str(i)] for i in sorted(map(int, catalogue))},
        "output_contract": {"required_hypothesis_keys": list(labels),
            "common_schema_for_each_hypothesis": common, "schema_is_permitted_values_not_answers": True}}
    messages = [{"role": "system", "content": system + NOTICE}, {"role": "user", "content": compact(body)}]
    return messages, schema, {"actual_source_executions": executions,
        "per_hypothesis_returned_original_indices": reads,
        "per_hypothesis_incremental_delivered_indices": incremental,
        "original_source_unchanged_without_global_query_tags": True,
        "no_control_metadata_or_variable_used_ID_schema_delivered": True,
        "no_program_code_or_semantic_inspection_delivered": True,
        "all_legal_decisions_and_final_citations_are_native": True}


def prepare_acquisition_inputs(cfg):
    cohort_path = ROOT / cfg["source_cohort"]
    cohort = read(cohort_path)
    assert cfg["training_ids"] == cohort["selected_source_ids_in_fixed_order"]
    assert len(cfg["training_ids"]) == 32 and len(set(cfg["training_ids"])) == 32
    archive_path = ROOT / cfg["source_archive"]
    assert sha(archive_path) == cfg["source_archive_sha256"]
    with zipfile.ZipFile(archive_path) as archive:
        author = json.loads(archive.read("contract-nli/train.json"))
    originals = {r["id"]: r for r in author["documents"]}
    rows = cohort["documents_without_Gold"]
    assert [r["id"] for r in rows] == cfg["training_ids"]
    for row in rows:
        assert set(row) == {"id", "text", "spans"}
        assert all(row[k] == originals[row["id"]][k] for k in row)
    RunStore.immutable_json(ROOT / cfg["input_packet"], {"public_hypotheses": author["labels"], "documents": rows})
    RunStore.immutable_json(ROOT / cfg["grading_only"], {"original_TRAIN_annotations": {
        str(r["id"]): originals[r["id"]]["annotation_sets"][0]["annotations"] for r in rows},
        "no_current_or_future_annotations_in_lawyer_payloads": True})
    selection = {"at": now(), "training_ids": cfg["training_ids"], "future_ids": [],
        "cohort_sha256": sha(cohort_path), "no_reselection_or_label_filter": True,
        "not_official_TEST_or_independent_learning_repeat": True}
    RunStore.immutable_json(ROOT / cfg["preselection"], selection)
    manifest_path = ROOT / cfg["ordinary_manifest"]
    manifest = read(manifest_path)
    assert sha(manifest["path"]) == manifest["pickle_sha256"]
    references = [cohort_path, archive_path, manifest_path, Path(manifest["path"]),
        ROOT / cfg["solver_system_reference"]]
    if cfg["method"] == "acquisition_interface":
        publication = ROOT / cfg["fixed_bank_publication"]
        assert sha(publication) == cfg["fixed_bank_publication_sha256"]
        assert cfg["diagnostic_source_ids"] == cfg["training_ids"][:16]
        assert cfg["planned_new_native_calls"] == 32 and cfg["planned_new_teacher_calls"] == 0
        references.append(publication)
    return selection, references


class AcquisitionStudy(Comparison):
    """Four real online updates; only native/check/teacher primitives inherited."""

    def __init__(self, config, *, run_id=None):
        self.cfg, self.config_path = read(config), Path(config).resolve()
        frozen = read(self.config_path.with_suffix(".frozen.json"))
        assert frozen["config_sha256"] == sha(self.config_path)
        self.bindings = frozen["files"].copy()
        self.run_id = safe_component(run_id or self.cfg["run_id"])
        self.out = ROOT / "runs" / self.run_id
        assert not self.out.exists(), "Never restart or overwrite a Run ID"
        packet = read(ROOT / self.cfg["input_packet"])
        self.labels, self.training = packet["public_hypotheses"], packet["documents"]
        assert [r["id"] for r in self.training] == self.cfg["training_ids"]
        assert all(set(r) == {"id", "text", "spans"} for r in self.training)
        self.system = read(ROOT / self.cfg["solver_system_reference"])["bundled_solver_system"]
        self.manifest = read(ROOT / self.cfg["ordinary_manifest"])
        assert sha(self.manifest["path"]) == self.manifest["pickle_sha256"]
        with Path(self.manifest["path"]).open("rb") as stream:
            self.model = pickle.load(stream)
        assert not self.model.programs and not self.model.queries
        self.native, self.teachers, self.own, self.first, self.units = [], [], [], [], []
        self.teacher_attempts, self.current_batch, self.stop = 0, 0, False
        self.bank, self.banks, self.proposals = [], {csha([]): []}, {}
        self.meter, self.summaries = WireClient(self.cfg["generation"]), []
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: setattr(self, "stop", True))

    def capacity(self, bank):
        assert len({s["id"] for s in bank}) == len(bank)
        for skill in bank:
            validate(skill, skill_record_schema(self.labels, guidance_schema=GUIDANCE_SCHEMA))
            assert len(skill["hypothesis_ids"]) == len(set(skill["hypothesis_ids"]))
        execute_library({"id": -1, "text": "", "spans": []}, bank)
        master = self.meter.token_count(text=compact(bank))
        scoped = self.meter.token_count(text=compact({"library": bank, "scope": {
            h: [s["id"] for s in bank if h in s["hypothesis_ids"]] for h in self.labels}}))
        assert max(master, scoped) <= self.cfg["library_token_hard_cap"], "Oversize publication retained; no pruning"
        return {"master": master, "with_public_scope_map": scoped}

    def payload(self, row, arm, bank):
        if row["id"] not in self.proposals:
            self.proposals[row["id"]] = evidence_proposals(self.model, row, self.labels)
        proposals = None if arm == "strong_empty" else self.proposals[row["id"]]
        actual = bank if arm == "skills" else []
        messages, schema, trace = source_messages(row, self.labels, self.system, actual, proposals)
        tokens = self.meter.token_count(messages=messages)
        assert tokens + self.cfg["generation"]["max_tokens"] <= self.cfg["generation"]["context_tokens"], "No clipping/shorter output/fallback"
        return {"document_id": row["id"], "arm": arm, "messages": messages, "schema": schema,
            "prompt_tokens": tokens, "bank": copy.deepcopy(actual), "bank_sha256": csha(actual),
            "fixed_ordinary_model_state": None if arm == "strong_empty" else self.manifest["state_sha256"],
            "actual_factual_trace": trace}

    def freeze_phase(self, stage, rows, arms):
        entries = []
        for index, row in enumerate(rows):
            order = arms[index % len(arms):] + arms[:index % len(arms)]
            for arm in order:
                p = self.payload(row, arm, self.bank)
                path = self.out / f"prospective/{stage}/{arm}/{row['id']}.json"
                RunStore.immutable_json(path, p)
                self.bindings[str(path)] = sha(path)
                entries.append({"stage": stage, "arm": arm, "document_id": row["id"], "path": str(path)})
        self.preserve_phase(stage)
        return entries

    def preserve_phase(self, stage):
        self.check()
        base = read(ROOT / self.cfg["prelaunch_backup_receipt"])
        assert base["all_members_verified"] and sha(base["archive"]) == base["archive_sha256"]
        target = ROOT.parent / "legal-skill-backups" / f"{self.run_id}-{stage}-all-bound-before-native.tar.gz"
        manifest = {str(Path(p).resolve().relative_to(ROOT)): digest for p, digest in self.bindings.items()}
        meta = compact({"at": now(), "files": manifest, "full_initial_source_and_git_backup": base,
            "same_vdb_not_offsite_weights_or_auth": True}).encode()
        with tarfile.open(target, "x:gz", compresslevel=2) as archive:
            for name in sorted(manifest):
                archive.add(ROOT / name, arcname="project/" + name, recursive=False)
            info = tarfile.TarInfo("phase_manifest.json")
            info.size = len(meta)
            archive.addfile(info, io.BytesIO(meta))
        expected = {"project/" + p: h for p, h in manifest.items()}
        expected["phase_manifest.json"] = hashlib.sha256(meta).hexdigest()
        observed = {}
        with tarfile.open(target, "r|gz") as archive:
            for member in archive:
                assert member.isfile() and member.name in expected
                stream, digest = archive.extractfile(member), hashlib.sha256()
                while chunk := stream.read(1024 * 1024):
                    digest.update(chunk)
                assert digest.hexdigest() == expected[member.name]
                observed[member.name] = digest.hexdigest()
        assert observed == expected
        RunStore.immutable_json(self.out / f"phase_backups/{stage}.json", {"at": now(),
            "archive": str(target), "archive_sha256": sha(target), "all_members_verified": True,
            "bound_files": len(manifest), "initial_full_git_and_source": base})

    def answer(self, entry):
        p = read(entry["path"])
        dest = self.out / f"native/{entry['stage']}/{entry['arm']}/{entry['document_id']}.final.native.json"
        response = self.call(dest, p["messages"], p["schema"], self.cfg["generation"]["max_tokens"], {
            "stage": entry["stage"], "arm": entry["arm"], "document_id": entry["document_id"],
            "call_role": "final", "input_payload": entry["path"], "bank_sha256": p["bank_sha256"]})
        assert response["finish_reason"] == "stop", "Incomplete native answer retained; no retry"
        validate(json.loads(response["content"]), p["schema"])
        self.bindings[str(dest)] = sha(dest)
        return {"stage": entry["stage"], "condition": entry["arm"], "document_id": entry["document_id"],
            "raw_artifact": str(dest), "payload": entry["path"], "response": response,
            "bank_sha256": p["bank_sha256"], "exact_same_run_cold_alias": False}

    def audit_and_grade(self, units):
        # Audit all real input/output wires BEFORE exposing this group's Gold.
        for u in units:
            p, raw = read(u["payload"]), read(u["raw_artifact"])
            assert len(raw["calls"]) == 1 and raw["transport_error"] is None
            request = raw["calls"][0]["request"]
            assert request["messages"] == p["messages"]
            assert request["response_format"]["json_schema"]["schema"] == p["schema"]
            assert raw["response"] == u["response"]
            validate(json.loads(u["response"]["content"]), p["schema"])
        gold = read(ROOT / self.cfg["grading_only"])["original_TRAIN_annotations"]
        sources = {r["id"]: r for r in self.training}
        result = []
        for u in units:
            d = u["document_id"]
            scored = original_score(u["response"], sources[d], gold[str(d)], list(self.labels))
            assert scored["public_valid"]
            result.append({**u, **scored})
        self.units.extend(result)
        return result

    def teacher_body(self, seen):
        gold = read(ROOT / self.cfg["grading_only"])["original_TRAIN_annotations"]
        receipts, observations = {}, []
        seen_ids = {r["id"] for r in seen}
        for u in self.own:
            assert u["document_id"] in seen_ids
            p = read(u["payload"])
            key = f"{u['bank_sha256']}:{u['document_id']}"
            events = p["actual_factual_trace"]["actual_source_executions"]
            if key in receipts:
                assert receipts[key] == events
            receipts[key] = events
            observations.append({"document_id": u["document_id"], "actual_stage": u["stage"],
                "actual_bank_sha256": u["bank_sha256"], "actual_native_raw_id": u["response"]["raw_id"],
                "actual_public_answer": json.loads(u["response"]["content"]),
                "actual_source_execution_ref": key, "actual_native_artifact_sha256": sha(u["raw_artifact"])})
        parent_refs, acquisition_feedback = {}, {}
        for row in seen:
            key = f"{csha(self.bank)}:{row['id']}"
            current = execute_library(row, self.bank)
            if key in receipts:
                assert receipts[key] == current
            receipts[key] = current
            parent_refs[str(row["id"])] = key
            feedback = {}
            for h in self.labels:
                returned = {i for s in self.bank if h in s["hypothesis_ids"]
                    for event in current[s["id"]] for role in ("matched", "neighbour", "preamble") for i in event[role]}
                annotation = gold[str(row["id"])][h]
                members = set(annotation["spans"])
                ordinary = {v["original_span_index"] for v in self.proposals[row["id"]]["by_hypothesis"][h]["candidates"]}
                feedback[h] = {"original_choice": annotation["choice"], "original_Gold_indices": annotation["spans"],
                    "current_query_returned_indices": sorted(returned), "Gold_not_returned": sorted(members - returned),
                    "Gold_already_in_fixed_ordinary_candidates": sorted(members & ordinary)}
            acquisition_feedback[str(row["id"])] = feedback
        return {"public_hypotheses": self.labels, "current_parent_library": self.bank,
            "complete_cumulative_original_TRAIN_sources_and_Gold": [{**r, "original_annotations": gold[str(r["id"])]} for r in seen],
            "observed_libraries": self.banks, "actual_own_public_observations": observations,
            "actual_source_execution_catalogue": receipts,
            "current_parent_source_replay_refs_not_new_native_responses": parent_refs,
            "current_parent_acquisition_member_feedback_not_legal_predictions": acquisition_feedback,
            "fixed_ordinary_model_manifest": self.manifest,
            "actual_visible_ordinary_candidates_by_source": {str(r["id"]): {
                h: self.proposals[r["id"]]["by_hypothesis"][h]["candidates"] for h in self.labels} for r in seen},
            "serving_notice": NOTICE, "runtime_stored_library_token_cap": self.cfg["library_token_hard_cap"],
            "exact_literal_matcher": {"lower_case_word_regex": _WORD.pattern,
                "ordered_suffixes": list(_SUFFIXES), "stem_only_if_input_length_at_least": 6,
                "minimum_remaining_stem_length": 4, "strip_first_allowed_suffix_only": True,
                "token_examples": {w: list(_tokens(w)) for w in (
                    "copy", "copies", "copied", "agreement", "agreements", "survive", "survives", "survival", "oral", "verbal")}},
            "parent_capacity": self.capacity(self.bank),
            "all_cumulative_own_successes_failures_retention_included_no_other_arm_answers": True}

    def update(self, seen):
        body = self.teacher_body(seen)
        name = f"update_b{self.current_batch}"
        path = self.out / f"learning_inputs/{name}.json"
        RunStore.immutable_json(path, body)
        self.bindings[str(path)] = sha(path)
        schema = differential_schema(self.labels, self.bank, [r["id"] for r in seen], guidance_schema=GUIDANCE_SCHEMA)
        value = self.teacher_call(name, TEACHER, body, schema)
        for p in (self.out / "teacher" / name).glob("*.json"):
            self.bindings[str(p)] = sha(p)
        published = apply_differential_publication(self.bank, value, self.labels, [r["id"] for r in seen], guidance_schema=GUIDANCE_SCHEMA)
        capacity = self.capacity(published)
        stats = publication_statistics(self.bank, value, published, capacity["master"])
        path = self.out / f"publications/b{self.current_batch}.json"
        RunStore.immutable_json(path, {"at": now(), "parent": self.bank, "delta": value,
            "publication": published, "capacity": capacity, "statistics": stats,
            "complete_cumulative_teaching_sources": [r["id"] for r in seen],
            "fixed_ordinary_model_state": self.manifest["state_sha256"],
            "no_fitting_effect_admission_rollback_or_native_answer_repair": True})
        self.bindings[str(path)] = sha(path)
        self.bank = published
        self.banks[csha(published)] = copy.deepcopy(published)
        return stats

    def execute(self):
        from legal_skill_guard.report import write_report

        self.check()
        RunStore.immutable_json(self.out / "declaration.json", {"at": now(), "run_id": self.run_id,
            "config": self.cfg, "frozen_bindings": self.bindings,
            "ordinary_model_held_fixed": self.manifest, "not_official_TEST_or_independent_replication": True})
        for batch in range(1, 5):
            self.current_batch = batch
            rows, seen = self.training[(batch - 1) * 8:batch * 8], self.training[:batch * 8]
            entries = self.freeze_phase(f"b{batch}_before", rows, ["strong_empty", "ordinary", "skills"])
            units = []
            for entry in entries:
                if batch == 1 and entry["arm"] == "skills":
                    continue
                units.append(self.answer(entry))
            if batch == 1:
                ordinary = {u["document_id"]: u for u in units if u["condition"] == "ordinary"}
                for e in entries:
                    if e["arm"] != "skills":
                        continue
                    old = ordinary[e["document_id"]]
                    p, q = read(e["path"]), read(old["payload"])
                    assert p["messages"] == q["messages"] and p["schema"] == q["schema"]
                    alias = {**old, "condition": "skills", "payload": e["path"], "exact_same_run_cold_alias": True}
                    RunStore.immutable_json(self.out / f"cold_aliases/{e['document_id']}.json", alias)
                    units.append(alias)
            before = self.audit_and_grade(units)
            self.first.extend(before)
            self.own.extend(u for u in before if u["condition"] == "skills")
            RunStore.immutable_json(self.out / f"b{batch}_before_complete.json", {"at": now(),
                "all24_logical_answers_saved_and_wires_checked": True, "units": before,
                "metrics": {a: points([u for u in before if u["condition"] == a]) for a in ("strong_empty", "ordinary", "skills")}})
            stats = self.update(seen)
            after_entries = self.freeze_phase(f"b{batch}_after_all_seen", seen, ["skills"])
            after = self.audit_and_grade([self.answer(e) for e in after_entries])
            self.own.extend(after)
            current_ids = {r["id"] for r in rows}
            summary = {"at": now(), "batch": batch, "source_ids": [r["id"] for r in rows],
                "before": {a: points([u for u in before if u["condition"] == a]) for a in ("strong_empty", "ordinary", "skills")},
                "after": {"skills": points([u for u in after if u["document_id"] in current_ids])},
                "retention_all_seen": points(after), "retention_unique_sources": len(seen),
                "strong_empty": points([u for u in before if u["condition"] == "strong_empty"]),
                "library_management": stats, "ordinary_model_state_unchanged": self.manifest["state_sha256"],
                "seen_after_is_external_skill_update_not_tool_refit_or_new_case_transfer": True}
            RunStore.immutable_json(self.out / f"b{batch}_all_seen_retention.json", {"at": now(), "units": after,
                "by_original_batch": {str(b): points([u for u in after if u["document_id"] in {
                    r["id"] for r in self.training[(b - 1) * 8:b * 8]}]) for b in range(1, batch + 1)}})
            RunStore.immutable_json(self.out / f"batch{batch}_summary.json", summary)
            self.summaries.append(summary)
            write_report(self.out)
        assert len(self.native) == self.cfg["planned_new_native_calls"] == 168
        assert len(self.teachers) == self.cfg["planned_new_teacher_calls"] == 4
        assert len({r["response"]["raw_id"] for r in self.native}) == 168
        self.check()
        complete = {"at": now(), "run_id": self.run_id, "actual_new_native_teacher_calls": [168, 4],
            "logical_observations": len(self.units), "explicit_same_run_cold_aliases": 8,
            "prequential_results": {a: points([u for u in self.first if u["condition"] == a]) for a in ("strong_empty", "ordinary", "skills")},
            "final_seen_retention": self.summaries[-1]["retention_all_seen"],
            "actual_native_usage": {k: sum(r["response"][k] for r in self.native) for k in ("prompt_tokens", "completion_tokens")},
            "actual_teacher_invocations": [t["invocation"] for t in self.teachers],
            "final_library": self.bank, "ordinary_model_manifest_unchanged": self.manifest,
            "independent_repeats_stronger_review_mature_comparison_and_official_TEST_still_pending": True}
        assert complete["logical_observations"] == 176
        RunStore.immutable_json(self.out / "completion.json", complete)
        RunStore.atomic_json(self.out / "progress.json", {"state": "completed", **complete})


class AcquisitionInterfaceStudy(AcquisitionStudy):
    """A held-bank causal check, explicitly not another online learning run."""

    def __init__(self, config, *, run_id=None):
        super().__init__(config, run_id=run_id)
        assert self.cfg["method"] == "acquisition_interface"
        path = ROOT / self.cfg["fixed_bank_publication"]
        assert sha(path) == self.cfg["fixed_bank_publication_sha256"]
        self.bank = read(path)["publication"]
        self.banks[csha(self.bank)] = copy.deepcopy(self.bank)
        assert self.cfg["diagnostic_source_ids"] == [r["id"] for r in self.training[:16]]
        assert self.cfg["planned_new_native_calls"] == 32
        assert self.cfg["planned_new_teacher_calls"] == 0

    def execute(self):
        self.check()
        self.capacity(self.bank)
        RunStore.immutable_json(self.out / "declaration.json", {"at": now(),
            "run_id": self.run_id, "config": self.cfg, "frozen_bindings": self.bindings,
            "fixed_published_bank_sha256": csha(self.bank),
            "all16_seen_sources_not_selected_failures_no_online_updates_or_TEST": True})
        entries = self.freeze_phase("held_K2_interface", self.training[:16], ["ordinary", "skills"])
        raw = [self.answer(entry) for entry in entries]
        scored = self.audit_and_grade(raw)
        RunStore.immutable_json(self.out / "complete32_native_and_original_scores.json", {"units": scored})
        results = {a: points([u for u in scored if u["condition"] == a]) for a in ("ordinary", "skills")}
        assert len(self.native) == 32 and not self.teachers and self.teacher_attempts == 0
        complete = {"at": now(), "run_id": self.run_id,
            "completed_native_calls": 32, "completed_teacher_calls": 0,
            "fixed_seen_interface_results": results,
            "by_original_training_batch": {str(b): {
                a: points([u for u in scored if u["condition"] == a and u["document_id"] in {
                    r["id"] for r in self.training[(b - 1) * 8:b * 8]}])
                for a in ("ordinary", "skills")} for b in (1, 2)},
            "actual_native_usage": {k: sum(r["response"][k] for r in self.native)
                for k in ("prompt_tokens", "completion_tokens")},
            "fixed_bank_publication": self.cfg["fixed_bank_publication"],
            "fixed_bank_sha256": csha(self.bank),
            "ordinary_model_manifest_unchanged": self.manifest,
            "not_new_case_transfer_online_evolution_independent_repeat_or_official_TEST": True}
        self.check()
        RunStore.immutable_json(self.out / "completion.json", complete)
        RunStore.atomic_json(self.out / "progress.json", {"state": "completed", **complete})
