"""Diagnose remaining current C TRAIN losses before a new acquisition request."""
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3

from experiments import legal_skill_evolution_C_TRAIN_runtime as current
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.open_acquisition import execute
from legal_skill_guard.skill_evolution.source_candidate_diagnosis import typed_envelope
from legal_skill_guard.skill_evolution.source_composition import statement_fingerprint
from legal_skill_guard.skill_evolution.source_concept_execution import convert
from legal_skill_guard.skill_evolution.span_compiler import execute_json

ROOT = current.ROOT
OUT = ROOT / 'artifacts/legal_skill_evolution_C_candidate_diagnosis_20261116'
PARENT = ROOT / 'artifacts/legal_skill_evolution_C_revision_integration_20261115'


def run():
    read = current.read
    with sqlite3.connect('file:' + str(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') + '?mode=ro', uri=True) as db:
        before = db.execute('select role,status,count(*) from calls group by role,status').fetchall()
    assert not any(status == 'reserved' for _, status, _ in before)
    library = read(PARENT / 'selected_library.json'); revision = library['source_revision']
    bank = read(current.generation.OUT / 'raw_source_bank.json'); grading = read(current.generation.OUT / 'TRAIN_grading.json')
    prior = read(ROOT / 'artifacts/legal_skill_evolution_source_residual_diagnosis_20261115/result.json')
    historical = {(r['source'], v['view']) for r in prior['results'] for v in r['views']}
    files = [Path(__file__), ROOT / 'legal_skill_guard/skill_evolution/source_candidate_diagnosis.py']
    immutable_json(OUT / 'protocol.json', {'source_sha256': {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
        'only_original_TRAIN': True, 'no_model_calls': True, 'goal_complete': False})
    summaries = []
    for path in sorted((PARENT / 'rows').glob('*.json')):
        actual = read(path); sid = actual['source']
        failures = [v for v in actual['feedback']['views'] if not v['score'] or not v['score']['correct']]
        if not failures:
            continue
        raw = read(current.OUT / 'C/raw_observations' / (digest(sid) + '.json'))
        candidates = {}; phi = {}; g_outputs = {}
        for producer in ('previous', 'proposed'):
            child = deepcopy(revision[producer]); observation = convert(child, raw)
            phi[producer] = observation['source_concept_execution']['program_output']
            immutable_json(OUT / 'actual_phi' / producer / (digest(sid) + '.json'), phi[producer])
            child['selected_rule_ids'] = [r['id'] for r in child['language']['rules']]
            all_g = execute(child, observation)['source_output']; g_outputs[producer] = all_g
            for row in all_g['statements']:
                key = statement_fingerprint(row)
                candidates.setdefault(key, {'statement': row, 'origins': []})['origins'].append({'producer': producer, 'kind': 'actual_all_G'})
            scoped = deepcopy(phi[producer]); scoped['actual_neural_answers'] = raw['visible_inputs']['answers']
            for item in typed_envelope(child, scoped):
                key = statement_fingerprint(item['statement'])
                candidates.setdefault(key, {'statement': item['statement'], 'origins': []})['origins'].append({'producer': producer, 'kind': 'typed_scope_relaxation', **{k: v for k, v in item.items() if k != 'statement'}})
        pool = list(candidates.values()); definitions = [i for i, r in enumerate(pool) if r['statement']['term'][0] == 'define_representative']
        root_sets = [sorted(set(definitions + [i])) for i in range(len(pool))]
        program = library['spec']['decision_program']; tree = ast.parse(program)
        entry = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'apply']; assert len(entry) == 1
        entry[0].name = 'consumer_apply'
        probe = ast.unparse(tree) + '''

def apply(inputs,premises):
    return {'results':[consumer_apply(inputs['case'],{'nodes':inputs['nodes'],'roots':r}) for r in inputs['root_sets']]}
'''
        nodes = [{'id': i, 'term': r['statement']['term'], 'child_ids': []} for i, r in enumerate(pool)]
        views = []
        for failure in failures:
            vid = failure['view']
            if (sid, vid) in historical:
                views.append({'view': vid, 'decision': 'reuse_historical_source_native_interpretation_diagnosis',
                    'no_new_probe_or_label_driven_source_repair': True}); continue
            view = next(v for v in bank[sid]['source']['views'] if v['id'] == vid)
            results = execute_json(probe, {'case': {'task_id': vid, 'question': view['public']['question']},
                'nodes': nodes, 'root_sets': root_sets}, {}, allow_helpers=True)['results']
            matches = [i for i, value in enumerate(results) if value['handled'] and value['used_nodes'] and value['answer'] == grading[sid][vid]['answer']]
            existing = [i for i in matches if any(o['kind'] == 'actual_all_G' for o in pool[i]['origins'])]
            decision = ('existing_G_output_selection_requires_source_review' if existing else
                'composition_extension_requires_source_review' if matches else 'source_concept_or_consumer_review_required')
            views.append({'view': vid, 'decision': decision, 'matching_rows': len(matches), 'matching_actual_G_rows': len(existing),
                'witnesses': [pool[i] for i in (existing or matches)[:4]],
                'scope': 'Singleton rendered frame plus actual definitions, fixed acquired primitive terms/templates/definite scoped choices.',
                'not_a_joint_theory_or_source_truth_certificate': True})
        receipt = {'source': sid, 'candidate_frames': pool, 'views': views,
            'all_G_outputs': g_outputs, 'new_model_calls': 0, 'no_new_term_or_absence_audit': True}
        immutable_json(OUT / 'rows' / (digest(sid) + '.json'), receipt)
        summaries.append({'source': sid, 'candidate_count': len(pool), 'views': [{k: v for k, v in x.items() if k != 'witnesses'} for x in views]})
        print(json.dumps({'source': sid, 'views': [(v['view'], v['decision'], v.get('matching_rows')) for v in views]}), flush=True)
    with sqlite3.connect('file:' + str(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') + '?mode=ro', uri=True) as db:
        assert db.execute('select role,status,count(*) from calls group by role,status').fetchall() == before
    immutable_json(OUT / 'result.json', {'rows': summaries, 'new_model_calls': 0, 'all_original_TRAIN': True,
        'not_all_G_inexpressibility_or_English_semantics': True, 'goal_complete': False})


if __name__ == '__main__':
    run()
