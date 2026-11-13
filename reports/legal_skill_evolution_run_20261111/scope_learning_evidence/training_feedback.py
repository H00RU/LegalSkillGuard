"""Build semantic feedback from existing acquisition TRAIN and physical outputs."""
from collections import Counter,defaultdict
import json
from pathlib import Path
import sqlite3

ROOT=Path(__file__).resolve().parents[3]
FOLDER=ROOT/'artifacts/legal_skill_evolution_scope_learning_20261113/execution'
read=lambda p:json.loads(p.read_text())


def run():
    data=read(FOLDER/'input.json');allowed=set(data['sources']);gold=defaultdict(set)
    for row in data['existing_acquired_examples']:
        gold[row['source'],row['operation'],row['focus_unit_id']].add(row['choice'])
    with sqlite3.connect(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3') as db:
        settled={r[0]:json.loads(r[1]) for r in db.execute("select id,result from calls where status='completed' and role='executor'")}
    rows=[];rejected=[]
    prior=ROOT/'artifacts/legal_skill_evolution_semantic_operations_v2_20261113'
    for file in sorted((prior/'calls').glob('*/request.json')):
        request=read(file)
        if request.get('source') not in allowed or request.get('id') not in settled:continue
        try:body=json.loads(request['payload']['messages'][1]['content'])
        except (ValueError,KeyError,IndexError):continue
        if not isinstance(body,dict) or 'current_queries' not in body:continue
        result=settled[request['id']]
        if result.get('finish_reason')!='stop':continue
        try:value=json.loads(result['content']);raw=value['answers']
        except (ValueError,KeyError):continue
        if isinstance(raw,dict):answers=[{'id':i,**v} for i,v in raw.items()]
        else:answers=raw
        ids=[a['id'] for a in answers];queries=body['current_queries']
        if len(set(ids))!=len(ids) or set(ids)!={q['id'] for q in queries}:
            rejected.append({'physical_call_id':request['id'],'reason':'Ambiguous/missing query identity; no target selected.'});continue
        by_id={a['id']:a for a in answers};ops={o['name']:o for o in body['operations']}
        for q in queries:
            focus=q.get('focus_unit_id',q['unit_ids'][-1]);choices=gold[request['source'],q['operation'],focus]
            if len(choices)!=1:continue
            expected=next(iter(choices));a=by_id[q['id']];operation=ops[q['operation']]
            declared=[c['name'] for c in operation['choices']]+['unknown']
            rows.append({'physical_call_id':request['id'],'source':request['source'],
                'query_id':q['id'],'operation':q['operation'],'focus_unit_id':focus,'unit_ids':q['unit_ids'],
                'expected_from_acquired_example':expected,'actual_choice':a['choice'],
                'matches_acquired_example':a['choice']==expected,'expected_choice_declared':expected in declared,
                'explicit_focus_in_prompt':'focus_unit_id' in q,'batch_queries':len(queries),
                'batch_operations':len(ops),'same_parent_demonstrations':sum(e['source']==request['source'] for e in operation['examples']),
                'target_is_acquired_supervision_not_independent_legal_gold':True})
    wrong=[r for r in rows if not r['matches_acquired_example']]
    summary={'observations':len(rows),'physical_calls':len({r['physical_call_id'] for r in rows}),
        'mother_sources':len({r['source'] for r in rows}),'mistakes_against_acquired_targets':len(wrong),
        'mistakes_with_correct_alternative_already_declared':sum(r['expected_choice_declared'] for r in wrong),
        'unknown_mistakes':sum(r['actual_choice']=='unknown' for r in wrong),
        'ambiguous_wire_records_excluded':len(rejected),'new_model_calls':0,
        'no_reuse_source_or_native_labels_included':True,'cannot_claim_cross_source_learning_from_one_parent':True}
    value={'summary':summary,'rows':rows,'wire_failures':rejected,'goal_complete':False}
    path=FOLDER/'training_semantic_feedback.json'
    raw=json.dumps(value,ensure_ascii=False,indent=2)+'\n'
    if path.exists():assert path.read_text()==raw
    else:path.write_text(raw)
    print(json.dumps(summary))

if __name__=='__main__':run()
