"""Source-reviewed,role-preserving batches for the formal interface learners.

Only development/calibration sources are read and natively graded. Pure
reference TRAIN worlds receive no primary weak reads or answer labels. Domain
refusals are declared from public law context before generation; other missing
reviews or physical failures stop the batch rather than disappearing from it.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from legal_skill_guard.paired_interfaces import asset_graph_pairs, rich_graph_pairs
from legal_skill_guard.paired_interfaces.empirical_channel import graph_record
from legal_skill_guard.paired_interfaces.formal_design import prefix
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.paired_interfaces.formal_learning import arm_snapshot, fit_prefix, pair_record
from legal_skill_guard.paired_interfaces.graph_evidence import normalize_graph_evidence
from legal_skill_guard.paired_interfaces.observed_abstention import canonical_pair
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


class MissingSourceReviews(ValueError):
    pass


class ReferenceRegistry:
    """An explicit manifest selects reviews;glob order never selects a revision."""
    def __init__(self, project_root, manifest, roles, public, interface_actor):
        self.root, self.manifest = Path(project_root).resolve(), deepcopy(manifest)
        self.roles = {r['source']: r for r in roles}
        self.public, self.actor = public, interface_actor
        if len(self.roles) != len(roles) or set(self.roles) != set(public):
            raise ValueError('Reference registry must bind the exact original formal TRAIN mothers')
        verify(manifest, 'registry_sha256')
        if manifest['source_public_sha256'] != {key: digest(value) for key, value in public.items()}:
            raise ValueError('The registry lost its exact per-source public bindings')
        if (manifest['formal_roles_sha256'] != digest(roles)
                or manifest['production_alignment_source_sha256'] != interface_actor.pipeline_binding
                or manifest['executor'] != interface_actor.executor.config):
            raise ValueError('The registry roles,production pipeline or frozen executor binding changed')
        for name, expected in manifest['production_alignment_source_sha256'].items():
            path = (self.root / name).resolve()
            if (not path.is_relative_to(self.root)
                    or hashlib.sha256(path.read_bytes()).hexdigest() != expected):
                raise ValueError('A current formal production/alignment source changed: ' + name)
        known_views = {(source, view['view']) for source in public
                       for view in interface_actor.views(public[source])}
        self.entries = {}
        for row in manifest['reviews']:
            identity = row['source'], row['view']
            if (identity in self.entries or identity not in known_views
                    or self.roles[row['source']]['role'] == 'structure_evaluation'):
                raise ValueError('Primary reference manifest contains duplicate or structural-evaluation truth')
            self.entries[identity] = row

    def review(self, source, view):
        row = self.entries.get((source['key'], view['view']))
        if row is None:
            raise MissingSourceReviews('Missing source-only review: ' + source['key'] + '/' + view['view'])
        path = (self.root / row['path']).resolve()
        if not path.is_relative_to(self.root) or hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('A reference review path or exact bytes changed')
        card = json.loads(path.read_text())
        role = self.roles[source['key']]['role']
        if (card['source'] != source['key'] or card['view_id'] != view['view'] or card['role'] != role
                or card['source_units_sha256'] != digest(view['source_units'])
                or card.get('source_semantic_truth_verified') is not True):
            raise ValueError('Source-local review lost its source/view/role/evidence binding')
        expected_kind = 'asset_program_ports' if source['dataset'] == 'OpenExempt' else 'literal_semantic_graph'
        if row['kind'] != expected_kind:
            raise ValueError('The reviewed reference belongs to another production interface')
        if expected_kind == 'asset_program_ports':
            world, receipt = asset_graph_pairs.reference_world(card, view['source_units'],
                view['read_input']['public_context']['governing_regime'])
        else:
            if (card.get('reference_ready') is not True
                    or card.get('native_answers_used_to_create_or_repair_graph') is not False
                    or sorted(card['native_views']) != view['native_tasks']):
                raise ValueError('Generic graph needs a source-only audit,not a teacher proposal or answer repair')
            graph, normalization = normalize_graph_evidence(card['graph'], view['source_units'])
            (world, _, receipt), _ = rich_graph_pairs.reference_graph(graph,
                {u['id']: u for u in view['source_units']}, view['scope']['context'])
            card = {**card, 'graph': graph}
            receipt = {'reference_evidence': normalization, 'numeric_transport': receipt}
        if (world.schema, world.context) != (view['scope']['schema'], view['scope']['context']):
            raise ValueError('Reference graph and actual reader target use different declared domains')
        return card, world, {'path': row['path'], 'sha256': row['sha256'], **receipt}

    def readiness(self, batch):
        missing, ready, refusals = [], [], []
        for row in prefix(list(self.roles.values()), batch):
            if row['role'] == 'structure_evaluation':
                continue
            source = self.public[row['source']]
            for view in self.actor.views(source):
                if view['pre_generation_domain_refusal']:
                    refusals.append([source['key'], view['view']]); continue
                try:
                    self.review(source, view)
                    ready.append([source['key'], view['view']])
                except MissingSourceReviews:
                    missing.append([source['key'], view['view']])
        return {'batch': batch, 'ready_source_views': ready, 'missing_source_views': missing,
                'pre_generation_domain_refusals': refusals,
                'ready': not missing, 'new_model_requests': 0,
                'source_local_review_is_not_independent_human_or_complete_legal_gold': True}


class InterfaceBatchTrainer:
    def __init__(self, root, *, roles, public, registry, actor, candidate_orders,
                 grade_provider, study_binding):
        self.root, self.roles, self.public = Path(root), deepcopy(roles), public
        self.registry, self.actor = registry, actor
        self.orders, self.grade_provider = deepcopy(candidate_orders), grade_provider
        self.binding = deepcopy(study_binding)
        if not self.binding or set(public) != {r['source'] for r in roles}:
            raise ValueError('The actual original TRAIN manifest and study binding are required')

    def batch(self, batch):
        current = prefix(self.roles, batch)
        visible = {r['source']: r for r in current}
        directory = self.root / ('B' + str(batch))
        # Verify every needed prefix review before ANY physical request in this
        # batch. Missing teacher proposals never become guessed source worlds.
        ready = self.registry.readiness(batch)
        immutable_json(directory / 'reference_readiness' / (digest(ready) + '.json'), ready)
        if not ready['ready']:
            raise MissingSourceReviews('Formal prefix lacks ' + str(len(ready['missing_source_views'])) + ' source-only reviews')
        paired, references, predictions, pair_refusals, ref_refusals = [], [], [], {}, {}
        native_ids, opaque_ids = {}, {}
        for source_id, row in visible.items():
            source = self.public[source_id]
            native_ids[source_id] = [v['id'] for v in source['views']]
            views = self.actor.views(source)
            opaque_ids[source_id] = [v['view'] for v in views]
            if row['role'] == 'structure_evaluation':
                continue
            for view in views:
                if view['pre_generation_domain_refusal']:
                    declaration = {'source': source_id, 'view': view['view'],
                        'public_context': view['read_input']['public_context'],
                        'declared_before_generation': True, 'not_a_physical_model_trial': True}
                    receipt = digest(declaration)
                    immutable_json(self.root / 'domain_refusals' / (receipt + '.json'), declaration)
                    if row['role'] == 'reference_only':
                        ref_refusals[source_id, view['view']] = receipt
                    else:
                        for plan in self.orders[row['dataset']]:
                            pair_refusals[source_id, view['view'], plan] = receipt
                            predictions.append({'source': source_id, 'dataset': row['dataset'], 'plan': plan,
                                'view': view['view'], 'native': {task: {'handled': False, 'answer': None}
                                    for task in view['native_tasks']}, 'pre_generation_domain_refusal': receipt})
                    continue
                card, world, review_receipt = self.registry.review(source, view)
                if row['role'] == 'reference_only':
                    references.append({'source': source_id, 'dataset': row['dataset'], 'view': view['view'],
                        'graph': graph_record(world), 'native_public': view['native_public'], 'review': review_receipt})
                    continue
                if [plan['name'] for plan in view['plans']] != self.orders[row['dataset']]:
                    raise ValueError('The original fixed candidate pool changed')
                for plan in view['plans']:
                    read = self.actor.measure(source, view, plan, 'skill_actor')
                    provenance = digest({'physical_read': read['physical_call_id'], 'review': review_receipt,
                                         'production_decode': digest(read)})
                    if source['dataset'] == 'OpenExempt':
                        pair, alignment = asset_graph_pairs.pair_from_port_record(card, read['ports'], plan,
                            view['source_units'], source=source_id, role=row['role'], provenance=provenance,
                            version=read['channel_version'], production_errors=read['production_errors'])
                    else:
                        pair, alignment = rich_graph_pairs.pair_from_audited_reference(card['graph'], read['graph'],
                            view['source_units'], source=source_id, role=row['role'], provenance=provenance,
                            version=read['channel_version'], context=view['scope']['context'],
                            semantic_reference_verified=True, observation_errors=read['production_errors'])
                        pair, outcome = canonical_pair(pair, {'graph': read['graph'], 'errors': read['production_errors']})
                        alignment = {**alignment, 'observed_outcome': outcome}
                    paired.append({'source': source_id, 'dataset': row['dataset'], 'view': view['view'],
                        'plan': plan['name'], 'pair': pair_record(pair), 'review': review_receipt,
                        'native_public': view['native_public'],
                        'physical_call_id': read['physical_call_id'], 'alignment': alignment})
                    predictions.append({'source': source_id, 'dataset': row['dataset'], 'view': view['view'],
                        'plan': plan['name'], 'native': read['native'], 'physical_call_id': read['physical_call_id']})
        # Persist the complete prefix's measured native outputs before asking
        # for any native TRAIN labels. Pure-reference sources are absent here.
        immutable_json(directory / 'predictions_before_grading.json', predictions)
        prediction_seal = sealed({'batch': batch, 'study_binding': self.binding,
            'predictions_sha256': digest(predictions), 'source_only_reference_native_labels_opened': False},
            'training_prediction_seal_sha256')
        immutable_json(directory / 'prediction_seal.json', prediction_seal)
        scores = []
        annotations = {}
        for prediction in predictions:
            source_id = prediction['source']; source = self.public[source_id]
            if source_id not in annotations:
                annotations[source_id] = self.grade_provider(source_id, deepcopy(prediction_seal))
            views = {v['id']: v for v in source['views']}
            for task, value in prediction['native'].items():
                grade = (grade_view(source['dataset'], views[task], annotations[source_id][task], value['answer'],
                    value.get('evidence_sentence_ids', [])) if value['handled'] else {'grade': 0.})
                scores.append({'source': source_id, 'dataset': source['dataset'], 'view': task,
                    'plan': prediction['plan'], 'handled': value['handled'], 'grade': grade['grade']})
        immutable_json(directory / 'native_TRAIN_scores.json', scores)
        snapshot = fit_prefix(self.roles, batch, paired, references, scores, native_ids,
            candidate_orders=self.orders, source_opaque_views=opaque_ids,
            declared_pair_domain_refusals=pair_refusals, declared_reference_domain_refusals=ref_refusals)
        immutable_json(directory / 'shared_verified_raw_evidence.json', {'pairs': paired, 'references': references,
            'registry_sha256': self.registry.manifest['registry_sha256'], 'study_binding': self.binding,
            'not_an_arm_learned_artifact': True})
        libraries = {arm: arm_snapshot(snapshot, arm) for arm in
                     ('M1_only', 'M2_fixed_interfaces', 'M1_full_trace_replay', 'M1_M2')}
        for arm, library in libraries.items():
            immutable_json(directory / 'libraries' / (arm + '.json'), library)
        return libraries
