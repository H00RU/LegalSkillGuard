"""Model-proposed local records, with a fixed common primary acquisition bank."""
from pathlib import Path
import argparse
import json
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from legal_skill_guard.lsl.data import load_json,write_json,sha
from legal_skill_guard.lsl.mixed_candidates import proposal_request,build_tables,_norm_native_constraints
from legal_skill_guard.lsl.native_semantics import predict,norm_graph
from legal_skill_guard.lsl.physical import dispatch_many,payload
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.method_ledger import MethodLedger


def run(out,stage,alias='common',split='train'):
    base=out/'candidates'/stage/split
    if not (base/'complete.json').exists():raise ValueError('Primary acquisition has not reached a safe completed boundary')
    primary=load_json(base/'results.json');rows={r['key']:r for r in load_json(out/'open_dataset.json')['records'] if r['split']==split}
    location=base/'local';location.mkdir(exist_ok=True)
    files=['experiments/lsl_mix_local_candidates.py','legal_skill_guard/lsl/mixed_candidates.py',
           'legal_skill_guard/lsl/native_semantics.py','legal_skill_guard/lsl/safe_program.py',
           'legal_skill_guard/lsl/native_scope.py',
           'legal_skill_guard/lsl/local_credit.py','legal_skill_guard/lsl/physical.py',
           'legal_skill_guard/lsl/native_training.py','legal_skill_guard/lsl/native_schema.py',
           'legal_skill_guard/lsl/contract_wire.py','legal_skill_guard/lsl/role_codec.py',
           'legal_skill_guard/lsl/scalar_proposals.py','legal_skill_guard/lsl/composition_data.py',
           'legal_skill_guard/lsl/projection.py','legal_skill_guard/lsl/semantic_witness.py']
    files+=['legal_skill_guard/lsl/horn_codec.py','legal_skill_guard/rr/public_horn.py']
    config={'stage':stage,'split':split,'primary_config_sha256':sha(base/'config.json'),
            'primary_results_sha256':sha(base/'results.json'),'code':{f:sha(ROOT/f) for f in files},
            'thinking':False,'source_selection':'all fixed sources; first four source-supported slots, selected before outcomes',
            'gold_in_requests':False,'local_alternatives_per_block':2,'common_context_limit':8}
    if (location/'config.json').exists() and load_json(location/'config.json')!=config:raise ValueError('Local candidate binding changed')
    write_json(location/'config.json',config)
    run_id='LSG-MIX256-local-'+stage+'-'+split
    ledger=MethodLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=run_id,
        binding={'code_hash':digest(config['code']),'config_hash':digest(config)},
        sources={s:[r['key'] for r in load_json(out/'open_dataset.json')['records'] if r['split']==s] for s in ('train','dev')},
        authorization_hash=sha(ROOT/'reports/legal_five_dataset_amendment_20261110/protocol.json'),
        question='Acquire source-local alternatives before native execution, without answer-directed program repair')
    requests=[];notes={};original={p['source']:p['result'] for p in primary}
    for p in primary:
        key=p['source'];row=rows[key];value=p['result'].get('parsed')
        try:
            if p['result'].get('finish')!='stop' or value is None:raise ValueError('Primary response incomplete/unparseable')
            minimal={k:row[k] for k in ('dataset','key','family_id','public')}
            if not predict(minimal,value)['valid']:raise ValueError('Primary native execution is invalid; no jointly executable local pair')
            q=proposal_request(row,value)
            if q is None:notes[key]={'status':'no_local_proposal_interface_or_slot'};continue
            if split=='train' and row['dataset']=='NormBench':
                graph=norm_graph(row,value)
                if not any(_norm_native_constraints(row,graph,s['slot']) for s in q['metadata']['slots']):
                    notes[key]={'status':'all_fixed_slots_excluded_by_other_independent_dense_native_fields',
                                'slots_selected_before_QA_outcomes':q['metadata']['slots']};continue
            public_only={k:row[k] for k in ('dataset','key','family_id','public')}
            if proposal_request(public_only,value)!=q:raise ValueError('Proposal depends on grading-only fields')
            requests.append({'call_id':run_id+':'+digest(key),'source':key,
                'purpose':'method_primitive_observation' if split=='train' else 'method_dev',
                'request':{'thinking':False,'primary_call_id':p['result']['call_id'],
                           'payload':payload(q['messages'],q['schema'],model=alias)}})
        except Exception as e:notes[key]={'status':'unavailable_primary_or_alignment','error':type(e).__name__+': '+str(e)}
    local={};write_json(location/'selection.json',{'selected':[r['source'] for r in requests],'excluded':notes,
        'source_order_before_QA_outcomes':True,'independent_native_constraint_screening':True})
    for start in range(0,len(requests),8):
        for f,h in config['code'].items():
            if sha(ROOT/f)!=h:raise ValueError('Live local candidate code changed: '+f)
        batch=requests[start:start+8];results=dispatch_many(ledger,batch,location/'raw',concurrency=8)
        for req,res in zip(batch,results):local[req['source']]=res
        write_json(location/'responses.json',local)
        print(json.dumps({'local_proposal_sources':len(local),'total':len(requests)}),flush=True)
    if split=='train':
        tables=[]
        for p in primary:
            key=p['source'];res=local.get(key,{});value=p['result'].get('parsed')
            if value is None or p['result'].get('finish')!='stop':
                tables.append({'source':key,'dataset':rows[key]['dataset'],'valid':False,'errors':['incomplete/unparseable primary'],'blocks':[],'squares':[]});continue
            table=build_tables(rows[key],value,res.get('parsed') if res.get('finish')=='stop' else None)
            tables.append(table)
            write_json(location/'tables'/ (digest(key)+'.json'),table)
        write_json(location/'tables.json',tables)
        print(json.dumps({'table_sources':len(tables),'valid':sum(r['valid'] for r in tables),
            'stable_local_blocks':sum(b.get('credit',{}).get('status')=='stable' for r in tables for b in r['blocks']),
            'native_squares':sum(len(r['squares']) for r in tables)}),flush=True)
    write_json(location/'complete.json',{'local_requests':len(requests),'config_sha256':sha(location/'config.json'),
               'TEST':False,'trained_method_yet':False,'goal_complete':False})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage',required=True);p.add_argument('--alias',default='common');p.add_argument('--split',choices=('train','dev'),default='train')
    p.add_argument('--out',default='artifacts/lsl_mixed256_20261110');a=p.parse_args();run((ROOT/a.out).resolve(),a.stage,a.alias,a.split)
