"""Read-only EV learning-content audit. Reads TRAIN only; no model/network calls."""
import copy
import hashlib
import json
import socket
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

def blocked(*args, **kwargs):
    raise RuntimeError('Network disabled in existing-TRAIN audit')

socket.socket.connect = blocked
socket.create_connection = blocked

from experiments.openexempt_online import native_claim_feedback
from legal_skill_guard.learning.legal_namespace import allowable_namespaces
from legal_skill_guard.learning.task_scoped_skills import task_view
from legal_skill_guard.openexempt import metrics
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

RUN = ROOT / 'runs/legal_openexempt_complete_output_utility_public_assets128_20261030_run01'
PACKET = ROOT / 'data/packets/openexempt_closed_feedback_public_assets128_20261021'

def read(path):
    return json.loads(path.read_text())

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def emit(name, value):
    path = OUT / name
    assert not path.exists(), 'New output name required: ' + name
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

rows = read(PACKET / 'inputs.json')['rows']
row_map = {(r['case_id'], r['family']): r for r in rows}
targets = {int(p.stem): read(p)['targets']['EV'] for p in (PACKET/'grading_only').glob('*.json')}
latest, bank, summaries, details = {}, [], [], []
bound_paths = [ROOT/'experiments/openexempt_online.py', ROOT/'legal_skill_guard/openexempt.py',
               ROOT/'legal_skill_guard/learning/task_scoped_skills.py', PACKET/'inputs.json']

def error_counts(values):
    counts = Counter()
    for r in values:
        fb = native_claim_feedback(r, targets[r['case_id']])
        counts['sources'] += 1
        counts['invalid'] += int(fb['invalid_response'])
        for key in ('correct', 'missing', 'incorrect_value', 'extra_or_duplicate'):
            counts[key] += fb.get(key, 0)
    return dict(counts)

