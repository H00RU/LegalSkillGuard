"""Fixed ordinary/SCOPE updates over the complete current TRAIN prefix.

Four optimizer teacher stages per dataset/arm,scheduled before formal dispatch.
Ordinary learns three programs at B1/B4/B8;SCOPE has its direct seed plus two
decompositions at B1/B8 and two independently checked adversary slots at B4.
Every batch reselects on all measured original prefix mothers,never variants,
pure-reference labels,DEV or TEST. This is a budget-matched SCOPE adaptation.
"""
from copy import deepcopy
import json
from pathlib import Path

import jsonschema

from experiments.two_method_ordinary_control import SYSTEM as ORDINARY_SYSTEM
from experiments.two_method_scope_control import BLIND_SYSTEM, SYSTEM as SCOPE_SYSTEM, attribution_feedback
from legal_skill_guard.inference.codex_cli_client import (
    CODEX_TURN_INPUT_CHARACTER_LIMIT, render_structured_codex_prompt, strict_output_schema_issues)
from legal_skill_guard.paired_interfaces.control_answers import source_bundle
from legal_skill_guard.paired_interfaces.control_learning import (
    CRITIQUE_SCHEMA, direct_program, pack_teacher_payload, program_from_proposal, proposal_schema)
from legal_skill_guard.paired_interfaces.control_tools import module_assets
from legal_skill_guard.paired_interfaces.formal_actors import ProgramActor
from legal_skill_guard.paired_interfaces.formal_design import prefix
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.paired_interfaces.formal_tools import legal_tools
from legal_skill_guard.paired_interfaces.pilot_metrics import summarize
from legal_skill_guard.paired_interfaces.scope_learning import (
    admit_variants, adversary_schema, blind_verifier_payload, make_variant, revision_schema, verification_schema)
from legal_skill_guard.paired_interfaces.scope_replay import attribute
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.ledger import BudgetError
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


ORDINARY = 'ordinary_teacher_skills'
SCOPE = 'budget_matched_SCOPE_adaptation'
SCHEDULE = {ORDINARY: {1: ['source_policy_critique', 'program_0'], 4: ['program_1'], 8: ['program_2']},
            SCOPE: {1: ['first_decomposition'], 4: ['local_and_systemic_adversaries', 'separate_blind_verification'],
                    8: ['second_decomposition']}}
INVALID = {'predicates': [], 'extractors': [],
           'composition': 'def compose(inputs, predict, extractors):\n    return None\n'}


def protocol():
    return {'protocol': 'formal-prefix-ordinary-and-SCOPE-v1', 'teacher_schedule': SCHEDULE,
        'optimizer_teacher_requests_per_dataset_per_arm': 4,
        'optimizer_teacher_requests_per_arm': 20,
        'fixed_candidates_per_dataset': 3,
        'candidate_selection': 'all current development/calibration original mothers;native mother macro;earlier candidate ties',
        'source_only_reference_native_labels_or_primary_weak_reads': False,
        'internal_structure_DEV_TEST_feedback_for_updates': False,
        'SCOPE_adversaries': 'B4,one local and one systemic literal edit per dataset;fixed first measured prefix parent;no resampling',
        'verified_variant_information_shared_with_all_arms': True,
        'synthetic_variants_are_not_new_mothers_or_channel_calibration': True,
        'native_variant_scores_never_select_main_checkpoints': True,
        'counterfactual_label_edit_limit': 2, 'counterfactual_replays_per_execution_limit': 128,
        'comparison_cap': 'unique completed primary prefix observations,input+output;conservative context charge if unmetered',
        'old_paid_cache_counts_as_logical_information_not_new_physical_cost': True,
        'actual_physical_and_teacher_costs_always_reported': True,
        'official_SCOPE_reproduction_claimed': False, 'no_extra_gain_driven_candidates_or_rounds': True}


