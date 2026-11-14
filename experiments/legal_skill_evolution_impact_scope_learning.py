"""Learn from preserved actual repairs, with explicit source-reviewed labels.

Graphs are an offline annotation of existing TRAIN source/program evidence,
shared with all controls. They are not fresh model-generated graphs, a new
benchmark, or evidence of prospective editing benefit. No model client here.
"""
from copy import deepcopy
import json
from pathlib import Path

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.repair_impact_learning import learn, predict, generation_scope


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/legal_skill_evolution_impact_scope_learning_20261114/positive_witnesses_v1'
IMPACT = ROOT / 'artifacts/legal_skill_evolution_repair_impact_20261114'
SCOPE = ROOT / 'artifacts/legal_skill_evolution_source_scope_repair_20261114'
GAP = ROOT / 'artifacts/legal_skill_evolution_source_gap_20261114'


def read(path):
    return json.loads(path.read_text())


def ref(path, pointer=()):
    data = read(path)
    value = data
    for part in pointer:
        value = value[part]
    return {'path': str(path.relative_to(ROOT)), 'json_path': list(pointer),
        'file_sha256': digest(data), 'value_sha256': digest(value)}


def check_refs(value):
    if isinstance(value, dict):
        if {'path', 'json_path', 'file_sha256', 'value_sha256'} <= value.keys():
            actual = ref(ROOT / value['path'], value['json_path'])
            if actual != value:
                raise ValueError('Actual source/program evidence changed')
        for child in value.values():
            check_refs(child)
    elif isinstance(value, list):
        for child in value:
            check_refs(child)


def event(name, parent, sources):
    return {'id': name, 'parent_revision': parent, 'mother_sources': sources,
        'graph': {'nodes': [], 'edges': [], 'seeds': []}, 'judgments': [],
        'graph_origin': 'offline_annotation_of_preserved_actual_TRAIN_source_and_program',
        'same_annotations_available_to_strong_controls': True,
        'not_a_fresh_or_blind_validation': True}


def node(e, key, kind, role, evidence, *, value=None, supported=False, seed=False):
    row = {'id': key, 'kind': kind, 'role': role, 'evidence_refs': evidence}
    if supported:
        row['current_validity'] = {'status': 'supported', 'value': deepcopy(value),
            'evidence_ref': deepcopy(evidence)}
    e['graph']['nodes'].append(row)
    if seed:
        e['graph']['seeds'].append(key)


def edge(e, a, b, relation, evidence):
    e['graph']['edges'].append({'from': a, 'to': b, 'relation': relation, 'evidence_refs': evidence})


def label(e, key, effect, holds, evidence):
    e['judgments'].append({'node': key, 'effect': effect, 'holds': holds,
        'evidence_refs': evidence, 'judgment_scope': 'explicit_actual_source_or_executed_variant_review'})


def action_event():
    path = IMPACT / 'actual_e82b_action_specific_source_repair.json'; r = read(path)
    evidence = [ref(path, ['source_evidence']), ref(path, ['actual_before_readings']), ref(path, ['actual_after_norms'])]
    e = event('actual_action_scope', r['event_id'], [r['mother_source']])
    node(e, 'request_condition', 'source_constraint', 'trigger', evidence, seed=True)
    node(e, 'copies_scope', 'source_constraint', 'material', evidence, seed=True)
    node(e, 'return', 'legal_action', 'return', evidence)
    node(e, 'destroy', 'legal_action', 'destroy', evidence)
    edge(e, 'request_condition', 'return', 'applies_to', evidence)
    edge(e, 'request_condition', 'destroy', 'applies_to', evidence)
    edge(e, 'copies_scope', 'destroy', 'applies_to', evidence)
    # These are the real acquired choices, not a corrupted synthetic program.
    readings = {x['operation']: x['choice'] for x in r['actual_before_readings']}
    for action in ('return', 'destroy'):
        for role in ('trigger', 'material'):
            key = action + '_' + role
            operation = action + ('_material_scope_v2' if role == 'material' else '_trigger_v2')
            stable = action == 'return'
            node(e, key, 'legal_field', role, evidence, value=readings[operation], supported=stable)
            edge(e, action, key, 'has_' + role, evidence)
            label(e, key, 'preserve', stable, evidence)
            # The header request needs checking on both actions. Checking the
            # already correct return trigger does not require changing it.
            label(e, key, 'recheck', role == 'trigger' or action == 'destroy', evidence)
    node(e, 'connection', 'legal_field', 'action_connection', evidence,
        value=readings['disposal_action_connection_v2'], supported=True)
    label(e, 'connection', 'preserve', True, evidence)
    label(e, 'connection', 'recheck', False, evidence)
    return e


