"""Which TRAIN signals can test the two mechanisms? No new inference or TEST."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re

from legal_skill_guard.skill_evolution.controlled import add_controlled
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.native import public_task, grade_view

ROOT = Path(__file__).resolve().parents[2]
ORIGINAL = Path('/home/yndx/hhy/legal-skill-redesign-20261109')


def read(path):return json.loads(path.read_text())


def sha(value):return hashlib.sha256(value.encode()).hexdigest()


def main():
    prepared = ORIGINAL / 'artifacts/legal_skill_evolution_20261111/prepared/train'
    records, grading = read(prepared / 'public.json'), read(prepared / 'grading.json')
    evidence = read(ORIGINAL / 'reports/legal_skill_evolution_plan_20261111/CONTROLLED_LAYER_EVIDENCE.json')
    enriched, enriched_grading = add_controlled(records, grading, evidence)
    manifest = read(ORIGINAL / 'reports/legal_skill_evolution_plan_20261111/candidate_source_manifest.json')
    batches = {s['source_key']: n for n, b in enumerate(manifest['source_sequence'], 1) for s in b['sources']}
    datasets = defaultdict(lambda: {'sources': set(), 'views': 0, 'additional_case_facts_views': 0,
                                    'law_hashes': Counter()})
    clauses = defaultdict(list)
    for source in records:
        group = datasets[source['dataset']];group['sources'].add(source['key'])
        for view in source['views']:
            group['views'] += 1;public = view['public']
            if 'original_input' in public:
                text = public['original_input'];law = text.split('Statutes:', 1)[1].split('Solved Reasoning Steps:', 1)[0]
                group['additional_case_facts_views'] += 1
            else:
                law = public['source_text']
                if 'facts' in public:group['additional_case_facts_views'] += 1
            group['law_hashes'][sha(law)] += 1
        if source['dataset'] == 'SARA_v2_Binary':
            question = source['views'][0]['public']['question']
            match = re.search(r'(?:section|§)\s*(\d+)((?:\([A-Za-z0-9]+\))*)', question, re.I)
            if match:clauses[match.group(1) + match.group(2)].append({'source': source['key'], 'batch': batches[source['key']]})
    profile = read(ORIGINAL / 'configs/legal_skill_evolution_pilot_v11_20261111.json')['executor']
    artifacts = ORIGINAL / 'artifacts/legal_skill_evolution_20261111'
    phases = sorted(artifacts.glob('pilot_v*')) + sorted(artifacts.glob('repair_v*'))
    direct = []
    for source in enriched:
        for view in source['views']:
            if not view.get('controlled_diagnostic'):continue
            identity = digest({'source': source['key'], 'task': public_task(source, view), 'frozen_executor': profile})
            paths = [p / 'native_direct_baselines' / (identity + '.json') for p in phases]
            paths = [p for p in paths if p.exists()]
            if not paths:
                direct.append({'source': source['key'], 'view': view['id'], 'found': False});continue
            bodies = [p.read_bytes() for p in paths]
            if any(b != bodies[0] for b in bodies):raise ValueError('A preserved direct output changed')
            value = json.loads(bodies[0]);execution = value['execution']
            if execution['core_executed'] or not execution['fallback']:raise ValueError('Expected a genuine direct baseline')
            score = grade_view(source['dataset'], view, enriched_grading[source['key']][view['id']],
                               execution['answer'], execution['evidence_sentence_ids'])
            direct.append({'source': source['key'], 'dataset': source['dataset'], 'view': view['id'],
                'found': True, 'grade': score['grade'], 'correct': score['correct'],
                'evidence_path': str(paths[0].relative_to(ORIGINAL)),
                'sha256': hashlib.sha256(bodies[0]).hexdigest()})
    membership = [v['public']['facts']['source_specified_person_role_and_membership_satisfied']
                  for s in enriched if s['dataset'] == 'MAUD' for v in s['views'] if v.get('controlled_diagnostic')]
    full = read(ORIGINAL / 'reports/legal_skill_evolution_run_20261111/formal_mechanism_inventory.json')
    output = {'new_model_calls': 0, 'TEST_read': False, 'goal_complete': False,
        'native_task_structure': {name: {'mother_sources': len(g['sources']), 'native_views': g['views'],
            'views_with_additional_facts_channel': g['additional_case_facts_views'],
            'distinct_supplied_law_texts': len(g['law_hashes']), 'law_text_hash_counts': dict(g['law_hashes'])}
            for name, g in datasets.items()},
        'SARA_exact_requested_clauses': dict(clauses),
        'controlled_direct_results': direct,
        'controlled_direct_found': sum(r['found'] for r in direct),
        'controlled_direct_correct': sum(r.get('correct', False) for r in direct),
        'MAUD_controlled_role_membership_values': dict(Counter(map(str, membership))),
        'current_library_evidence': 'formal_mechanism_inventory.json',
        'interpretation': [
            'The fixed native numerical tasks contain case variation but repeat the supplied law/policy. Applicability can still vary: identical text alone does not prove that Lift is unnecessary.',
            'The varying native contract tasks have fixed document questions and no separate case-facts channel. They can test extraction/binding, but a reader that answers that whole question is not evidence of a learned reasoning procedure.',
            'Every preserved direct controlled answer is correct. Under the fixed strict parent-grade improvement rule, changing only an already-correct controlled view cannot admit an update. A controlled creation table is not old-skill co-revision.',
            'The MAUD controlled layer fixes person/role membership true, so it cannot independently demonstrate improvement in person-role binding.',
            'SARA exact queried clauses are not repeated in these 24 TRAIN parents. This limits repeated-rule revision opportunities, without proving that cross-clause reuse is impossible.',
            'No new sources, curriculum, correctness threshold or model configuration is introduced by this analysis. No further small trial is justified merely to turn a mechanism counter nonzero.']}
    destination = ROOT / 'reports/legal_skill_evolution_run_20261111/training_signal_audit.json'
    destination.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'native_task_structure': {k: {a: b for a, b in v.items() if a != 'law_text_hash_counts'}
        for k, v in output['native_task_structure'].items()}, 'controlled_direct': [output['controlled_direct_correct'],
        output['controlled_direct_found']], 'membership': output['MAUD_controlled_role_membership_values']}, ensure_ascii=False))


if __name__ == '__main__':main()
