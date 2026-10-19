"""Chronological case-backed skill evolution with exact historical evidence memory.

Reuses the original native model, ordinary tool, publication and scorer. This is
an experimental entrypoint, not a second runtime service or an answer adapter.
"""
from __future__ import annotations

import copy
import fcntl
import json
import sys
import traceback
from pathlib import Path

from experiments.decision_evidence_transfer import (
    EDIT_FEEDBACK_METHOD,
    RankedOnline,
    evidence_proposals,
)
from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.learning.catalog import encode_teacher_body
from legal_skill_guard.learning.decision_evidence import (
    materialize_witness_skills,
    training_nonmember_catalog,
    training_witness_catalog,
    witness_knowledge_view,
    witness_membership_example,
    witnessed_guidance_schema,
    witnessed_skill_payload,
)
from legal_skill_guard.learning.experiment import ROOT, now, points, read
from legal_skill_guard.learning.member_contract import annotated_sources
from legal_skill_guard.learning.member_learning import paired_effect
from legal_skill_guard.learning.packing import expand, keyed, table
from legal_skill_guard.learning.publication import (
    apply_differential_publication,
    differential_schema,
    publication_statistics,
)
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

TEACHER_SYSTEM = (
    "Learn reusable legal inspection skills backed by selected ORIGINAL historical TRAIN evidence "
    "demonstrations. This replaces rules-only memory, not the task or frozen lawyer. Every inference "
    "remains ONE frozen8B native reason/choice/original-integer-SPAN answer on the full current NDA "
    "and same ordinary tool. Use actual supplied sources, Gold, answers and candidate observations, "
    "including successes and harms. Old reference policies are identified historical versions, NOT "
    "invented executions of this new representation. Their prose and labels are fallible experience, "
    "not universal law. Publish explicit CREATE/UPDATE/DELETE/MERGE/NOOP against current_parent_library; "
    "unmentioned records stay verbatim. Each guidance has procedure, witness_refs and nonmember_refs. A witness_ref "
    "selects an eligible already-seen source/hypothesis pair WITHIN the skill's public scope. The host "
    "materializes ALL original evidence texts. A nonmember_ref selects a REAL extra citation from "
    "a supplied past originally non-neutral task, together with that task's COMPLETE correct evidence. "
    "The exact original quotation and membership come from actual observations, not a new legal judge. "
    "Original E/C/NM labels remain available to YOU for training and audit, but past-case NLI labels "
    "are NOT delivered as lawyer examples. Runtime examples teach annotated members and an optional "
    "unannotated actual citation, not an NLI answer prior. Unannotated does not mean legally false "
    "or universally forbidden, and a local excerpt cannot establish whole-contract NM. "
    "These are different past examples, not current facts or answers. "
    "NM deliberately has no snippet demonstration: a local excerpt cannot prove whole-contract absence. "
    "Use concrete legal contrasts and source functions to teach actor/action/object, modality, "
    "quantifiers, prohibitions, triggers, exceptions and complete responsive evidence. Preserve "
    "opposed boundaries rather than treating every restriction as NM. Lack of a matching example "
    "never implies a legal label. Avoid arbitrary literal shortcuts and generalizing one phrasing. "
    "Distill source-observable relation checks from the supplied full training labels into procedures, "
    "but never infer opposition just because a permission was not found or vice versa. "
    "Choose informative historical member/nonmember contrasts and selection boundaries; "
    "do not force a fixed skill/witness count, growth, one-per-hypothesis or positive-label-only list. "
    "Both reference lists may be empty when justified; do not force signed examples or a quota. "
    "No case answer tables, IDs, original indices, "
    "parties or dates in procedures. Exact past text is supplied by reference only. Same-source "
    "member AND nonmember examples are excluded by source identity AND content hash, even for training reanswers. "
    "All original current indices remain selectable; only the lawyer decides final labels/citations. "
    "Use the REAL supplied policy differences; do not invent comparisons or missing ablation arms. "
    "candidate_contexts stores exact actual source-reading inputs once; observation context references "
    "resolve to those same complete inputs without omitted candidates or scores. Original three-way "
    "accuracy, Gold-NN hard original-SPAN F1 and strict joint are unchanged. The actual lawyer system "
    "instructions, visible output contract and exact common native schema are supplied in "
    "lawyer_task_contracts; observation references identify what was REALLY executed. Follow that "
    "task, not a different legal-brief-writing objective. The target is COMPLETE original evidence "
    "membership, NOT the smallest sufficient proof. Independently responsive repeated provisions, "
    "definitions, introductions or qualifications can be separate original members; do not exclude "
    "them categorically as repetition, recitals or context. Conversely, adjacency or usefulness for "
    "reading alone never establishes membership. Learn both inclusion and exclusion conditions "
    "from the actual original members, missed_original_members and extra_actual_citations, each "
    "resolved to exact original text. Their counts and differences are the existing benchmark "
    "feedback, not a new semantic judge. Gold-NN evidence scoring includes ALL originally non-neutral "
    "queries even when the lawyer predicts the wrong relation or NotMentioned; label changes cannot "
    "make missed evidence disappear. Preserve supported/opposed relations while repairing partial "
    "evidence, and distinguish classification errors, missing members and extra citations. Do not "
    "mistake shorter answers, fewer citations, or NM gains alone for learned evidence acquisition. "
    "A reusable skill must provide observable source selection conditions, not 'cite the Gold' or "
    "a historical case answer. The COMPLETE MATERIALIZED "
    "knowledge bank, INCLUDING every procedure/scope, ALL positive evidence texts and complete false-citation "
    "contrasts, must fit4096 "
    "actual target8B tokens; aim2800. Internal audit hashes/IDs are stored/reported separately, not served "
    "knowledge. Each eligible example's exact standalone target8B token cost is supplied. These costs "
    "guide packing, not a promise of additive BPE costs; leave room for rules/structure. Reference IDs "
    "are NOT cheap substitutes for full texts. Do not "
    "blindly attach many long examples. No per-record character clipping or fixed template quota. "
    "All structurally valid edits publish without utility admission, best-bank selection, score-based "
    "retry, fallback or a second curator. Explain the actual source-supported change for each "
    "operation; do not invent successful execution or expose hidden reasoning. No tools/outside data. "
    "Return the exact differential JSON schema."
)


