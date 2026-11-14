"""Add source-reviewed cross-source harms to the existing parent repair event.

The original four native regressions are three mother contexts, not four new
repairs. Keep labels below concern quoted legal fields, not native answer truth.
This offline update does not rerun or tune the completed paired validation.
"""
from copy import deepcopy
import json

from experiments import legal_skill_evolution_impact_scope_learning as l
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.repair_impact_learning import learn, predict, generation_scope


OUT = l.OUT.parent / 'cross_source_feedback_v2'


def run():
    events = deepcopy(l.read(l.OUT / 'actual_events.json'))
    old_model = l.read(l.OUT / 'learned_impact.json')
    # These exact source errors were already reviewed in the original events:
    # destroy trigger/material, inherited written qualification, and the
    # invented inquiry target. Their actual before/after evidence identifies
    # necessary semantic changes. Do not infer this label from mere failure to
    # preserve an arbitrary unreviewed value.
    for item in events:
        if item['id'] in ('actual_action_scope', 'actual_group_qualification'):
            known = [j for j in item['judgments'] if j['effect'] == 'preserve']
            for judgment in known:
                l.label(item, judgment['node'], 'must_change', not judgment['holds'], judgment['evidence_refs'])
        elif item['id'] == 'actual_condition_consumer_coupling':
            node = next(n for n in item['graph']['nodes'] if n['id'] == 'condition')
            l.label(item, 'condition', 'must_change', True, node['evidence_refs'])
            for judgment in list(item['judgments']):
                if judgment['effect'] == 'preserve' and judgment['holds']:
                    l.label(item, judgment['node'], 'must_change', False, judgment['evidence_refs'])
    event, = [e for e in events if e['id'] == 'actual_group_qualification']
    harm_path = l.IMPACT / 'actual_NDA_scope_repair_and_cross_source_harm.json'
    harms = l.read(harm_path)['actual_cross_source_regressions']
    added = []; seen = set()
    for hi, harm in enumerate(harms):
        source = harm['source']
        if source in seen:
            continue
        seen.add(source)
        previous = harm['actual_before_used_roots'][0]
        old_path = next((l.GAP / 'unbound_pure_preview/ConstraintAcquire').glob('*' + source.split(':')[1] + '*.json'))
        old = l.read(old_path)
        units = old['observation']['visible_inputs']['units']
        support = previous['support_ids']
        quoted = [u for u in units if u['id'] in support]
        assert quoted and source not in event['mother_sources']
        evidence = [l.ref(harm_path, ['actual_cross_source_regressions', hi]),
            l.ref(old_path, ['observation', 'visible_inputs', 'units'])]
        if source.startswith('ContractNLI:e7b'):
            text = ' '.join(u['text'] for u in quoted)
            assert 'expiration or termination' in text and 'request of Auditee' in text and 'immediately' in text
            fields = [(3, 'trigger', 'The actual clause states immediate expiry/termination OR request; preserve that sourced trigger, not merely the old Entailment answer.')]
        elif source.startswith('ContractNLI:a5b'):
            text = ' '.join(u['text'] for u in quoted)
            assert 'without Hydranautics' in text and 'consent' in text and 'Visitor' in text
            fields = [(1, 'actor', 'Visitor is the expressly obligated source actor.'),
                (4, 'condition', 'The disclosure prohibition is expressly subject to consent; this does not establish an employee permission or the NotMentioned native answers.')]
        elif source.startswith('ContractNLI:8fb'):
            text = ' '.join(u['text'] for u in quoted)
            assert 'If requested' in text and '____ days' in text
            fields = [(3, 'trigger', 'Preserve the express request condition and blank deadline. No agreement-end rule, numeric deadline or native Contradiction is inferred.')]
        else:
            raise ValueError('An unreviewed source cannot become a keep label')
        for index, role, judgment in fields:
            key = 'cross_source:' + str(len(added))
            value = previous['term'][index]
            l.node(event, key, 'legal_field', role, evidence, value=value, supported=True)
            # Different current-source inputs are a literal scope fact. It is
            # not a claim that their shared compiler cannot accidentally change
            # both, which is precisely the harm demonstrated by this event.
            l.edge(event, 'qualification', key, 'independent_current_source', evidence)
            l.label(event, key, 'preserve', True, evidence)
            l.label(event, key, 'must_change', False, evidence)
            added.append({'node': key, 'source': source, 'role': role,
                'value': value, 'quote': quoted, 'judgment': judgment,
                'native_answer_not_promoted_to_a_legal_invariant': True,
                'shared_compiler_change_really_harmed_this_context': True})
    assert len(seen) == 3 and len(added) == 4
    event['cross_source_source_validity_reviews'] = added
    l.check_refs(events)
    model = learn(events, max_path=3, max_literals=2)
    checks = []
    for e in events:
        current = predict(model, e); byid = {r['node']: r for r in current['nodes']}
        mismatch = [j for j in e['judgments'] if
            model['policies'][j['effect']]['status'] == 'learned' and
            (j['effect'] in byid[j['node']]['effects']) != j['holds']]
        assert not mismatch
        checks.append({'event': e['id'], 'actual_training_prediction': current,
            'generation_input': generation_scope(model, e), 'mismatches': mismatch})
    before = {r['node']: r for r in predict(old_model, event)['nodes']}
    after = {r['node']: r for r in predict(model, event)['nodes']}
    delta = [{'node': a['node'], 'before': before[a['node']]['effects'],
        'after': after[a['node']]['effects'], 'new_feedback_training_not_prospective_validation': True} for a in added]
    immutable_json(OUT / 'actual_events.json', events)
    immutable_json(OUT / 'learned_impact.json', model)
    immutable_json(OUT / 'actual_training_execution.json', checks)
    immutable_json(OUT / 'feedback_update_delta.json', delta)
    summary = {'parent_model_sha256': digest(old_model), 'updated_model_sha256': digest(model),
        'independent_parent_revisions_still': model['independent_parent_revisions'],
        'actual_native_harm_records': len(harms), 'source_contexts_reviewed': len(seen),
        'source_supported_legal_field_keep_reviews': len(added),
        'total_explicit_training_judgments': len(model['feedback']),
        'learned_policy_status': {k: v['status'] for k, v in model['policies'].items()},
        'new_model_requests': 0, 'real_editor_has_consumed_this_v2_model': False,
        'paired_validation_not_rerun_or_reinterpreted': True, 'goal_complete': False}
    immutable_json(OUT / 'summary.json', summary)
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    run()
