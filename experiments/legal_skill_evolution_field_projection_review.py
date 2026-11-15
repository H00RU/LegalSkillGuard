"""Recheck actual TRAIN executions and costs without any model client."""
from pathlib import Path
import hashlib
import json
import sqlite3

from experiments import legal_skill_evolution_field_projection_integration as stage
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.native_observation_execution import evaluate
from legal_skill_guard.skill_evolution.objects import digest

ROOT=stage.ROOT
OUT=ROOT/'artifacts/legal_skill_evolution_field_projection_scopes_20261115'


def run():
    public,kernels=stage.acquired.runtime.previous.data();grading=stage.read(OUT/'TRAIN_grading.json')
    rows=[]
    for path in sorted(OUT.glob('*/*/*.json')):
        if path.parts[-3]not in ('native_residual','direct_inputs_first'):continue
        row=stage.read(path);sid=row['source'];lib=stage.read(OUT/'libraries'/(row['candidate']+'.json'))
        result=evaluate(lib,kernels[sid],public[sid]['views'][0]['public'],row['observation'],sid)
        score=grade_view(public[sid]['dataset'],public[sid]['views'][0],
            grading[sid][public[sid]['views'][0]['id']],result['answer'])
        valid=result['handled']and score['correct']and not any(
            w['source_review']['failures']for w in result['binding_executions'])
        rows.append({'source':sid,'condition':row['candidate'],'policy':row['read_policy'],
            'reads':len(row['reads']),'retained_original_artifact':str(path.relative_to(ROOT)),
            'original_sha256':digest(row),'original_handled':row['execution']['handled'],
            'reviewed_execution':result,'reviewed_native_score':score,'reviewed_core_correct':valid,
            'failed_observation_components':row['failed_observation_components'],'new_model_calls':0})
    conditions={}
    for row in rows:
        r=conditions.setdefault(row['condition']+'/'+row['policy'],{'correct':0,'total':0,'logical_reads':0})
        r['correct']+=int(row['reviewed_core_correct']);r['total']+=1;r['logical_reads']+=row['reads']
    report={'rows':rows,'conditions':conditions,'new_model_calls':0,'known_false_positive_excluded':True,
        'original_results_not_modified':True,'review_code_sha256':{str(p.relative_to(ROOT)):
            hashlib.sha256(p.read_bytes()).hexdigest()for p in [Path(__file__),
            ROOT/'legal_skill_guard/skill_evolution/observation_source_review.py',
            ROOT/'legal_skill_guard/skill_evolution/partial_native_proof.py']},'goal_complete':False}
    (OUT/'unbound_reviewed_results.json').write_text(json.dumps(report,indent=2)+'\n')
    with sqlite3.connect('file:'+str(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3')+'?mode=ro',uri=True)as db:
        calls=db.execute('select * from calls order by id').fetchall()
    prefixes=('legal_skill_evolution_field_projection_integration_20261115:',
        'legal_skill_evolution_field_projection_scopes_20261115:')
    old=[r for r in calls if not r[0].startswith(prefixes)]
    before=stage.read(ROOT/'artifacts/legal_skill_evolution_field_projection_integration_20261115/before.json')
    assert len(old)==before['ledger_rows']
    assert hashlib.sha256(json.dumps(old,ensure_ascii=False,default=str).encode()).hexdigest()==before['old_ledger_sha256']
    requests=[];counts={};increments={}
    for row in calls:
        counts[(row[1],row[6])]=counts.get((row[1],row[6]),0)+1
        if not row[0].startswith(prefixes):continue
        key=(row[0].split(':',1)[0],row[1],row[6]);increments[key]=increments.get(key,0)+1
        value=json.loads(row[-1])if row[-1]else{}
        requests.append({'id':row[0],'source':row[4],'status':row[6],'usage':value.get('usage'),
            'elapsed_seconds':value.get('elapsed_seconds'),'finish_reason':value.get('finish_reason')})
    cost={'counts':[[*k,n]for k,n in counts.items()],'increments':[[*k,n]for k,n in increments.items()],
        'all_11875_prior_rows_unchanged':True,'requests':requests,'new_teacher_calls':0,
        'cash_invoice_and_GPU_allocation_unknown':True,
        'prompt_tokens':sum((r['usage']or{}).get('prompt_tokens',0)for r in requests),
        'completion_tokens':sum((r['usage']or{}).get('completion_tokens',0)for r in requests),
        'request_elapsed_seconds':sum(r['elapsed_seconds']or 0 for r in requests)}
    (OUT/'unbound_stage_cost.json').write_text(json.dumps(cost,indent=2)+'\n')
    print(json.dumps({'conditions':conditions,'new_requests':len(requests),'counts':cost['counts']}),flush=True)


if __name__=='__main__':run()
