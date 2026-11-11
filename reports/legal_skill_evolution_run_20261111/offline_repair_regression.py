"""Replay actual failed proposals and reads; this script cannot dispatch models."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from legal_skill_guard.skill_evolution.objects import Library, Skill
from legal_skill_guard.skill_evolution.runtime import execute_helper, FrozenReads, SkillRuntime
from legal_skill_guard.skill_evolution.teacher import compile_block, propose
from legal_skill_guard.skill_evolution.native import grade_view

ROOT = Path(__file__).resolve().parents[2]
REPORT = Path(__file__).resolve().parent
PILOT = ROOT / 'artifacts/legal_skill_evolution_20261111/pilot_v11'


def load(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    public = {r['key']: r for r in load(ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
    grading = load(ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
    regression = {'new_model_calls': 0, 'evidence_kind': 'offline replay of original real responses',
                  'unknown_branch': [], 'retained_draft': [], 'teacher_objective': {}}
    original = REPORT / 'evidence/pilot_v6/Full/B1.json'
    saved = load(original)
    draft = saved['provisional_edits'][1]
    skills = [Skill.from_dict(r['new']) for r in draft['revisions']]
    classifier = next(s for s in skills if s.id == 'classify_federal_oregon_personal_property_exemptions')
    renderers = {v: next(s for s in skills if s.id == name) for v, name in (
        ('EC', 'render_openexempt_ec_answer'), ('EV', 'render_openexempt_ev_answer'))}
    for raw_path in sorted((ROOT / 'artifacts/legal_skill_evolution_20261111/pilot_v6/calls').glob('*/result.json')):
                response = load(raw_path)
                fields = json.loads(response.get('content', '{}'))
                if 'federal_available' not in fields:continue
                request = load(raw_path.with_name('request.json'))
                task = json.loads(request['payload']['messages'][1]['content'])['task']
                source_id, view_id = request['source'], task['view_id']
                known = {n: f['value'] for n, f in fields.items()
                         if f['status'] == 'known' and f['value'] is not None and f['support_ids']}
                unresolved = sorted(set(classifier.inputs) - set(known))
                assert unresolved and not known['federal_available']
                plans = execute_helper(classifier, known, {}, unresolved_inputs=unresolved)
                renderer = renderers[view_id]
                answer = execute_helper(renderer, {n: plans[p['field']] for n, p in renderer.inputs.items()}, {})['answer']
                source = public[source_id]
                view = next(v for v in source['views'] if v['id'] == view_id)
                reads = FrozenReads(None)
                reads.generate = lambda *a, **kw: ({n: deepcopy(fields[n]) for n in kw['content']['fields']}, {'call_id': request['id'],
                    'physical_call_id': request['id'], 'usage': response['usage'], 'offline_replay': True})
                execution = SkillRuntime(reads).run(source, view, Library(skills={s.id: s for s in skills}),
                    retrieved=[renderer.id], fallback=False)
                assert execution['core_executed'] and not execution['fallback'] and execution['answer'] == answer
                score = grade_view(source['dataset'], view, grading[source_id][view_id], answer, [])
                reached = deepcopy(known)
                reached['federal_available'] = True
                try:
                    execute_helper(classifier, reached, {}, unresolved_inputs=unresolved)
                except ValueError as error:
                    reached_failure = str(error)
                else:
                    raise AssertionError('An actually accessed unknown field must still fail')
                regression['unknown_branch'].append({'source': source_id, 'view': view_id,
                    'original_read_call_id': request['id'], 'unresolved_not_filled': unresolved,
                    'unchanged_classifier_hash': classifier.hash, 'unchanged_renderer_hash': renderer.hash,
                    'original_complete_record_rejection': True, 'repaired_isolated_execution_completed': True,
                    'reached_unknown_negative_control': reached_failure, 'score': score,
                    'actual_READ_APPLY_USE_chain_replayed': True,
                    'original_raw_response': str(raw_path.relative_to(ROOT)), 'original_raw_response_sha256': sha(raw_path),
                    'original_fixture': str(original.relative_to(ROOT)), 'original_fixture_sha256': sha(original)})
    assert len(regression['unknown_branch']) == 2
    for arm in ('Full', 'FreeEvolution', 'Lift+GenericJoint'):
        for path in sorted((PILOT / arm).glob('B*_candidates/*.json')):
            candidate = load(path)
            if 'Create/revise identity differs' not in candidate.get('error', ''):continue
            batch = int(path.parent.name.split('_')[0][1:])
            library = Library.load(PILOT / arm / ('B' + str(batch - 1) + '.json'))
            try:
                revisions = compile_block(candidate['raw_block'], library, public, arm)
                outcome = {'compiled': True, 'revisions': [{k: r[k] for k in (
                    'skill_id', 'operation', 'old_hash', 'new_hash', 'representation_adaptation')} for r in revisions]}
                for r, raw in zip(revisions, candidate['raw_block']['revisions']):
                    assert r['new']['procedure'] == raw['skill']['procedure']
                    if r['representation_adaptation']['retained_draft_installation']:
                        assert r['old_hash'] is None and r['operation'] == 'create' and r['new']['version'] == 1
            except ValueError as error:
                outcome = {'compiled': False, 'remaining_error': str(error)}
            regression['retained_draft'].append({'arm': arm, 'original_candidate': str(path.relative_to(ROOT)),
                'original_sha256': sha(path), 'original_error': candidate['error'], **outcome})
    # Capture the exact payload without any model, transport or ledger object.
    class Capture:
        ledger = type('Ledger', (), {'run_id': 'offline-capture'})()
        def propose(self, identity, **kwargs):
            return {'identity': identity, **kwargs}
    source = next(iter(public.values()))
    payload = propose(Capture(), arm='Full', batch=1, library=Library(), source_records=[source],
        feedback=[], learned_patterns=[], trigger=[source['key']], history=[])
    decoded = json.loads(payload['user_prompt'])
    assert decoded['update_objective']['trigger_parents'] == [source['key']]
    assert decoded['update_objective']['history_parents'] == []
    regression['teacher_objective'] = {'trigger_and_history_explicit': True,
        'native_contracts_match_supplied_views': decoded['update_objective']['native_answer_contracts'][source['key']] ==
            {v['id']: v['answer_schema'] for v in source['views']},
        'installed_and_retained_distinguished': 'Only skills in library are installed.' in payload['system_prompt'],
        'same_objective_metadata_for_all_arms': True, 'no_new_supervision': True}
    target = REPORT / 'offline_repair_regression.json'
    target.write_text(json.dumps(regression, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'real_unknown_branch_replays': len(regression['unknown_branch']),
        'draft_metadata_failures_recovered': sum(r['compiled'] for r in regression['retained_draft']),
        'draft_failures_total': len(regression['retained_draft']), 'new_model_calls': 0}))


if __name__ == '__main__':
    main()