def qualification_event():
    old = next((GAP / 'unbound_pure_preview/ConstraintAcquire').glob('*6fce*.json'))
    new = next((SCOPE / 'ConstraintAcquire/execution').glob('*6fce*.json'))
    before = read(old)['actual']['execution']['source_output']['statements']
    after = read(new)['actual']['execution']['source_output']['statements']
    e = event('actual_group_qualification', 'actual_NDA_scope_repair_and_cross_source_harm', [read(new)['source']])
    conditions = [(i, s) for i, s in enumerate(after) if s['term'][0] == 'source_disclosure_condition_atom_v4']
    assert len(conditions) == 1
    ci, condition = conditions[0]
    ce = [ref(new, ['actual', 'execution', 'source_output', 'statements', ci])]
    node(e, 'qualification', 'source_constraint', 'condition', ce, seed=True)
    node(e, 'representatives', 'legal_group', 'qualified_group', ce)
    edge(e, 'qualification', 'representatives', 'qualifies_group', ce)
    roles = ('employees_of', 'consultants_of', 'agents_of')
    for role in roles:
        oi, previous = next((i, s) for i, s in enumerate(before) if s['term'][0] == 'permission' and s['term'][2][2][0] == role)
        ni, current = next((i, s) for i, s in enumerate(after) if s['term'][0] == 'permission' and s['term'][2][2][0] == role
            and 12 in s['support_ids'])
        proof = ce + [ref(old, ['actual', 'execution', 'source_output', 'statements', oi]),
            ref(new, ['actual', 'execution', 'source_output', 'statements', ni])]
        assert previous['term'][3] != current['term'][3]
        member = 'member:' + role
        node(e, member, 'legal_participant', 'member', proof)
        edge(e, 'representatives', member, 'has_member', proof)
        for index, name in ((1, 'actor'), (3, 'condition')):
            key = role + ':' + name
            node(e, key, 'legal_field', name, proof, value=previous['term'][index], supported=name == 'actor')
            edge(e, member, key, 'has_' + name, proof)
            label(e, key, 'recheck', name == 'condition', proof)
            label(e, key, 'preserve', name == 'actor', proof)
    return e


def consumer_event():
    path = IMPACT / 'actual_MAUD_inquiry_target_repair.json'; r = read(path)
    proof = [ref(path, ['source_reviews']), ref(path, ['actual_candidates']), ref(path, ['observed_coupling_supervision'])]
    e = event('actual_condition_consumer_coupling', r['parent_program_revision'], r['mother_sources'])
    node(e, 'condition', 'legal_field', 'inquiry_condition', proof, seed=True)
    node(e, 'renderer', 'program_component', 'renderer', proof)
    node(e, 'consumer', 'program_component', 'consumer', proof)
    edge(e, 'condition', 'renderer', 'rendered_by', proof)
    edge(e, 'renderer', 'consumer', 'interpreted_by', proof)
    for key in ('renderer', 'consumer'):
        label(e, key, 'recheck', True, proof)
    # The source and these stable semantic operands are unchanged in the
    # existing complete repair; unknown necessity of untested edits is omitted.
    for key in ('actor', 'matter'):
        node(e, key, 'legal_field', key, proof)
        label(e, key, 'recheck', False, proof)
        label(e, key, 'preserve', True, proof)
    return e


def main():
    events = [action_event(), qualification_event(), consumer_event()]
    check_refs(events)
    model = learn(events, max_path=3, max_literals=2)
    immutable_json(OUT / 'actual_events.json', events)
    immutable_json(OUT / 'learned_impact.json', model)
    checks = []
    for e in events:
        prediction = predict(model, e); by_id = {r['node']: r for r in prediction['nodes']}
        mismatches = [j for j in e['judgments'] if (j['effect'] in by_id[j['node']]['effects']) != j['holds']]
        checks.append({'event': e['id'], 'judgments': len(e['judgments']), 'mismatches': mismatches,
            'prediction': prediction, 'generation_input': generation_scope(model, e)})
    immutable_json(OUT / 'actual_training_execution.json', checks)
    summary = {'actual_parent_revisions': model['independent_parent_revisions'],
        'effect_policy_status': {k: v['status'] for k, v in model['policies'].items()},
        'reviewed_training_judgments': sum(len(e['judgments']) for e in events),
        'training_mismatches': sum(len(c['mismatches']) for c in checks),
        'new_model_requests': 0, 'prospective_real_editing_benefit_established': False,
        'graph_annotation_not_claimed_as_free_model_acquisition': True,
        'goal_complete': False}
    immutable_json(OUT / 'summary.json', summary)
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