REFLECTION_SYSTEM = (
    "Analyze the ACTUAL public answers of a frozen legal model, before skill-library editing. "
    "This is training-only reflection, not inference, a new judge, or a generated corrected answer. "
    "Every current source is complete; original labels/member sets and matched empty/current-memory "
    "answers are supplied. The original task contract and actual source-reading inputs are retained. "
    "For EACH source, preserve what demonstrably worked and identify consequential label mistakes, "
    "missing members, extra citations, and concrete guidance misapplications. Report concise, "
    "public evidence findings and actionable source-reading changes, not hidden chain of thought. "
    "Resolve every cited index against that source. Never use a local excerpt to establish whole-source "
    "absence. Distinguish a complete original member set from a smallest sufficient proof. "
    "Inspect the REAL parent procedure AND historical examples: a correct-sounding instruction can "
    "still confuse this model. 'The rule already says this' is not an execution diagnosis. Where "
    "an instruction was ignored, specify a simpler observable action, an applicability distinction, "
    "a misleading comparison to remove, or explicitly say the cause remains unestablished. "
    "Related parent IDs are diagnostic associations, not experimentally isolated causal attribution. "
    "Do not infer that every memory/empty difference is a skill's causal effect or that every "
    "provided original label is universal legal doctrine. Preserve opposing examples and actual "
    "failures. No synthetic trajectories, future cases, proposed current answers, mandatory edits, "
    "case-specific rule tables, performance admission, best-bank rollback, or tools. The later "
    "curator, not this reflection, makes all library edits. A source with no supported improvement "
    "can have an empty findings list. Return the exact JSON schema."
)


