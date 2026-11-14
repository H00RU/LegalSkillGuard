"""Audit real component revisions and later-case use; never generate observations.

An error reference, unchanged component ID, or correct native answer alone is
not semantic transfer evidence. Preserve actual version hashes and source IDs.
"""
from collections import defaultdict
import json

from experiments import legal_skill_evolution_observation_library_train as train
from legal_skill_guard.skill_evolution.objects import digest


OUT = train.ROOT / 'artifacts/legal_skill_evolution_observation_transfer_20261114'


def payload(component):
    return {k: component[k] for k in ('meaning', 'prompt', 'schema_json')}


def run():
    events = []
    revisions = []
    for arm in train.ARMS:
        previous = {}
        for batch in range(1, 9):
            path = train.OUT / f'B{batch}' / arm / 'library.json'
            if not path.exists():
                break
            library = train.read(path)
            components = {c['id']: c for c in library['components']}
            check = train.OUT / f'B{batch}' / arm / 'unbound_library_preflight.json'
            checked = train.read(check) if check.exists() else {}
            bad = {r['component'] for r in checked['lineage_issues']} if 'lineage_issues' in checked else set(components)
            for cid, component in components.items():
                before = previous.get(cid)
                if before and payload(before) == payload(component):
                    continue
                revisions.append({'arm': arm, 'update_batch': batch, 'component': cid,
                    'component_payload_sha256': digest(payload(component)),
                    'operation': 'changed_existing_id' if before else 'introduced_id',
                    'prior_same_id_payload_sha256': digest(payload(before)) if before else None,
                    'declared_error_ids': component['error_feedback_ids'],
                    'declared_parent_ids': component['parent_component_ids'],
                    'provenance_references_valid': cid not in bad if 'lineage_issues' in checked else None,
                    'provenance_audit_available': 'lineage_issues' in checked,
                    'later_actual_pre_update_uses': []})
            previous = components
    for batch in range(2, 9):
        path = train.OUT / f'B{batch}/initial_scored_results.json'
        if not path.exists():
            continue
        for row in train.read(path)['rows']:
            library = train.read(train.OUT / f'B{batch-1}' / row['arm'] / 'library.json')
            assert row['library_sha256'] == digest(library)
            components = {c['id']: c for c in library['components']}
            for cid in row['actual_component_ids']:
                component = components[cid]
                matches = [r for r in revisions if r['arm'] == row['arm'] and r['component'] == cid
                    and r['update_batch'] < batch and r['component_payload_sha256'] == digest(payload(component))]
                if not matches:
                    raise ValueError('Actual used component has no matching immutable prior revision')
                event = {'batch': batch, 'source': row['source'], 'library_sha256': row['library_sha256'],
                    'neural_reads': len(row['reads']), 'handled': row['execution']['handled'],
                    'native_correct': row['native_score']['correct'],
                    'source_semantic_transfer_not_proven_by_native_score': True,
                    'actual_observation_present': isinstance(row.get('observation'), dict) and cid in row['observation']}
                matches[-1]['later_actual_pre_update_uses'].append(event)
                events.append({'arm': row['arm'], 'component': cid, **event})
    summary = defaultdict(lambda: {'changed_or_introduced_versions': 0, 'versions_later_selected': 0,
        'valid_error_referenced_versions_later_observed': 0})
    for r in revisions:
        s = summary[r['arm']]
        s['changed_or_introduced_versions'] += 1
        s['versions_later_selected'] += bool(r['later_actual_pre_update_uses'])
        s['valid_error_referenced_versions_later_observed'] += bool(r['declared_error_ids'] and
            r['provenance_references_valid'] and any(u['actual_observation_present'] and u['neural_reads']
                for u in r['later_actual_pre_update_uses']))
    result = {'same_goal': True, 'new_model_calls': 0, 'revisions': revisions, 'actual_uses': events,
        'summary': dict(summary), 'not_a_semantic_success_count': True,
        'later_mixed_batch_not_blind_unseen_TRAIN': True,
        'renames_may_count_as_introduced_ids_not_new_mechanisms': True,
        'invalid_lineage_or_source_only_primitives_not_error_learning_credit': True,
        'no_model_or_native_results_changed': True, 'goal_complete': False}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'unbound_actual_revision_and_use.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'summary': dict(summary), 'actual_use_events': len(events)}), flush=True)


if __name__ == '__main__':
    run()
