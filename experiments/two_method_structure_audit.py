"""Audit fixed pilot relationship combinations after all choices are sealed.

No new model calls. No grading input. Keep reviewed semantic types and coarse
relation topology separate, and never promote partial-annotation absence into
a verified absence from the original TRAIN sources.
"""
import json
from pathlib import Path

from experiments.two_method_annotate import inputs
from experiments.two_method_graph_corpus import BASE, ROOT, read, sha
from experiments.two_method_pilot_comparison import MAIN
from legal_skill_guard.paired_interfaces import graph_interface as gi
from legal_skill_guard.paired_interfaces.structure_audit import compare_target
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


STRUCTURAL = BASE / 'structural_source_audits_v1/a18c08baa20de12e730a4b653947fce02c2922b753ed87d7870d337d2d5245ce/manifest.json'


def run():
    lock_path = BASE / 'pilot_lock.json'
    seal_path = MAIN / 'selection_freeze.json'
    lock, seal, manifest = read(lock_path), read(seal_path), read(STRUCTURAL)
    if seal['calibration_or_structure_evaluation_grades_used_for_main_selection']:
        raise ValueError('Source structure auditing must follow choice freezing')
    if manifest['main_selection_freeze_sha256'] != sha(seal_path):
        raise ValueError('The structural source audits lost their original choice binding')
    public_path = ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
    train = {source['key']: source for source in read(public_path)}
    evaluation = {(item['source'], item['view']): item['audit_path'] for item in manifest['reviews']}
    bindings = {str(path.relative_to(ROOT)): sha(path)
                for path in (lock_path, seal_path, STRUCTURAL, public_path, Path(__file__),
                             ROOT / 'legal_skill_guard/paired_interfaces/structure_audit.py')}
    records = []
    for row in lock['rows']:
        folder = BASE / 'annotation_v1/proposed_references' / digest(row['key'])
        task_path = folder / 'task.json'
        task = read(task_path)
        actual, _ = inputs(train[row['key']])
        if actual != task['task'] or not task['no_native_answers_or_questions']:
            raise ValueError('The annotation no longer binds its original source-only input')
        bindings[str(task_path.relative_to(ROOT))] = sha(task_path)
        for view in task['task']['views']:
            identity = (row['key'], view['view_id'])
            path = (ROOT / evaluation[identity] if row['role'] == 'structure_evaluation'
                    else folder / 'audits' / view['view_id'] / 'source_review.json')
            audit = read(path)
            if (audit['source'] != row['key'] or audit['view_id'] != view['view_id']
                    or audit['role'] != row['role'] or not audit['reference_ready']
                    or not audit['source_semantic_truth_verified']
                    or audit['source_units_sha256'] != digest(view['source_units'])
                    or audit['native_answers_used_to_create_or_repair_graph']):
                raise ValueError('A scoped source review lost its evidence/role binding')
            gi.validate(audit['graph'], view['source_units'])
            bindings[str(path.relative_to(ROOT))] = sha(path)
            records.append({'source': row['key'], 'view': view['view_id'],
                            'dataset': row['dataset'], 'role': row['role'],
                            'audit_path': str(path.relative_to(ROOT)), 'graph': audit['graph']})
    reference = [item for item in records if item['role'] != 'structure_evaluation']
    targets = [item for item in records if item['role'] == 'structure_evaluation']
    if len(reference) != 39 or len(targets) != 13:
        raise ValueError('The original fixed source-view denominator changed')
    output = []
    for target in targets:
        within = [item['graph'] for item in reference if item['dataset'] == target['dataset']]
        typed = compare_target(target['graph'], within, typed=True)
        untyped = compare_target(target['graph'], within, typed=False)
        coarse_keys = set(untyped['annotation_unseen_combinations'])
        output.append({k: target[k] for k in ('source', 'view', 'dataset', 'audit_path')} | {
            'training_views': len(within), 'typed_relationship_pairs': typed,
            'relation_argument_topology_pairs': untyped,
            'coarse_annotation_unseen_pair_count': len(coarse_keys),
            'source_scope_complete': target['graph']['scope_complete'],
            'source_unresolved_count': len(target['graph']['unresolved']),
            'source_semantics_novelty_not_certified_by_annotation_features': True})
    protocol = {'experiment': 'fixed_source_relationship_pair_audit_v1', 'sha256': bindings,
        'feature_family': 'two stated/negated hyperedges sharing a referent;argument positions and equality preserved',
        'identity_amount_date_quote_and_display_name_invariant': True,
        'typed_and_untyped_reported_separately': True,
        'source_review_reification_can_create_annotation_only_novelty': True,
        'incomplete_training_annotations_preclude_source_absence_certification': True,
        'no_full_graph_novelty_or_M2_transfer_claim': True, 'new_model_requests': 0,
        'source_folds_or_candidate_pool_changed': False, 'native_grading_loaded': False}
    out = BASE / 'structure_audit_v1' / digest(protocol)
    immutable_json(out / 'protocol.json', protocol)
    result = {'training_source_views': len(reference), 'evaluation_source_views': len(targets),
        'source_absence_certified_targets': 0, 'targets': output,
        'evaluation_views_with_annotation_unseen_typed_pairs': sum(bool(item['typed_relationship_pairs']['annotation_unseen_combinations']) for item in output),
        'evaluation_views_with_annotation_unseen_coarse_pairs': sum(bool(item['relation_argument_topology_pairs']['annotation_unseen_combinations']) for item in output),
        'no_unseen_natural_structure_or_transfer_claim': True, 'new_model_requests': 0}
    immutable_json(out / 'report.json', result)
    print(json.dumps({'artifact_root': str(out.relative_to(ROOT)),
                     **{key: value for key, value in result.items() if key != 'targets'}}, ensure_ascii=False))


if __name__ == '__main__':
    run()
