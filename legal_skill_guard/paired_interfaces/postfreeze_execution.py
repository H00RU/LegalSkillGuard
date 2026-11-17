"""Execute only the fixed,sealed post-B8 contribution diagnostics.

The main TEST subset is reused for presealed ablations,not renamed or repaired.
MOAR-style current-TRAIN scoring happens after ALL fixed-pool reads are saved.
The primary/M2/noise choices have already been sealed without those outcomes.
"""
from collections import defaultdict
import json
from pathlib import Path

from legal_skill_guard.paired_interfaces.formal_design import ARMS
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.paired_interfaces.pilot_metrics import summarize
from legal_skill_guard.paired_interfaces.postfreeze_protocol import (
    ABLATIONS, TRANSFER_SYSTEMS, measured_MOAR_choices, seal)
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


class PostfreezeExecution:
    def __init__(self, root, *, roles, source_lock, public_train, public_test,
                 interface_trainer, ablation_asset_manifest, ablation_asset_manifest_sha256,
                 actor_factory, grade_provider, source_binding_check):
        self.root = Path(root); self.roles, self.source_lock = roles, source_lock
        self.train, self.test = public_train, {s['key']: s for s in public_test}
        self.interfaces = interface_trainer
        self.assets, self.assets_sha = ablation_asset_manifest, ablation_asset_manifest_sha256
        self.actor_factory, self.grade_provider, self.check = actor_factory, grade_provider, source_binding_check
        self.plan, self.libraries = None, None

    def prepare(self, libraries, training_seal):
        self.check()
        b8 = {arm: libraries[arm, 8] for arm in ARMS}
        raw = json.loads((self.interfaces.root / 'B8/shared_verified_raw_evidence.json').read_text())
        self.plan = seal(self.root, roles=self.roles, source_lock=self.source_lock, libraries=b8,
            training_seal=training_seal, public_train=self.train, interface_actor=self.interfaces.actor,
            paired_records=raw['pairs'], ablation_asset_manifest=self.assets,
            ablation_asset_manifest_sha256=self.assets_sha)
        self.libraries = b8
        return self.plan

    def _grade_native(self, source, native, annotation):
        if set(native) != {v['id'] for v in source['views']}:
            raise ValueError('Every diagnostic native task must remain,including unresolved outputs')
        rows = []
        for view in source['views']:
            value = native[view['id']]
            score = (grade_view(source['dataset'], view, annotation[view['id']], value['answer'],
                value.get('evidence_sentence_ids', [])) if value['handled'] else {'grade': 0., 'unresolved_or_failed': True})
            rows.append({'source': source['key'], 'dataset': source['dataset'], 'view': view['id'],
                         'handled': value['handled'], 'grade': score['grade'], 'native_metrics': score})
        return rows

    def _cohort(self, label, phase, partition, sources, libraries, main_freeze):
        self.check(); directory = self.root / 'diagnostics' / phase / label
        purpose = 'skill_actor' if partition == 'train' else 'skill_test'
        actor_by_arm, predictions = {}, []
        for source in sources:
            library = libraries[source['dataset']]
            arm = library['arm']
            if arm not in actor_by_arm:
                actor_by_arm[arm] = self.actor_factory(arm, partition, main_freeze)
            actor = actor_by_arm[arm]; path = directory / 'predictions' / (digest(source['key']) + '.json')
            if path.exists():
                value = json.loads(path.read_text())
            else:
                value = {'source': source['key'], 'public_sha256': digest(source),
                         'library_sha256': library['snapshot_sha256'], 'result': actor(source, library, purpose)}
                immutable_json(path, value)
            if value['public_sha256'] != digest(source) or value['library_sha256'] != library['snapshot_sha256']:
                raise ValueError('A diagnostic prediction belongs to another frozen source/library')
            actor.verify_saved(source, library, purpose, value['result'])
            predictions.append(value)
        prediction_seal = sealed({'diagnostic_seal_sha256': self.plan['diagnostic_seal_sha256'],
            'phase': phase, 'label': label, 'partition': partition,
            'source_cohort': [s['key'] for s in sources], 'predictions_sha256': digest(predictions),
            'all_predictions_saved_before_this_grading': True}, 'diagnostic_prediction_seal_sha256')
        immutable_json(directory / 'prediction_seal.json', prediction_seal)
        scores = []
        for source, prediction in zip(sources, predictions):
            annotation = self.grade_provider(partition, source['key'], prediction_seal)
            scores.extend(self._grade_native(source, prediction['result']['native'], annotation))
        reports = {}
        for dataset in sorted({s['dataset'] for s in sources}):
            expected = {(s['key'], v['id']) for s in sources if s['dataset'] == dataset for v in s['views']}
            reports[dataset] = summarize([r for r in scores if r['dataset'] == dataset], expected)
        result = {'phase': phase, 'label': label, 'partition': partition, 'source_scores': scores,
                  'datasets': reports, 'prediction_seal': prediction_seal, 'independent_trial_claim_from_cache': False}
        immutable_json(directory / 'scores.json', result)
        return result

    def _transfer(self, main_freeze):
        decisions = self.plan['transfer_decisions']
        directory = self.root / 'diagnostics/transfer'
        actor = self.actor_factory('M1_M2', 'train', main_freeze)
        by_source = defaultdict(dict)
        for decision in decisions: by_source[decision['source']][decision['view']] = decision
        reads = []
        for source_id in self.plan['design']['transfer_TRAIN_sources']:
            self.check(); source = self.train[source_id]
            for view in actor.views(source):
                decision = by_source[source_id][view['view']]
                if digest(source) != decision['public_source_sha256'] or view['native_tasks'] != decision['native_tasks']:
                    raise ValueError('A transfer target changed after its choices were sealed')
                if [p['name'] for p in view['plans']] != decision['fixed_candidate_order']:
                    raise ValueError('The measured MOAR pool cannot expand')
                for plan in view['plans']:
                    value = actor.measure(source, view, plan, 'skill_actor')
                    if set(value['native']) != set(decision['native_tasks']):
                        raise ValueError('A measured probe dropped native tasks')
                    reads.append({'source': source_id, 'view': view['view'], 'plan': plan['name'], 'read': value})
        immutable_json(directory / 'all_fixed_pool_predictions.json', reads)
        keys = sorted((r['source'], r['view'], r['plan'], task) for r in reads for task in r['read']['native'])
        prediction_seal = sealed({'diagnostic_seal_sha256': self.plan['diagnostic_seal_sha256'],
            'phase': 'transfer', 'partition': 'train', 'source_cohort': self.plan['design']['transfer_TRAIN_sources'],
            'predictions_sha256': digest(reads), 'native_candidate_slots': len(keys),
            'native_slot_keys_sha256': digest(keys), 'diagnostic_decisions_sha256': digest(decisions),
            'all_fixed_pool_predictions_saved_before_native_grading': True}, 'probe_prediction_seal_sha256')
        immutable_json(directory / 'prediction_seal.json', prediction_seal)
        annotations, scores = {}, []
        native_views = {source: {v['id']: v for v in self.train[source]['views']} for source in by_source}
        for row in reads:
            source = self.train[row['source']]
            if source['key'] not in annotations:
                annotations[source['key']] = self.grade_provider('train', source['key'], prediction_seal)
            for task, value in row['read']['native'].items():
                view = native_views[source['key']][task]
                score = (grade_view(source['dataset'], view, annotations[source['key']][task], value['answer'],
                    value.get('evidence_sentence_ids', [])) if value['handled'] else {'grade': 0., 'unresolved_or_failed': True})
                scores.append({'source': source['key'], 'dataset': source['dataset'], 'opaque_view': row['view'],
                    'view': task, 'plan': row['plan'], 'handled': value['handled'], 'grade': score['grade'], 'native_metrics': score})
        immutable_json(directory / 'all_fixed_candidate_native_scores.json', scores)
        moar = measured_MOAR_choices(scores, decisions, prediction_seal)
        immutable_json(directory / 'measured_MOAR_choices.json', moar)
        moar_lookup = {(r['source'], r['view']): r['plan'] for r in moar}
        selected, reports = {}, {}
        for system in TRANSFER_SYSTEMS:
            choices = {(d['source'], d['view']): (moar_lookup[d['source'], d['view']] if system == TRANSFER_SYSTEMS[-1]
                        else d['frozen_choices'][system]['plan']) for d in decisions}
            rows = [r for r in scores if r['plan'] == choices[r['source'], r['opaque_view']]]
            selected[system] = rows
            reports[system] = {}
            for dataset in sorted({r['dataset'] for r in rows}):
                sources = [self.train[s] for s in by_source if self.train[s]['dataset'] == dataset]
                expected = {(s['key'], v['id']) for s in sources for v in s['views']}
                reports[system][dataset] = summarize([r for r in rows if r['dataset'] == dataset], expected)
        physical = {r['read']['physical_call_id']: r['read']['usage'] for r in reads}
        comparisons = []
        for decision in decisions:
            matching = [r for r in scores if (r['source'], r['opaque_view']) == (decision['source'], decision['view'])]
            means = {plan: sum(r['grade'] for r in matching if r['plan'] == plan) / len(decision['native_tasks'])
                     for plan in decision['fixed_candidate_order']}
            failures = {plan: float(any(not r['handled'] or r['grade'] != 1.
                                       for r in matching if r['plan'] == plan)) for plan in means}
            for system in TRANSFER_SYSTEMS:
                choice = ({'plan': moar_lookup[decision['source'], decision['view']]}
                          if system == TRANSFER_SYSTEMS[-1] else decision['frozen_choices'][system])
                plan = choice['plan']; prediction = choice.get('risks', {}).get(plan, {})
                interval = prediction.get('interval', prediction.get('empirical_risk_interval'))
                observed = failures[plan]
                comparisons.append({'source': decision['source'], 'dataset': decision['dataset'], 'view': decision['view'],
                    'system': system, 'plan': plan, 'native_tasks': len(decision['native_tasks']),
                    'observed_candidate_native_means': means,
                    'selection_native_regret': max(means.values()) - means[plan],
                    'observed_full_native_signature_failure': observed,
                    'conditional_model_predicted_failure_interval': interval,
                    'distance_to_single_observed_outcome': (max(interval[0] - observed, 0., observed - interval[1])
                                                          if interval is not None else None),
                    'single_outcome_distance_is_not_probability_coverage': True,
                    'reference_F_loss_model_is_not_certified_native_gold': True})
        result = {'system_native_metrics': reports, 'selected_native_rows': selected,
            'per_source_consumer_selection_and_prediction_diagnostics': comparisons,
            'actual_probe_physical_response_usage': physical,
            'logical_target_candidate_observations': len(reads), 'source_mothers': len(by_source),
            'physical_response_reuse_is_not_a_new_trial_or_cash_saving_estimate': True,
            'actual_target_native_feedback_used_only_by_MOAR_choice': True,
            'primary_M2_replay_and_noise_choices_not_repaired': True,
            'single_case_native_outcomes_are_not_confidence_interval_coverage_estimates': True,
            'natural_structure_novelty_and_method_advantage_not_established_by_execution': True}
        immutable_json(directory / 'report.json', result)
        return result

    def run(self, main_freeze):
        if self.plan is None or self.libraries is None:
            raise ValueError('Diagnostics require their original pre-evaluation choice seal')
        verify(self.plan, 'diagnostic_seal_sha256'); verify(main_freeze, 'freeze_sha256')
        if main_freeze['training_B8_seal']['training_seal_sha256'] != self.plan['training_seal_sha256']:
            raise ValueError('The diagnostics belong to another primary training freeze')
        transfer = self._transfer(main_freeze)
        internal_sources = [self.train[s] for s in self.plan['design']['internal_structural_TRAIN_sources']]
        internal = {arm: self._cohort(arm, 'internal_structure', 'train', internal_sources,
                    {s['dataset']: self.libraries[arm] for s in internal_sources}, main_freeze) for arm in ARMS}
        test_sources = [self.test[s] for s in self.plan['design']['M1_ablation_fixed_TEST_sources']]
        ablations = {variant: self._cohort(variant, 'M1_ablation', 'test', test_sources,
            {s['dataset']: self.plan['ablation_libraries'][variant] for s in test_sources}, main_freeze)
            for variant in ABLATIONS}
        terminal = {'status': 'fixed_postfreeze_contribution_diagnostics_evaluated',
            'diagnostic_seal_sha256': self.plan['diagnostic_seal_sha256'],
            'transfer_mothers': transfer['source_mothers'], 'internal_structure_systems': len(internal),
            'M1_ablation_variants': len(ablations), 'M1_ablation_TEST_cells': sum(len(r['datasets']) for r in ablations.values()),
            'no_primary_repair_from_any_diagnostic_label': True,
            'two_independent_contributions_or_complete_goal_established': False}
        immutable_json(self.root / 'diagnostics/terminal.json', terminal)
        return terminal