for batch in range(1, 9):
    publication_path = RUN/'publications'/f'b{batch}.json'
    bound_paths.append(publication_path)
    pub = read(publication_path)
    first = read(RUN/'batches'/f'b{batch}_prequential_records.json')['skills']
    latest.update({(r['case_id'], r['family']): r for r in first})
    current_ids = {r['case_id'] for r in first}
    for step, decision in enumerate(pub['training_decisions'], 1):
        name = f'b{batch}_candidate{step}'
        parent_bank = copy.deepcopy(bank)
        if decision.get('teaching_task') == 'EV':
            proposed = decision.get('proposed_replay', decision.get('actual_replay', []))
            proposed = [r for r in proposed if r['family'] == 'EV']
            parent = [latest[r['case_id'], 'EV'] for r in proposed]
            if proposed:
                wire_path = RUN/'teacher'/name/'wire_request.json'
                bound_paths.append(wire_path)
                wire = read(wire_path)
                body = json.loads(wire['user_prompt'])
                supplied = {c['source_case_id']: c for c in body['already_seen_training']}
                summary = {'batch':batch, 'step':name, 'accepted':decision['accepted'],
                    'reason':decision.get('reason'), 'parent_bank_sha256':csha(parent_bank),
                    'proposed_bank_sha256':csha(decision['proposed_bank']),
                    'EC_projection_identical':task_view(parent_bank, 'EC') == task_view(decision['proposed_bank'], 'EC'),
                    'edits':decision.get('edit_audit'), 'proposal_tokens':decision.get('proposed_tokens'),
                    'teacher_current_sources':body['current_source_case_ids'],
                    'teacher_supplied_source_count':len(supplied),
                    'teacher_historical_feedback_count':len(body.get('rejected_candidate_feedback',[]))}
                transitions = []
                for before, after in zip(parent, proposed):
                    row = row_map[before['case_id'], 'EV']
                    bf = native_claim_feedback(before, targets[before['case_id']])
                    af = native_claim_feedback(after, targets[after['case_id']])
                    transitions.append({'case_id':before['case_id'], 'source_key':before['source_key'],
                        'batch':batch, 'is_current':before['case_id'] in current_ids,
                        'namespaces':sorted(allowable_namespaces(row)),
                        'native_delta_pp':100*(after['score']['f1']-before['score']['f1']),
                        'complete_delta_pp':100*(after['score']['full_output_f1']-before['score']['full_output_f1']),
                        'parent_invalid':bf['invalid_response'], 'proposal_invalid':af['invalid_response'],
                        'parent_errors':bf, 'proposal_errors':af,
                        'parent_raw_path':before['raw_call_path'], 'proposal_raw_path':after['raw_call_path'],
                        'same_raw_response':before['raw_call_path']==after['raw_call_path'],
                        'teacher_saw_source':before['case_id'] in supplied,
                        'facts':row['components']['facts'], 'public_solved_steps':row['components']['solved_steps'],
                        'target':targets[before['case_id']],
                        'parent_answer':(before['parsed'] or {}).get('answer'),
                        'proposal_answer':(after['parsed'] or {}).get('answer')})
                summary['cohorts'] = {}
                for cohort in ('current','prior'):
                    predicate = lambda r: (r['case_id'] in current_ids) == (cohort=='current')
                    p = [r for r in parent if predicate(r)]
                    q = [r for r in proposed if predicate(r)]
                    if not p:
                        continue
                    pm, qm = metrics(p)['EV'], metrics(q)['EV']
                    recorded = decision['proposed_whole_bank_acceptance']
                    for key in ('f1','full_output_f1','invalid_format'):
                        assert abs(pm[key]-recorded['parent_'+cohort]['EV'][key])<1e-12
                        assert abs(qm[key]-recorded['candidate_'+cohort]['EV'][key])<1e-12
                    selected = [t for t in transitions if t['is_current']==(cohort=='current')]
                    summary['cohorts'][cohort] = {'sources':len(p),
                        'parent_metrics':pm, 'proposal_metrics':qm,
                        'parent_error_counts':error_counts(p), 'proposal_error_counts':error_counts(q),
                        'native_delta_pp':100*(qm['f1']-pm['f1']),
                        'complete_delta_pp':100*(qm['full_output_f1']-pm['full_output_f1']),
                        'native_delta_contribution_from_new_invalid_pp':sum(t['native_delta_pp'] for t in selected if t['proposal_invalid'] and not t['parent_invalid'])/len(p),
                        'native_delta_contribution_from_both_parseable_pp':sum(t['native_delta_pp'] for t in selected if not t['parent_invalid'] and not t['proposal_invalid'])/len(p),
                        'improved_sources':sum(t['native_delta_pp']>1e-10 for t in selected),
                        'worsened_sources':sum(t['native_delta_pp']<-1e-10 for t in selected),
                        'same_response_sources':sum(t['same_raw_response'] for t in selected),
                        'worst_case_ids':[t['case_id'] for t in sorted(selected,key=lambda t:t['native_delta_pp'])[:5]]}
                summary['per_context'] = {}
                for context in sorted({'+'.join(t['namespaces']) for t in transitions}):
                    ts=[t for t in transitions if '+'.join(t['namespaces'])==context]
                    summary['per_context'][context]={'sources':len(ts),
                        'native_delta_pp':sum(t['native_delta_pp'] for t in ts)/len(ts),
                        'new_invalid':sum(t['proposal_invalid'] and not t['parent_invalid'] for t in ts),
                        'worsened_source_ids':[t['case_id'] for t in ts if t['native_delta_pp']<-1e-10]}
                summaries.append(summary)
                details.append({'step':name,'parent_bank':parent_bank,
                    'proposed_bank':decision['proposed_bank'],'delta':decision['delta'],
                    'transitions':transitions,'teacher_request_path':str(wire_path.relative_to(ROOT))})
        if decision['accepted']:
            bank=decision['candidate']
            latest={(r['case_id'],r['family']):r for r in decision['actual_replay']}
    assert csha(bank)==pub['bank_sha256']

evidence={'scope':'Existing TRAIN only; no TEST reads, teacher, actor or embedding calls',
          'source_sha256':{str(p.relative_to(ROOT)):sha(p) for p in bound_paths},
          'new_model_calls':0,'new_teacher_calls':0,'original_records_modified':False,
          'EV_proposals':summaries}
emit('existing_train_EV_audit_v1.json',evidence)
emit('existing_train_EV_case_transitions_v1.json',details)
for s in summaries:
    print(json.dumps({'batch':s['batch'],'accepted':s['accepted'],
        'cohorts':{k:{f:v[f] for f in ('sources','native_delta_pp','native_delta_contribution_from_new_invalid_pp',
             'native_delta_contribution_from_both_parseable_pp','parent_error_counts','proposal_error_counts')}
            for k,v in s['cohorts'].items()}},ensure_ascii=False),flush=True)
