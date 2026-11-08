"""Read saved current-build records and the physical ledger; never generate."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    stage = ROOT / 'artifacts/rr_method_runtime_20261107' / args.run_id
    seal = json.loads((stage / 'seal.json').read_text())
    with sqlite3.connect('file:' + str((ROOT / seal['ledger_path']).resolve()) + '?mode=ro', uri=True) as db:
        charged = db.execute('select role,status,count(*) from calls group by role,status').fetchall()
        current = db.execute('select role,status,count(*) from calls where id like ? group by role,status', (args.run_id + ':%',)).fetchall()
    rows = []
    for sid in seal['sources']['train']:
        key = hashlib.sha256(json.dumps(sid,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
        path = stage / 'build/sources' / (key + '.json')
        if not path.exists():
            continue
        record = json.loads(path.read_text())
        pred = record['prediction']; result = pred['result']; learning = record['learning']
        compiled = [h for h in pred['history'] if h.get('program_status') in {'source_IR_compiled','model_Horn_IR_compiled'}]
        execution = result.get('execution') or (result.get('assessment') or {}).get('execution') or {}
        rows.append({
            'source': sid, 'dataset': record['dataset'], 'record_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'source_IR_typed_in_any_attempt': bool(compiled), 'final_program_status': result['program_status'],
            'certificate_status': result['certificate_status'], 'answer': result['answer'],
            'TRAIN_match': record['score']['task_correct'], 'fallback': result.get('fallback_used',False),
            'A_actual': result.get('A_main_path_executed',False), 'B_actual': result.get('B_main_path_executed',False),
            'independent_executor_compilation': result.get('independent_executor_compilation'),
            'template_instance': result.get('actual_executor_template_instantiation'),
            'pattern_uses': execution.get('pattern_uses',[]), 'learning_status': learning['status'],
            'learned_pattern': learning.get('learned_pattern'),
            'compiler_material_count': len(record.get('compiler_learning',{}).get('templates',[])),
            'logical_requests': pred['model_calls'],
            'exact_paid_wire_replays': sum(bool(c.get('physical_origin_call_id')) for c in pred['calls']),
            'requests': [{k:c.get(k) for k in ('step','purpose','request_hash','usage','elapsed_seconds','physical_origin_call_id')} for c in pred['calls']],
            'selection_bases': [a.get('selection_basis',a.get('kind')) for a in pred['translation_actions']],
            'final_error': result.get('error'),
            'source_semantic_review_not_implied_by_type_or_TRAIN_match': True,
        })
    def totals(items):
        return {'sources':len(items), **{field:sum(bool(r[field]) for r in items) for field in
            ('source_IR_typed_in_any_attempt','TRAIN_match','fallback','A_actual','B_actual','template_instance')},
            'learning_status':dict(Counter(r['learning_status'] for r in items)),
            'final_program_status':dict(Counter(r['final_program_status'] for r in items))}
    batches = sorted((stage / 'build/batches').glob('B*.json'))
    dev_path = stage / 'dev/scores.json'
    value = {'captured_utc':datetime.now(timezone.utc).isoformat(), 'run_id':args.run_id,
        'original_fixed_sources':128, 'committed_sources':len(rows), 'completed_batches':len(batches),
        'ledger_role_status_counts':charged, 'current_run_new_physical_role_status_counts':current,
        'totals':totals(rows), 'by_dataset':{name:totals([r for r in rows if r['dataset']==name]) for name in sorted({r['dataset'] for r in rows})},
        'source_rows':rows, 'build_completion_saved':(stage/'build/completion.json').exists(),
        'six_arm_DEV_complete':dev_path.exists() and json.loads(dev_path.read_text()).get('DEV_complete',False),
        'new_model_or_oracle_calls_by_this_audit':0, 'DEV_or_TEST_labels_read':False,
        'component_results_not_pooled_with_uniform_build':True, 'full_goal_complete':False}
    out=ROOT/args.output
    temporary=out.with_suffix(out.suffix+'.tmp');temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');temporary.replace(out)
    print(json.dumps({k:v for k,v in value.items() if k not in {'source_rows','by_dataset'}},ensure_ascii=False))


if __name__ == '__main__':
    main()
