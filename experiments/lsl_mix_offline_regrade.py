"""Recover exact semantic-equivalent Horn annotations from existing responses.

This makes no model call. It verifies all cached proposal request hashes, keeps
the original bank and grading evidence, and writes a new explicit grader bank.
"""
from pathlib import Path
from collections import Counter
import json
import os
import sqlite3
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from legal_skill_guard.lsl.data import load_json,write_json,sha
from legal_skill_guard.lsl.mixed_candidates import proposal_request,build_tables
from legal_skill_guard.lsl.physical import payload
from legal_skill_guard.rr.coverage import digest


def main():
    out=ROOT/'artifacts/lsl_mixed256_20261110';old=out/'candidates/common-sparse/train';new=out/'candidates/common-canonical/train'
    assert (old/'local/complete.json').exists()
    if (new/'local/complete.json').exists():print('Canonical offline grading already complete; preserving bank');return
    db=sqlite3.connect(out.parent/'rr_v2_preflight/research_ledger.sqlite3');before=db.execute('select count(*) from calls').fetchone()[0]
    assert db.execute("select count(*) from calls where status='reserved'").fetchone()[0]==0
    rows={r['key']:r for r in load_json(out/'open_dataset.json')['records'] if r['split']=='train'}
    primary=load_json(old/'results.json');responses=load_json(old/'local/responses.json');bykey={p['source']:p['result'] for p in primary}
    assert len(rows)==256 and set(rows)==set(bykey)
    checked=0
    for key,res in responses.items():
        q=proposal_request(rows[key],bykey[key]['parsed'])
        request={'thinking':False,'primary_call_id':bykey[key]['call_id'],'payload':payload(q['messages'],q['schema'],model='common')}
        assert digest(request)==res['request_hash'],key
        checked+=1
    codes=['legal_skill_guard/lsl/horn_codec.py','legal_skill_guard/lsl/native_semantics.py','legal_skill_guard/lsl/mixed_candidates.py',
           'legal_skill_guard/rr/public_horn.py','legal_skill_guard/lsl/native_scope.py','experiments/lsl_mix_offline_regrade.py']
    new.mkdir(parents=True,exist_ok=True);(new/'local').mkdir(exist_ok=True)
    cfg={'stage':'common-canonical','checkpoint_sha256':load_json(old/'config.json')['checkpoint_sha256'],
         'parent_config_sha256':sha(old/'config.json'),'primary_results_sha256':sha(old/'results.json'),
         'cached_local_responses_sha256':sha(old/'local/responses.json'),'cached_request_hashes_verified':checked,
         'changes':['Controlled-English verb and entity-case serialization shared by all arms',
                    'Exact per-rule alpha and unordered conjunction/rule comparison',
                    'Native fact annotation aligned to its source quote, never guessed by list position'],
         'code':{p:sha(ROOT/p)for p in codes},'new_model_calls':0,'no_missing_semantics_added':True,'TEST':False}
    write_json(new/'config.json',cfg)
    if not (new/'results.json').exists():os.link(old/'results.json',new/'results.json')
    assert sha(new/'results.json')==cfg['primary_results_sha256']
    if not (new/'local/responses.json').exists():os.link(old/'local/responses.json',new/'local/responses.json')
    started=time.monotonic();tables=[]
    for p in primary:
        key=p['source'];row=rows[key];res=responses.get(key,{});raw=p['result'];value=raw.get('parsed')
        if value is None or raw.get('finish')!='stop':
            table={'source':key,'dataset':row['dataset'],'valid':False,'errors':['incomplete/unparseable primary'],'blocks':[],'squares':[]}
        else:table=build_tables(row,value,res.get('parsed') if res.get('finish')=='stop' else None)
        tables.append(table);write_json(new/'local/tables'/(digest(key)+'.json'),table)
    write_json(new/'local/tables.json',tables)
    statuses=Counter(b['credit']['status'] for t in tables for b in t['blocks'])
    after=db.execute('select count(*) from calls').fetchone()[0];assert before==after
    summary={'sources':256,'valid_primary_executions':sum(t['valid'] for t in tables),
        'credit_statuses':dict(statuses),'by_dataset':{},'cached_physical_requests_verified':checked,
        'new_model_calls':0,'ledger_rows_before':before,'ledger_rows_after':after,'seconds':time.monotonic()-started,
        'old_bank_preserved':str(old.relative_to(ROOT)),'not_a_trained_method_result':True,'goal_complete':False}
    for d in sorted({r['dataset']for r in rows.values()}):
        ts=[t for t in tables if t['dataset']==d]
        summary['by_dataset'][d]={'sources':len(ts),'valid':sum(t['valid']for t in ts),
            'stable_blocks':sum(b['credit']['status']=='stable'for t in ts for b in t['blocks']),
            'squares':sum(len(t['squares'])for t in ts)}
    write_json(new/'local/config.json',cfg);write_json(new/'local/regrade_summary.json',summary)
    write_json(new/'local/complete.json',{'sources':256,'new_model_calls':0,'config_sha256':sha(new/'local/config.json')})
    write_json(new/'complete.json',{'sources':256,'new_model_calls':0,'config_sha256':sha(new/'config.json')})
    print(json.dumps(summary,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