def system_prompt(arm):
    if arm not in (ORDINARY, SCOPE):
        raise ValueError('Use the fixed independent control arms')
    text = ORDINARY_SYSTEM if arm == ORDINARY else SCOPE_SYSTEM
    text = text.replace('primary pilot', 'formal primary prefix reads')
    text = text.replace('original D0', 'current measured TRAIN prefix').replace('original-D0', 'current measured TRAIN prefix')
    text = text.replace('fixed development mother', 'measured prefix mother')
    return text + '''
This is the formal eight-batch study. measured_examples are ALL currently seen
development/calibration TRAIN mothers,not the pilot D0 subset. Write SCOPE seed
rationales for exactly required_seed_rationale_sources. source_only_examples
contain only public sources and source-local reviews;they have NO native labels
or weak reads. Never infer absent source facts from a native answer. Shared
verified variants are auxiliary TRAIN information,not additional independent
mothers or the candidate-selection cohort. The public_context_residual_legal_module
is available identically to every arm. Preserve its unknowns and original law.
There are exactly three program candidates in total,no new candidate at other
batches. Complete source inputs and actual feedback must not be truncated.
'''


class ControlBatchTrainer:
    def __init__(self, root, *, arm, roles, public, registry, teacher, executor,
                 grade_provider, study_binding, shared_variants_root, actor_factory=None):
        if arm not in SCHEDULE:
            raise ValueError('An independent formal control arm is required')
        self.root, self.arm = Path(root), arm
        self.roles, self.public, self.registry = deepcopy(roles), public, registry
        self.teacher, self.executor, self.grade_provider = teacher, executor, grade_provider
        self.binding, self.shared = deepcopy(study_binding), Path(shared_variants_root)
        self.actor_factory = actor_factory or (lambda: ProgramActor(executor, self.root,
            max_calls=max(1, executor.token_cap)))
        self.datasets = sorted({r['dataset'] for r in roles})
        if set(public) != {r['source'] for r in roles} or not self.binding:
            raise ValueError('Bind the complete original TRAIN source manifest')
        immutable_json(self.root / 'optimizer_protocol.json', {'arm': arm, 'study_binding': self.binding, **protocol()})

    def _rows(self, batch, dataset, *, measured_only=False):
        return [r for r in prefix(self.roles, batch) if r['dataset'] == dataset
                and r['role'] != 'structure_evaluation'
                and (not measured_only or r['role'] in ('development', 'calibration'))]

    def _grades(self, source, batch, seal):
        if source not in {r['source'] for r in prefix(self.roles, batch)
                          if r['role'] in ('development', 'calibration')}:
            raise ValueError('Control feedback cannot include future,reference-only or structural native labels')
        return self.grade_provider(source, seal)

    def task(self, batch, dataset):
        measured, references = [], []
        for row in self._rows(batch, dataset):
            source = self.public[row['source']]
            cards = []
            for view in self.registry.actor.views(source):
                if view['pre_generation_domain_refusal']:
                    cards.append({'view': view['view'], 'public_F_domain_refusal': True,
                                  'reference_not_invented': True})
                else:
                    card, _, receipt = self.registry.review(source, view)
                    cards.append({'card': card, 'review_receipt': receipt,
                                  'not_independent_human_or_complete_legal_gold': True})
            tools, assets = legal_tools(source, source_bundle(source))
            example = {'source': source['key'], 'input': source_bundle(source), 'source_only_reviews': cards,
                'common_tool_contracts': {name: {k: v for k, v in tool.items() if k != 'invoke'} for name, tool in tools.items()},
                'common_legal_assets': assets}
            if row['role'] in ('development', 'calibration'):
                example['native_TRAIN_feedback'] = self._grades(source['key'], batch,
                    {'batch': batch, 'stage': 'control_source_supervision_after_primary_prefix', 'study_binding': self.binding})
                measured.append(example)
            else:
                references.append(example)
        variants = []
        path = self.shared / dataset / 'verified.json'
        if batch >= 4 and not (self.arm == SCOPE and batch == 4) and path.exists():
            variants = json.loads(path.read_text())['variants']
        return {'batch': batch, 'dataset': dataset, 'measured_examples': measured,
            'source_only_examples': references, 'required_seed_rationale_sources': [e['source'] for e in measured],
            'shared_legal_assets': module_assets(dataset), 'shared_verified_training_variants': variants,
            'selection_unit': 'original measured mother', 'main_method_generated_candidate_pool_supplied': False}

    def _teacher(self, batch, dataset, stage, payload, schema, ids, *, blind=False):
        if stage not in SCHEDULE[self.arm].get(batch, []):
            raise ValueError('An optimizer call falls outside the fixed four-stage schedule')
        if not ids or len(ids) != len(set(ids)) or not set(ids) <= {r['source'] for r in self._rows(batch, dataset)}:
            raise ValueError('Teacher source bindings must be current prefix TRAIN mothers')
        system = BLIND_SYSTEM if blind else system_prompt(self.arm)
        encoded = pack_teacher_payload(payload)
        user = json.dumps(encoded, ensure_ascii=False, sort_keys=True)
        if strict_output_schema_issues(schema) or len(render_structured_codex_prompt(system, user)) > CODEX_TURN_INPUT_CHARACTER_LIMIT:
            raise ValueError('Complete control teacher evidence/schema cannot be transported;no truncation')
        identity = self.teacher.ledger.run_id + ':optimizer:' + digest([batch, dataset, stage, system, user, schema, ids])
        folder = self.root / 'teacher_outputs' / dataset / stage
        immutable_json(folder / 'input.json', {'batch': batch, 'source_ids': ids, 'system_prompt': system,
                                              'payload': encoded, 'schema': schema, 'physical_call_id': identity})
        target = folder / 'result.json'
        if target.exists():
            with self.teacher.ledger.transaction() as db:
                old = db.execute('select status from calls where id=?', (identity,)).fetchone()
            if old is None or old[0] != 'completed':
                raise BudgetError('An optimizer cache has no matching completed teacher call')
        # Existing identities are still checked by the original frozen teacher
        # request hash;failed identities never retry or acquire a new round.
        response = self.teacher.propose(identity, source_ids=ids, system_prompt=system,
                                       user_prompt=user, output_schema=schema)
        record = {'physical_call_id': identity, 'value': response['value'], 'batch': batch,
                  'stage': stage, 'input_sha256': digest(encoded), 'blind': blind}
        immutable_json(target, record)
        return record

    def _history(self, dataset):
        values = []
        for path in sorted((self.root / 'candidates' / dataset).glob('*.json')):
            value = json.loads(path.read_text()); verify(value, 'candidate_sha256')
            if value['proposal'] is not None:
                with self.teacher.ledger.transaction() as db:
                    physical = db.execute('select status,result from calls where id=?',
                        (value['proposal']['physical_call_id'],)).fetchone()
                if physical is None or physical[0] != 'completed' or json.loads(physical[1])['value'] != value['proposal']['value']:
                    raise BudgetError('A learned candidate lost its actual completed teacher provenance')
            values.append(value)
        if [v['index'] for v in values] != list(range(len(values))) or len(values) > 3:
            raise ValueError('Only the original three ordered candidates are allowed')
        return values

    def _add(self, dataset, index, batch, response, task):
        failure = None
        try:
            if self.arm == SCOPE:
                rationales = response['value']['seed_rationales']
                if len(rationales) != len(task['required_seed_rationale_sources']) or {
                        r['source'] for r in rationales} != set(task['required_seed_rationale_sources']):
                    raise ValueError('SCOPE rationales must cover every measured prefix mother exactly once')
            program = program_from_proposal(response['value'], list(self.public))
        except (ValueError, KeyError, TypeError, SyntaxError, jsonschema.SchemaError, jsonschema.ValidationError) as error:
            program, failure = deepcopy(INVALID), type(error).__name__ + ': ' + str(error)
        result = sealed({'index': index, 'created_batch': batch, 'program': program,
            'proposal': response, 'validation_failure': failure, 'fixed_monolithic_seed': False}, 'candidate_sha256')
        immutable_json(self.root / 'candidates' / dataset / (str(index) + '.json'), result)

    def evaluate(self, candidate, batch, dataset, *, auxiliary=None):
        stage = 'B' + str(batch) + '_' + str(candidate['index'])
        directory = self.root / ('variant_feedback' if auxiliary is not None else 'evaluations') / dataset / stage
        rows = self._rows(batch, dataset, measured_only=True)
        sources = ([self.public[r['source']] for r in rows] if auxiliary is None else [v['source'] for v in auxiliary])
        actor = self.actor_factory()
        predictions = []
        for index, source in enumerate(sources):
            path = directory / 'predictions' / (digest([source, index]) + '.json')
            if path.exists():
                record = json.loads(path.read_text())
            else:
                result = actor.execute(candidate['program'], source, 'skill_actor')
                record = {'source': source['key'], 'public_sha256': digest(source), 'result': result}
                immutable_json(path, record)
            if record['source'] != source['key'] or record['public_sha256'] != digest(source):
                raise ValueError('A control prediction lost its source binding')
            if callable(getattr(actor, 'verify_program_result', None)):
                actor.verify_program_result(source, candidate['program'], 'skill_actor', record['result'])
            predictions.append(record)
        seal = sealed({'batch': batch, 'arm': self.arm, 'dataset': dataset,
            'candidate_sha256': candidate['candidate_sha256'], 'predictions_sha256': digest(predictions),
            'auxiliary_variants_not_main_selection': auxiliary is not None}, 'control_prediction_seal_sha256')
        immutable_json(directory / 'prediction_seal.json', seal)
        scores = []
        for index, (source, record) in enumerate(zip(sources, predictions)):
            annotation = (self._grades(source['key'], batch, seal) if auxiliary is None else
                          {k: {'answer': v} for k, v in auxiliary[index]['independent_answer'].items()})
            native = record['result']['native']
            if set(native) != {v['id'] for v in source['views']}:
                raise ValueError('A control prediction dropped native tasks')
            for view in source['views']:
                value = native[view['id']]
                grade = (grade_view(dataset, view, annotation[view['id']], value['answer'],
                    value.get('evidence_sentence_ids', [])) if value['handled'] else {'grade': 0.})
                # Two adversaries share a parent and are NOT two mothers.
                # Their score rows are auxiliary only,never passed to summarize.
                scores.append({'source': source['key'], 'view': view['id'],
                    'handled': value['handled'], 'grade': grade['grade'], 'auxiliary_index': index})
        result = {'batch': batch, 'index': candidate['index'], 'candidate_sha256': candidate['candidate_sha256'],
                  'predictions': predictions, 'source_scores': scores, 'prediction_seal': seal}
        if auxiliary is None:
            result.update(summarize(scores, {(s['key'], v['id']) for s in sources for v in s['views']}))
        else:
            result.update(auxiliary_not_independent_mothers=True, main_selection_score_computed=False)
        immutable_json(directory / 'result.json', result)
        return result

    def _attribution(self, candidate, evaluation, batch, dataset):
        directory = self.root / 'attribution' / dataset / ('B' + str(batch) + '_' + str(candidate['index']))
        path = directory / 'result.json'
        if path.exists():
            return attribution_feedback(json.loads(path.read_text()))
        reports = []
        for prediction in evaluation['predictions']:
            source = self.public[prediction['source']]
            result = prediction['result']; input_path = Path(result['execution_input_path'])
            tools, _ = legal_tools(source, source_bundle(source))
            report = attribute(json.loads(input_path.read_text()), result['execution'], legal_tools=tools)
            target = {task: value['answer'] for task, value in self._grades(source['key'], batch,
                       evaluation['prediction_seal']).items()}
            for intervention in report['interventions']:
                intervention['matches_recorded_target_exactly'] = bool(
                    intervention['supported'] and digest(intervention['answer']) == digest(target))
            reports.append({'source': source['key'], 'target_answer': target, **report})
        result = {'source_reports': reports, 'new_model_requests': 0,
                  'counterfactuals_are_not_actual_weak_observations': True}
        immutable_json(path, result)
        return attribution_feedback(result)

    def _variants(self, batch, dataset, task, history):
        parent_id = min(r['source'] for r in self._rows(batch, dataset, measured_only=True))
        parent = self.public[parent_id]; current = self._best(history)
        response = self._teacher(batch, dataset, 'local_and_systemic_adversaries',
            {**task, 'instruction': 'Generate exactly one local and one systemic literal-edit variant of this fixed parent. Use real traces and policy clauses. No resampling;never change law,questions,answer contracts,IDs or CNI sentence boundaries. Local must name an actual predicate. The intended answer_json covers all current native tasks.',
             'fixed_parent_source': parent_id, 'parent_input': source_bundle(parent),
             'current_best_program': current['candidate']['program'], 'search_history': history},
            adversary_schema(), [r['source'] for r in self._rows(batch, dataset)])
        variants, invalid = [], []
        specs = response['value']['variants']
        if len(specs) != 2 or {s['slot'] for s in specs} != {'local', 'systemic'}:
            invalid.append({'reason': 'Both unique fixed adversary slots are required'})
        else:
            for spec in specs:
                try:
                    if spec['slot'] == 'local' and spec['target_predicate'] not in {
                            p['id'] for p in current['candidate']['program']['predicates']}:
                        raise ValueError('Local adversary must target an actual predicate')
                    variants.append(make_variant(parent, spec, spec['slot']))
                except (ValueError, KeyError, TypeError, jsonschema.ValidationError) as error:
                    invalid.append({'specification': spec, 'error': type(error).__name__ + ': ' + str(error)})
        verification = self._teacher(batch, dataset, 'separate_blind_verification',
            blind_verifier_payload(variants, task['shared_legal_assets']), verification_schema(), [parent_id], blind=True)
        try:
            checked = admit_variants(variants, verification['value'])
        except (ValueError, KeyError, TypeError) as error:
            checked = [{**v, 'admitted': False, 'verification_error': str(error)} for v in variants]
        record = {'variants': checked, 'invalid': invalid, 'parent_source': parent_id,
            'verification_physical_call_id': verification['physical_call_id'],
            'available_to_all_formal_arms': True, 'new_independent_mothers': 0,
            'not_channel_reference_truth_or_primary_cohort_expansion': True}
        immutable_json(self.shared / dataset / 'verified.json', record)
        admitted = [v for v in checked if v['admitted']]
        if admitted:
            self.evaluate(current['candidate'], batch, dataset, auxiliary=admitted)

    @staticmethod
    def _best(history):
        return max(history, key=lambda h: (h['evaluation']['mother_macro'], -h['candidate']['index']))

    def completion_evidence(self):
        """Actual fixed teacher stages and all nine libraries,not a done flag."""
        identities = []
        for dataset in self.datasets:
            history = self._history(dataset)
            if len(history) != 3:
                raise ValueError('All three fixed control candidates must be preserved')
            for batch, stages in SCHEDULE[self.arm].items():
                for stage in stages:
                    result = json.loads((self.root / 'teacher_outputs' / dataset / stage / 'result.json').read_text())
                    if result['batch'] != batch or result['stage'] != stage:
                        raise ValueError('A teacher stage changed its fixed formal schedule')
                    with self.teacher.ledger.transaction() as db:
                        row = db.execute('select status,result from calls where id=?',
                                         (result['physical_call_id'],)).fetchone()
                    if row is None or row[0] != 'completed' or json.loads(row[1])['value'] != result['value']:
                        raise BudgetError('A formal teacher stage is not physically settled as recorded')
                    identities.append(result['physical_call_id'])
        with self.teacher.ledger.transaction() as db:
            actual = db.execute('select id,status from calls where role=? and id like ?',
                                ('teacher', self.teacher.ledger.run_id + ':%')).fetchall()
        if len(set(identities)) != len(identities) or sorted(actual) != sorted((i, 'completed') for i in identities):
            raise BudgetError('The optimizer phase must contain exactly its fixed teacher calls')
        libraries = {}
        for batch in range(9):
            value = json.loads((self.root / 'libraries' / ('B' + str(batch) + '.json')).read_text())
            verify(value, 'snapshot_sha256'); libraries[str(batch)] = value['snapshot_sha256']
        return {'arm': self.arm, 'actual_fixed_optimizer_teacher_calls': identities,
            'candidates_per_dataset': 3, 'libraries_B0_through_B8': libraries,
            'comparison_budget': self.executor.summary(), 'native_selection_cohort': 'original measured prefix mothers'}

    def batch(self, batch):
        if type(batch) is not int or not 0 <= batch <= 8:
            raise ValueError('Use the original B0..B8 prefix')
        target = self.root / 'libraries' / ('B' + str(batch) + '.json')
        if target.exists():
            library = json.loads(target.read_text()); verify(library, 'snapshot_sha256')
            if library['arm'] != self.arm or library['batch'] != batch or library['study_binding'] != self.binding:
                raise ValueError('A saved control library belongs to a different arm,prefix or study')
            return library
        if batch and not (self.root / 'libraries' / ('B' + str(batch - 1) + '.json')).exists():
            raise ValueError('Control training must preserve every original batch in order')
        if batch:
            readiness = self.registry.readiness(batch)
            if not readiness['ready']:
                raise ValueError('Current control prefix is missing source-only reviews before teacher dispatch')
            if self.executor.batch != batch:
                raise ValueError('Resolve this exact primary-prefix comparison budget first')
        if batch >= 4 and (self.arm == ORDINARY or batch > 4):
            if any(not (self.shared / dataset / 'verified.json').exists() for dataset in self.datasets):
                raise ValueError('Complete the fixed shared B4 variant information before later control updates')
        selections = {}
        for dataset in self.datasets:
            if batch == 0:
                selections[dataset] = {'program': direct_program(), 'fixed_monolithic_seed': True,
                                       'initialization_only': True, 'candidate_index': None}
                if self.arm == SCOPE:
                    seed = sealed({'index': 0, 'created_batch': 0, 'program': direct_program(),
                        'fixed_monolithic_seed': True, 'validation_failure': None, 'proposal': None}, 'candidate_sha256')
                    immutable_json(self.root / 'candidates' / dataset / '0.json', seed)
                continue
            task = self.task(batch, dataset)
            if not task['measured_examples']:
                raise ValueError('The fixed update schedule requires current measured mothers in each dataset')
            ids = [r['source'] for r in self._rows(batch, dataset)]
            history = []
            for candidate in self._history(dataset):
                history.append({'candidate': candidate, 'evaluation': self.evaluate(candidate, batch, dataset)})
            admitted = [v for v in task['shared_verified_training_variants'] if v['admitted']]
            variant_feedback = (self.evaluate(self._best(history)['candidate'], batch, dataset, auxiliary=admitted)
                                if history and admitted and batch in (4, 8) else None)
            if self.arm == ORDINARY and batch in (1, 4, 8):
                critique = (self._teacher(batch, dataset, 'source_policy_critique',
                    {**task, 'instruction': 'Derive source-supported policy rules and general implementation advice.'},
                    CRITIQUE_SCHEMA, ids) if batch == 1 else
                    json.loads((self.root / 'teacher_outputs' / dataset / 'source_policy_critique/result.json').read_text()))
                index = {1: 0, 4: 1, 8: 2}[batch]
                if not any(h['candidate']['index'] == index for h in history):
                    best = self._best(history) if history else None
                    response = self._teacher(batch, dataset, 'program_' + str(index),
                        {**task, 'instruction': 'Acquire or revise a general external skill using complete current TRAIN feedback. No extra candidates or rounds.',
                         'policy_critique': critique['value'], 'search_history': history,
                         'actual_shared_variant_feedback': variant_feedback,
                         'current_best_program': best['candidate']['program'] if best else None}, proposal_schema(), ids)
                    self._add(dataset, index, batch, response, task)
            elif self.arm == SCOPE:
                if batch in (1, 8):
                    index, stage = (1, 'first_decomposition') if batch == 1 else (2, 'second_decomposition')
                    if not any(h['candidate']['index'] == index for h in history):
                        best = self._best(history)
                        attribution = self._attribution(best['candidate'], best['evaluation'], batch, dataset)
                        response = self._teacher(batch, dataset, stage,
                            {**task, 'instruction': 'Analyze actual errors and correct contrasts,then produce the fixed next clause-grounded decomposition. Backtrack to the best original-prefix program,not the growing variant pool.',
                             'search_history': history, 'current_best_program': best['candidate']['program'],
                             'actual_shared_variant_feedback': variant_feedback,
                             'counterfactual_attribution': attribution}, revision_schema(), ids)
                        self._add(dataset, index, batch, response, task)
                elif batch == 4:
                    self._variants(batch, dataset, task, history)
            history = [{'candidate': c, 'evaluation': self.evaluate(c, batch, dataset)} for c in self._history(dataset)]
            best = self._best(history)
            selections[dataset] = {'program': best['candidate']['program'], 'candidate_index': best['candidate']['index'],
                'candidate_sha256': best['candidate']['candidate_sha256'],
                'fixed_monolithic_seed': best['candidate']['fixed_monolithic_seed'],
                'validation_failure': best['candidate']['validation_failure'],
                'current_prefix_mother_macro': best['evaluation']['mother_macro'],
                'current_prefix_measured_mothers': len(task['measured_examples'])}
            immutable_json(self.root / 'search_history' / dataset / ('B' + str(batch) + '.json'), history)
        library = sealed({'arm': self.arm, 'batch': batch, 'datasets': selections, 'study_binding': self.binding,
            'execution_max_neural_callbacks': max(1, self.executor.token_cap) if batch else 1,
            'optimizer_protocol_sha256': digest(protocol()),
            'comparison_budget': self.executor.summary() if batch else None,
            'pure_reference_or_evaluation_native_feedback_used': False,
            'main_method_learned_artifacts_or_candidate_pool_used': False}, 'snapshot_sha256')
        immutable_json(self.root / 'libraries' / ('B' + str(batch) + '.json'), library)
        return library
