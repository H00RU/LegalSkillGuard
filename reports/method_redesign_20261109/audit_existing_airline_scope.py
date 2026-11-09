"""Read one existing public TRAIN case; compare local fee composition only.

No generated reader, native answer, grade, new source or model call is used.
The policy-to-fee mapping below is an explicit author reference for this local
software audit. It is not a learned policy or a complete benchmark predictor.
"""
import hashlib,json,re,sqlite3
from pathlib import Path
from legal_skill_guard.rr.checkpoint import immutable_json

ROOT=Path(__file__).resolve().parents[2]
STAGE=ROOT/'artifacts/rr_method_redesign_20261109/existing_airline_scope_v1_20261110'
DB=ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3'


def snapshot():
    with sqlite3.connect('file:'+str(DB)+'?mode=ro',uri=True) as c:
        return {t:c.execute('SELECT * FROM '+t+' ORDER BY 1').fetchall() for t in ['calls','meta','oracle_views']}


def main():
    before=snapshot()
    records=json.loads((ROOT/'data/packets/rr_v2/public_train.json').read_text())['sources']
    case=next(r for r in records if r['dataset']=='RuleArena_Airline')
    assert case['native_split']=='unsplit'  # Original corpus has no native split; project TRAIN above is fixed.
    public=case['public'];policy=public['rules'];prompt=public['prompt']
    assert 'Basic Economy' in prompt and 'Phoenix to Rio de Janeiro' in prompt
    clause='The higher fee between oversize and overweight applies, in addition to the checked bag fee.'
    assert clause in policy
    items=[]
    pattern=r'(?m)^(\d+)\. (.*?): (\d+) x (\d+) x (\d+) inches, (\d+) lbs;'
    for m in re.finditer(pattern,prompt):
        items.append({'id':int(m[1]),'description':m[2],'dimensions':[int(m[k]) for k in [3,4,5]],'weight_lbs':int(m[6])})
    assert len(items)==5
    carry=[r for r in items if all(a<=b for a,b in zip(r['dimensions'],[22,14,9]))]
    assert [r['id'] for r in carry]==[1]
    assert not all(a<=b for a,b in zip(carry[0]['dimensions'],[18,14,8]))
    checked=[r for r in items if r not in carry]
    base=[60,100,200,200]
    rows=[]
    for r,b in zip(checked,base):
        size=sum(r['dimensions']);weight=r['weight_lbs']
        assert size<=115 and weight<=70
        oversize=0 if size<=62 else 30 if size<=65 else 150
        overweight=0 if weight<=50 else 30 if weight<=53 else 100
        rows.append(r|{'linear_inches':size,'base_fee':b,'oversize_fee':oversize,'overweight_fee':overweight})
    correct=sum(r['base_fee']+max(r['oversize_fee'],r['overweight_fee']) for r in rows)
    global_max=sum(base)+max(sum(r['oversize_fee'] for r in rows),sum(r['overweight_fee'] for r in rows))
    additive=sum(r['base_fee']+r['oversize_fee']+r['overweight_fee'] for r in rows)
    assert (correct,global_max,additive)==(870,800,990)
    assert snapshot()==before
    output={'source':case['key'],'selection':'first existing RuleArena_Airline project TRAIN row; no outcome selection',
        'project_split':'train','native_split':case['native_split'],
        'policy_sha256':hashlib.sha256(policy.encode()).hexdigest(),'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest(),
        'policy_composition_clause':clause,'public_prompt':prompt,'actual_items':items,
        'carry_on':carry,'checked_fee_rows':rows,'correct_local_checked_fee':correct,
        'wrong_global_max_fee':global_max,'wrong_add_all_fee':additive,
        'role_of_manual_adapter':'author reference derived from source table; not generated reader or learned skill',
        'local_contract':'Basic Economy US to Brazil, one fitting carry-on, four remaining bags; base/size/weight fees assumed correctly source-mapped',
        'first_base_fee':{'source':'First Bag South America excluding Colombia/Ecuador/Peru/Guyana/Suriname','value':60},
        'second_base_fee':{'source':'Second Bag South America excluding Guyana/Suriname','value':100},
        'third_fourth_base_fees':[200,200],
        'source_scope_pattern':'sum per bag of base plus max(size fee,weight fee); max after global sums is different',
        'ordinary_correct_cache_can_express_same_composition':True,'shared_annual_cap_operator_not_forced_on_Airline':True,
        'not_a_new_method_contribution_or_native_prediction':True,'native_label_read_or_grade_added':False,
        'new_original_sources':0,'new_model_calls':0,'new_oracle_views':0,'ledger_rows_unchanged':True,'goal_complete':False}
    immutable_json(STAGE/'local_scope_comparison.json',output)
    print(json.dumps({k:output[k] for k in ['source','correct_local_checked_fee','wrong_global_max_fee','wrong_add_all_fee','new_model_calls','new_oracle_views','ledger_rows_unchanged']},ensure_ascii=False))


if __name__=='__main__':main()
