"""Resolve an actual footprint-feature collision using the available program.

This consumes the just-completed real repair as TRAIN feedback. It does not
rerun that repair or count refitting as independent validation. Source/code
operators are public current input to both methods, not new legal supervision.
"""
from copy import deepcopy
import json

from experiments import legal_skill_evolution_impact_guided_edit as trial
from experiments import legal_skill_evolution_impact_scope_learning as l
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.repair_impact_learning import learn, observations, predict, generation_scope


OLD = l.OUT.parent / 'cross_source_feedback_v2'
OUT = l.OUT.parent / 'actual_program_feedback_v3'


def operator_from_old_evidence(node):
    value = node.get('current_validity', {}).get('value')
    if isinstance(value, list) and value and isinstance(value[0], str):
        return value[0]
    for evidence in node['evidence_refs']:
        if not isinstance(evidence, dict) or 'source_gap_20261114/unbound_pure_preview/' not in evidence.get('path', ''):
            continue
        old = l.read(l.ROOT / evidence['path'])
        for key in evidence['json_path']:
            old = old[key]
        if isinstance(old, dict) and isinstance(old.get('term'), list):
            index = {'actor': 1, 'condition': 3}.get(node['role'])
            if index is not None and len(old['term']) > index:
                field = old['term'][index]
                if isinstance(field, list) and field and isinstance(field[0], str):
                    return field[0]
    return None


def run():
    assert l.read(trial.OUT / 'TERMINAL_PRESERVATION.json')['pair_terminal']
    assert not any(r[6] == 'reserved' for r in trial.rows())
    events = deepcopy(l.read(OLD / 'actual_events.json'))
    previous_model = l.read(OLD / 'learned_impact.json')
    task = l.read(trial.OUT / 'common_task.json')
    actual = l.read(trial.OUT / 'unbound_actual_check/summary.json')
    assert all(row['target_partial_source_checks']['known_unconditional_assertion_absent'] is True
        and row['target_partial_source_checks']['source_supported_qualified_restriction_present'] is True for row in actual['rows'])
    new = deepcopy(task['current_source_program_dependency_graph'])
    before = observations(new, max_path=3)
    assert before['norm:0:condition']['features'] == before['norm:1:condition']['features']
    new['id'] = 'actual_qualified_duplicate_repair_feedback'
    new['parent_revision'] = trial.RUN + ':ImpactGuided:teacher'
    new['same_task_FreeHistory_is_a_candidate_variant_not_another_independent_family'] = True
    evidence = [l.ref(trial.OUT / 'common_task.json', ['current_source_program_dependency_graph', 'partial_source_review']),
        l.ref(trial.OUT / 'unbound_actual_check/summary.json')]
    for ni in (0, 1):
        condition = 'norm:' + str(ni) + ':condition'
        l.label(new, condition, 'must_change', ni == 1, evidence)
        l.label(new, condition, 'preserve', ni == 0, evidence)
        l.label(new, condition, 'recheck', True, evidence)
        actor = 'norm:' + str(ni) + ':actor'
        l.label(new, actor, 'must_change', False, evidence)
        l.label(new, actor, 'preserve', True, evidence)
    review = new['partial_source_review']
    for node in new['graph']['nodes']:
        if node['id'].startswith('norm:'):
            ni = int(node['id'].split(':')[1])
            raw = review['supported_existing_qualified_norm' if ni == 0 else 'forbidden_unconditional_norm']['term']
            field = raw[4] if node['role'] == 'condition' else raw[1]
            node['program_operator'] = field[0]
            node['program_operator_origin'] = evidence
    events.append(new)
    for event in events[:-1]:
        for node in event['graph']['nodes']:
            opcode = operator_from_old_evidence(node)
            if opcode:
                node['program_operator'] = opcode
                node['program_operator_origin'] = deepcopy(node['evidence_refs'])
    after = observations(new, max_path=3)
    assert after['norm:0:condition']['features'] != after['norm:1:condition']['features']
    l.check_refs(events)
    model = learn(events, max_path=3, max_literals=2)
    checked = []
    for event in events:
        result = predict(model, event)
        rows = {r['node']: r for r in result['nodes']}
        errors = [j for j in event['judgments'] if model['policies'][j['effect']]['status'] == 'learned'
            and (j['effect'] in rows[j['node']]['effects']) != j['holds']]
        assert not errors
        checked.append({'event': event['id'], 'training_prediction': result,
            'generation_input': generation_scope(model, event), 'training_errors': errors})
    immutable_json(OUT / 'actual_events.json', events)
    immutable_json(OUT / 'learned_impact.json', model)
    immutable_json(OUT / 'actual_training_execution.json', checked)
    immutable_json(OUT / 'actual_feature_collision_and_resolution.json', {
        'before_features_identical': True, 'after_features_distinct': True,
        'actual_operators': ['add_exception', 'no_exceptions'],
        'operator_input_already_available_to_both_teachers': True,
        'source_literals_and_native_answers_not_added_as_features': True,
        'actual_feedback_not_new_independent_validation': True,
        'new_model_requests': 0})
    summary = {'parent_model_sha256': digest(previous_model), 'model_sha256': digest(model),
        'actual_parent_revisions': model['independent_parent_revisions'],
        'explicit_training_judgments': len(model['feedback']),
        'effect_policy_status': {k: v['status'] for k, v in model['policies'].items()},
        'actual_program_shape_collision_resolved_offline': True,
        'new_model_requests': 0, 'real_editor_has_consumed_v3_model': False,
        'independent_U_gain_established': False, 'goal_complete': False}
    immutable_json(OUT / 'summary.json', summary)
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    run()