def reflection_schema(rows, labels, bank):
    """Bind every supplied source and original coordinate, not teacher conclusions."""
    parent_ids = [s['id'] for s in bank]
    related = {'type': 'array', 'items': {'type': 'string'}}
    if parent_ids:
        related['items']['enum'] = parent_ids
    else:
        related['maxItems'] = 0
    cases = {}
    for row in rows:
        finding = {'type': 'object', 'additionalProperties': False,
            'required': ['hypothesis_id', 'observed_failure', 'source_original_indices',
                         'source_reading_action', 'related_parent_skill_ids'],
            'properties': {
                'hypothesis_id': {'type': 'string', 'enum': list(labels)},
                'observed_failure': {'type': 'string'},
                'source_original_indices': {'type': 'array', 'items': {
                    'type': 'integer', 'enum': list(range(len(row['spans'])))}},
                'source_reading_action': {'type': 'string'},
                'related_parent_skill_ids': copy.deepcopy(related)}}
        cases[str(row['id'])] = {'type': 'object', 'additionalProperties': False,
            'required': ['preserve_observed_successes', 'findings'], 'properties': {
                'preserve_observed_successes': {'type': 'string'},
                'findings': {'type': 'array', 'items': finding}}}
    return {'type': 'object', 'additionalProperties': False,
        'required': ['case_findings', 'cross_source_execution_lessons'], 'properties': {
            'case_findings': {'type': 'object', 'additionalProperties': False,
                'required': list(cases), 'properties': cases},
            'cross_source_execution_lessons': {'type': 'array', 'items': {'type': 'string'}}}}


class WitnessedExperience(RankedOnline):
    teaching_system = TEACHER_SYSTEM

    def new_fit_count(self):
        return len(self.fit_records)

    def observe(self, units):
        values, contexts, contracts = [], {}, {}
        sources = {r['id']: r for r in self.documents}
        for u in units:
            row = sources[u['document_id']]
            actual = read(self.out / f"inputs/{u['stage']}/{u['document_id']}/{u['condition']}.json")
            native_body = json.loads(actual['messages'][1]['content'])
            properties = actual['schema']['properties']
            common = next(iter(properties.values()))
            assert all(v == common for v in properties.values())
            assert set(properties) == set(actual['schema']['required'])
            contract = {
                'actual_system_messages': [m for m in actual['messages'] if m['role'] == 'system'],
                'actual_user_visible_output_contract': native_body['output_contract'],
                'actual_schema_root': {k:v for k,v in actual['schema'].items() if k != 'properties'},
                'actual_common_hypothesis_schema': common,
                'common_schema_applies_verbatim_to_every_required_hypothesis': True}
            contract_ref = csha(contract)
            contracts.setdefault(contract_ref, contract)
            delivery = read(self.out / f"deliveries/{u['stage']}/{u['document_id']}/{u['condition']}.json")
            context = delivery.pop("actual_visible_candidates")
            ref = csha(context)
            contexts.setdefault(ref, context)
            feedback = {}
            for q in u['queries']:
                gold = set(q['gold']['spans'])
                cited = set(q['prediction']['spans']) if q['prediction'] is not None else set()
                def excerpts(indices):
                    return table([{'original_span_index':i,
                        'literal_original_text':row['text'][slice(*row['spans'][i])]}
                        for i in sorted(indices)])
                feedback[q['hypothesis_id']] = {**copy.deepcopy(q),
                    'retained_original_member_indices': sorted(gold & cited),
                    'missed_original_members': excerpts(gold - cited),
                    'extra_actual_citations': excerpts(cited - gold)}
            values.append({
                "document_id": u["document_id"], "stage": u["stage"], "bank_sha256": u["bank_sha256"],
                "actual_ordinary_tool_source_ids": u["ordinary_tool_source_ids"],
                "actual_native_answer": u["parsed"], "public_valid": u["public_valid"],
                "invalid_native_content": None if u["public_valid"] else u["response"]["content"],
                "actual_delivery": delivery, "actual_candidate_context_ref": ref,
                "actual_lawyer_task_contract_ref": contract_ref,
                "original_component_feedback": keyed(feedback)})
        return {"encoding": "lossless_source_candidates_and_actual_task_contracts_v2",
                "candidate_contexts": contexts, "lawyer_task_contracts": contracts,
                "observations": table(values), "all_actual_candidates_scores_and_text_retained": True,
                "original_member_credit_is_exact_set_difference_not_a_new_judge": True}

    def publish(self, body, name):
        parent = copy.deepcopy(self.bank)
        catalog = body["eligible_original_non_neutral_historical_witnesses"]
        nonmembers = body['eligible_actual_false_citation_contrasts']
        window = expand(body["complete_already_revealed_original_source_window_and_Gold"])
        allowed = sorted({r["id"] for r in window} | {
            x['source_case_id'] for x in [*catalog.values(), *nonmembers.values()]})
        guidance = witnessed_guidance_schema(catalog, nonmembers)
        schema = differential_schema(self.labels, parent, allowed, guidance_schema=guidance)
        body["current_parent_library"] = parent
        body["current_materialized_parent_including_all_past_evidence_texts"] = self.materialized
        body["library_budget"] = {"current_materialized_target8B_tokens": self.memory_tokens,
                                  "target_tokens": 2800, "hard_tokens": 4096}
        self.progress("memory_budget", current_arm=name,
                      exact_CPU_tokenizer_cost_requests=len(catalog)+len(nonmembers))
        assert not set(catalog) & set(nonmembers)
        body["exact_standalone_example_target8B_token_costs"] = {
            ref: self.meter.token_count(text=json.dumps(witness_membership_example(w),
                ensure_ascii=False, separators=(",", ":")))
            for ref, w in {**catalog, **nonmembers}.items()}
        body["token_costs_are_existing_CPU_tokenizer_requests_not_native_generations"] = len(catalog)+len(nonmembers)
        self.record(f"learning_inputs/{name}.json", body)
        delta = self.teacher_call(name, self.teaching_system, encode_teacher_body(body), schema)
        bank = apply_differential_publication(parent, delta, self.labels, allowed, guidance_schema=guidance)
        materialized = materialize_witness_skills(bank, self.labels, catalog, nonmembers)
        tokens = self.meter.token_count(text=json.dumps(witness_knowledge_view(materialized),
            ensure_ascii=False, separators=(",", ":")))
        audit_storage_tokens = self.meter.token_count(text=json.dumps(materialized,
            ensure_ascii=False, separators=(",", ":")))
        assert tokens <= 4096, "Complete materialized knowledge exceeds capacity; no clipping, gate or old-bank substitute"
        stats = publication_statistics(parent, delta, bank, tokens)
        self.record(f"publications/{name}.json", {
            "at": now(), "parent": parent, "delta": delta, "publication": bank,
            "materialized_runtime_memory": materialized, "statistics": stats,
            "source_ids_actually_available_to_teacher": allowed,
            "all_valid_edits_used_without_utility_gate": True,
            "complete_model_delivered_knowledge_target8B_tokens": tokens,
            "internal_audit_storage_target8B_tokens_reported_separately": audit_storage_tokens,
            "exact_tokenizer_budget_requests_not_native_generations": len(catalog)+len(nonmembers)+2})
        self.bank, self.materialized, self.catalog, self.memory_tokens = bank, materialized, catalog, tokens
        self.nonmember_catalog = nonmembers
        self.publication_history.append(stats)

    def answer_mode(self, row, mode, proposals):
        role = "joint_empty" if mode == "empty" else "skills"
        messages, schema, delivery = witnessed_skill_payload(
            row, self.labels, proposals, self.cfg["bundled_solver_system"], self.materialized, mode=mode)
        native = self.generate(row, role, messages, schema)
        body = json.loads(messages[1]["content"])
        self.record(f"deliveries/{self.phase}/{row['id']}/{role}.json", {
            **delivery, "actual_native_raw_id": native["raw_id"], "materialized_bank_sha256": csha(self.materialized),
            "actual_source_read_selection": proposals["selection"],
            "actual_visible_candidates": {"hypotheses": body["hypotheses"],
                                          "candidate_original_text": body["candidate_original_text"]}})
        return self.logical(row, role, native)



class WitnessedOnline(WitnessedExperience):
    """Full chronological skill learning; shared trained read access is not skill gain."""

    teaching_system = TEACHER_SYSTEM + (
        " This is the MAIN chronological online run, not a four-arm pilot. Only actual same-case "
        "empty-versus-current-memory pairs and the previous actual before/after publication are supplied. "
        "The library starts EMPTY; the ordinary prior202 is shared tool supervision, not your skill "
        "experience. Every batch is taught exactly once and every valid edit executes on ALL current8. "
        "Cold identical-policy aliases are one physical answer, never independent exploration. "
        "The complete-source window is current8 plus previous8; older retained witnesses are exact "
        "past evidence, not fabricated fresh answers or full old documents. Publication feedback is "
        "actual same-tool before/after, including all harms; never treat it as guaranteed success. "
        "Reading access is deliberately recall-favouring and calibrated ONLY on prior TRAIN. These "
        "broader candidates are optional source leads, not evidence answers or legal confidence. "
        "Diagnose original NN members missed inside and outside the leads. Correct NM gains alone "
        "are NOT improved evidence acquisition. For correct relations with incomplete evidence, repair "
        "source inspection rather than simply demanding more explicit wording or switching to NM. "
        "Contrast your OWN selected witnesses with your procedure; do not synthesize a universal "
        "permission or exclusion inconsistent with the supplied counterexamples. If original labels "
        "have an ambiguous boundary, preserve the observed distinction without inventing universal law "
        "or deleting inconvenient source data. A separate training reflector has inspected every "
        "current source and actual matched answers before this edit. Its findings are evidence-based "
        "learning proposals, not verified causal claims or mandatory edits. Reconcile them with the "
        "full original feedback and actual previous publication effects. Repair operational delivery, "
        "not just legal-rule wording: deleting an overgeneralized example, splitting a confusing "
        "procedure or replacing an unexecutable instruction can be justified even when no new legal "
        "boundary was discovered. Do not equate 'already mentioned' with 'successfully executed'. "
        "Keep useful content; NOOP remains valid when no supported change is available. "
        "No manual case exceptions, fixed library size, efficacy "
        "admission, best-bank rollback or future-case knowledge."
    )

    def reflect_current_batch(self, body, rows):
        """ACE-inspired reflection before curation; no new lawyer call or inference layer."""
        current = {r['id'] for r in rows}
        window = expand(body['complete_already_revealed_original_source_window_and_Gold'])
        selected = [r for r in window if r['id'] in current]
        assert [r['id'] for r in selected] == [r['id'] for r in rows]
        packet = {
            'public_hypotheses': self.labels,
            'complete_current_original_sources_and_Gold': table(selected),
            'all_actual_current8_matched_empty_and_memory_observations':
                body['all_actual_current8_matched_empty_and_memory_observations'],
            'actual_current_batch_metrics': body['actual_current_batch_metrics'],
            'current_parent_library': copy.deepcopy(self.bank),
            'actual_materialized_parent': copy.deepcopy(self.materialized),
            'same_ordinary_tool_and_original_metrics': True,
            'all_current_sources_reflected_not_selected_by_success': True,
            'no_future_source_or_Gold_and_not_runtime_answer_correction': True}
        name = f'reflect_b{self.current_batch}'
        self.record(f'learning_inputs/{name}.json', packet)
        result = self.teacher_call(name, REFLECTION_SYSTEM, encode_teacher_body(packet),
                                   reflection_schema(rows, self.labels, self.bank))
        self.record(f'reflections/b{self.current_batch}.json', {
            'at': now(), 'actual_teacher_name': name,
            'source_ids': [r['id'] for r in rows], 'value': result,
            'diagnostic_associations_not_isolated_causal_proof': True,
            'not_served_to_lawyer_or_used_as_current_case_answer': True})
        return result

    def cold_alias(self, row, proposals, empty):
        assert not self.bank and not self.materialized and self.current_batch == 1
        messages, schema, delivery = witnessed_skill_payload(row, self.labels, proposals,
            self.cfg["bundled_solver_system"], [], mode="combined")
        original_input = self.out / f"inputs/b1_prequential_empty/{row['id']}/joint_empty.json"
        actual = read(original_input)
        assert actual == {"messages": messages, "schema": schema}
        native_path = self.out / f"native/b1_prequential_empty/{row['id']}/joint_empty.json"
        assert read(native_path)["response"] == empty["response"]
        self.record(f"inputs/{self.phase}/{row['id']}/skills.json", actual)
        body = json.loads(messages[1]["content"])
        self.record(f"deliveries/{self.phase}/{row['id']}/skills.json", {
            **delivery, "actual_native_raw_id": empty["response"]["raw_id"],
            "materialized_bank_sha256": csha([]), "actual_source_read_selection": proposals["selection"],
            "explicit_identical_policy_physical_alias_not_an_independent_rollout": True,
            "actual_visible_candidates": {"hypotheses": body["hypotheses"],
                                          "candidate_original_text": body["candidate_original_text"]}})
        self.record(f"aliases/cold_{row['id']}.json", {
            "at": now(), "source_native_path": str(native_path), "source_input_path": str(original_input),
            "input_and_schema_exactly_equal": True, "new_native_calls": 0,
            "original_raw_id_and_content_preserved": True})
        return self.logical(row, "skills", empty["response"])

    def leads(self, row):
        return evidence_proposals(self.prefix_model, row, self.labels,
                                  reading_threshold=self.reading_policy["threshold"])

    def execute(self):
        assert self.cfg["method"] == EDIT_FEEDBACK_METHOD and len(self.documents) == 128
        assert self.cfg['teacher_task_contract_version'] == 'reflection_before_signed_publication_v3'
        assert len(self.past) == len(self.prefix_ids) == 202 and not self.bank
        assert [r["id"] for r in self.documents] == self.cfg["episode_ids"]
        calibration = read(ROOT / self.cfg["reading_calibration_completion"])
        assert calibration["actual_completed_CPUfits"] == 5
        assert set(calibration["source_fold_assignment"]) == {str(i) for i in self.prefix_ids}
        assert calibration["reading_policy"]["beta"] == 2
        self.reading_policy = calibration["reading_policy"]
        self.materialized, self.catalog, self.memory_tokens, self.publication_history = [], {}, 0, []
        self.nonmember_catalog = {}
        self.fit_records, self.last_update = [], None
        self.record("declaration.json", {
            "at": now(), "config": self.cfg, "frozen_bindings": self.bindings.copy(),
            "planned_new_native_teacher_CPUfits": [376,32,16], "planned_logical_answers": 384,
            "teacher_roles": {"training_batch_reflections": 16, "library_curations": 16},
            "reflection_not_an_inference_layer_or_skill_efficacy_gate": True,
            "only8_exact_cold_aliases_not_independent_exploration": True,
            "shared_prior202_calibration_and_growing_tool_not_skill_gain": True,
            "reading_policy": self.reading_policy, "independent_empty_memory_start": True,
            "prior_training_development_exposures_not_an_independent_algorithmic_repeat": True,
            "same_source_witnesses_excluded_even_for_training_reanswers": True,
            "official_DEV_TEST_not_used_for_tuning": True})
        summaries = []
        for batch in range(1,17):
            self.current_batch = batch
            rows, start = self.documents[(batch-1)*8:batch*8], len(self.answers)
            assert len(self.prefix_ids) == 202+(batch-1)*8
            for index, row in enumerate(rows):
                proposals = self.leads(row)
                if batch == 1:
                    self.phase = "b1_prequential_empty"
                    empty = self.answer_mode(row, "empty", proposals)
                    self.phase = "b1_prequential_combined"
                    self.cold_alias(row, proposals, empty)
                else:
                    for mode in (("empty","combined") if index%2 == 0 else ("combined","empty")):
                        self.phase = f"b{batch}_prequential_" + mode
                        self.answer_mode(row, mode, proposals)
            fresh = self.score(self.answers[start:])
            self.units.extend(fresh)
            groups = {m: [u for u in fresh if u["stage"].endswith("_"+m)] for m in ("empty","combined")}
            assert all(len(v) == 8 for v in groups.values())
            metrics = {m: points(v) for m,v in groups.items()}
            effect = paired_effect(groups["empty"],groups["combined"],seed=2026101980+batch,replicates=5000)
            summary = {"at": now(), "batch": batch, "new_source_ids": [r["id"] for r in rows],
                "metrics": metrics, "same_case_skill_effect": effect,
                "current_bank_sha256": csha(self.bank), "current_skill_count": len(self.bank),
                "knowledge_tokens": self.memory_tokens, "shared_ordinary_source_ids": self.prefix_ids,
                "shared_reading_policy": self.reading_policy,
                "all_current8_both_views_generated_before_current_Gold": True}
            self.record(f"batch_summaries/b{batch}_before.json", summary)
            summaries.append(summary)
            print(json.dumps({"batch": batch, "metrics": metrics}), flush=True)
            gold = read(ROOT / self.cfg["grading_only"])["original_TRAIN_annotations"]
            seen = self.documents[:batch*8]
            window = seen[-16:]
            catalog = training_witness_catalog(window, self.labels, gold)
            nonmembers = training_nonmember_catalog(window, self.labels, self.units)
            for skill in self.bank:
                for ref in skill["guidance"]["witness_refs"]:
                    catalog.setdefault(ref, self.catalog[ref])
                for ref in skill['guidance']['nonmember_refs']:
                    nonmembers.setdefault(ref, self.nonmember_catalog[ref])
            body = {"public_hypotheses": self.labels,
                "complete_already_revealed_original_source_window_and_Gold": annotated_sources(window,self.labels,gold),
                "eligible_original_non_neutral_historical_witnesses": catalog,
                'eligible_actual_false_citation_contrasts': nonmembers,
                "all_actual_current8_matched_empty_and_memory_observations": self.observe(fresh),
                "actual_current_batch_metrics": metrics,
                "current_shared_ordinary_tool_source_ids": self.prefix_ids,
                "shared_training_only_reading_policy_not_skill_gain": self.reading_policy,
                "cold_policy_aliases_are_one_physical_answer_not_independent_sampling": batch == 1,
                "previous_actual_complete8_publication_experience": self.last_update,
                "no_future_source_text_answers_annotations_or_official_DEV_TEST": True,
                "outside_window_old_sources_not_reanswered_no_all_seen_retention_claim": True}
            parent, before_materialized = copy.deepcopy(self.bank), copy.deepcopy(self.materialized)
            name = f"online_b{batch}"
            body['actual_training_reflection_before_curation'] = self.reflect_current_batch(body, rows)
            self.publish(body, name)
            start_after, self.phase = len(self.answers), f"b{batch}_after_seen_combined"
            for row in rows:
                self.answer_mode(row, "combined", self.leads(row))
            after = self.score(self.answers[start_after:])
            self.units.extend(after)
            update = paired_effect(groups["combined"],after,seed=2026102000+batch,replicates=5000)
            self.record(f"update_effects/b{batch}.json", {
                "at": now(), "effect": update, "same_current_ordinary_tool_and_reading_policy": True,
                "same_source_witness_exclusion_on_all8_training_reanswers": True,
                "training_effect_not_new_source_transfer_or_skill_admission": True})
            publication = read(self.out/f"publications/{name}.json")
            self.last_update = {"parent_library": parent, "delta": publication["delta"],
                "published_library": self.bank, "parent_materialized_memory": before_materialized,
                "all8_actual_before_and_after": self.observe(groups["combined"]+after),
                "same_ordinary_source_ids": self.prefix_ids, "reading_policy": self.reading_policy,
                "original_training_effect": update, "not_a_selected_successful_update": True}
            self.record(f"batch_summaries/b{batch}_complete.json", {**summary,
                "publication_statistics": self.publication_history[-1], "actual_training_update_effect": update})
            self.fit_prefix(seen)
        assert len(self.native) == 376 and len(self.answers) == 384
        assert len(self.teachers) == 32 and len(self.fit_records) == 16 and len(self.prefix_ids) == 330
        groups = {m: [u for u in self.units if "_prequential_" in u["stage"] and u["stage"].endswith("_"+m)]
                  for m in ("empty","combined")}
        assert all(len(v) == 128 for v in groups.values())
        result = {"at": now(), "run_id": self.run_id, "all128_prequential_metrics": {m:points(v) for m,v in groups.items()},
            "all128_source_paired_effect": paired_effect(groups["empty"],groups["combined"],seed=2026102020,replicates=5000),
            "batch_summaries": summaries, "actual_new_native_teacher_CPUfits": [376,32,16],
            "actual_teacher_roles": {"training_batch_reflections": 16, "library_curations": 16},
            "inherited_shared_read_calibration_CPUfits": 5,
            "prior_development_family_native_teacher_CPUfits": self.cfg["prior_development_family_native_teacher_CPUfits"],
            "total_this_development_family_native_teacher_CPUfits": [a+b for a,b in zip(
                [376,32,16],self.cfg["prior_development_family_native_teacher_CPUfits"],strict=True)],
            "final_bank": self.bank, "final_materialized_memory": self.materialized,
            "final_common_ordinary_source_ids": self.prefix_ids, "actual_ordinary_fits": self.fit_records,
            "publication_statistics": self.publication_history, "units": self.units,
            "all_adverse_cases_invalids_and_original_denominators_preserved": True,
            "not_independent_algorithmic_repeat_mature_baseline_superiority_or_official_TEST": True}
        self.record("completion.json", result)
        RunStore.atomic_json(self.out/"progress.json", {
            "at": now(), "state": "completed", "run_id": self.run_id,
            "completed_native_calls": 376, "completed_teacher_calls": 32, "actual_new_CPUfits": 16,
            "all128_prequential_metrics": result["all128_prequential_metrics"]})
        print(json.dumps({"completed": self.run_id, "metrics": result["all128_prequential_metrics"]}),flush=True)


def main():
    with (ROOT / "artifacts/gpu_generation.lock").open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        config = Path(sys.argv[1])
        kind = read(config)["study_kind"]
        if kind != "full128_reflective_signed_member_skill_online":
            raise ValueError("Only the full online protocol is active; finite historical studies remain in Git/archives")
        study = WitnessedOnline(config)
        try:
            study.execute()
        except BaseException as error:
            failure = {"at": now(), "state": "failed", "error": repr(error), "traceback": traceback.format_exc(),
                "actual_native_teacher_CPUfits": [len(study.native),len(study.teachers),study.new_fit_count()],
                "inherited_failed_native_teacher_CPUfits": study.cfg.get("inherited_failed_native_teacher_CPUfits", [0,0,0]),
                "no_retry_answer_repair_fallback_gate_or_selected_bank": True}
            study.record("failure.json", failure)
            RunStore.atomic_json(study.out / "progress.json", failure)
            raise


if __name__ == "__main__":
    main()
