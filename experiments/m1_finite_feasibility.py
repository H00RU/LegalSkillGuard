"""Locked small TRAIN feasibility check; no full study, teacher, DEV or TEST.

Reuse the18 original OE port reads. Compare fixed full ports, development-selected
F-derived residual ports, and development-selected ordinary prompt variants.
At most six new loopback reads, no retries, and no outcome-dependent additions.
"""
from copy import deepcopy
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import sqlite3

from experiments.two_method_annotate import inputs
from legal_skill_guard.paired_interfaces.production_decode import decode_response
from legal_skill_guard.paired_interfaces.reference_wire import reference_wire
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'artifacts/two_method_followthrough_20261116'
OUT = BASE/'M1_feasibility_20261117/finite_real'
OLD = BASE/'asset_port_reads_v1/71eee85048e48fe8ebf7f4a190c4df814cdc5f36efc1b1c450123c3e05b72f3c'
CARDS = BASE/'asset_port_source_reviews_v1/b34952ae92340022b6ab0b26babba0ff77d5dc9038a6029afe1321042e0814b0/manifest.json'
ASSETS = BASE/'formal_read_preflight_v1/6e22e5920c3df1aac061f9bd159788e44b30c9bd570fc9f740c4c0894a56058f/plan_assets.json'
LEDGER = ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3'
PROMPT = '''\nBefore producing the JSON, check the complete source inventory against every requested field.
Use the declared field dictionary literally. Keep each item's own quote and source order.
Use a contiguous exact quote, and make the description exactly the described source item.
Apply only the explicit public assumptions printed in this input; explicit contrary facts take priority.
For categories that cannot be determined from this input retain unknown/null. Never mark an unknown as false.
Do not add commentary or a legal answer. Check parallel fields, statuses and null values against the schema.
'''


def read(path): return json.loads(path.read_text())
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare():
    manifest = read(CARDS)
    reviews = {(r['source'],r['view']):r for r in manifest['reviews']}
    assert len(reviews) == 6 and {r['role'] for r in reviews.values()} == {'development','calibration'}
    public = {s['key']:s for s in read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')
              if s['key'] in {r['source'] for r in reviews.values()}}
    raw_requests = read(OLD/'requests.json')
    plans = {p['version']:p for ps in read(ASSETS)['OE_by_public_regime'].values() for p in ps}
    cases = []
    for request in raw_requests:
        source = public[request['source']]; task, mapping = inputs(source)
        v = next(v for v in task['views'] if v['view_id'] == request['opaque_view'])
        native = {v['id']:v for v in source['views']}
        names = [n for n,opaque in mapping.items() if opaque == request['opaque_view']]
        plan = plans[request['version']]
        row = reviews[source['key'],request['opaque_view']]
        assert sha(ROOT/row['card_path']) == row['card_sha256']
        card = read(ROOT/row['card_path'])
        assert digest(v['source_units']) == card['source_units_sha256']
        view = {'source_units':v['source_units'],'native_tasks':names,
                'native_public':{n:native[n]['public'] for n in names}, 'scope':None}
        decoded_path = OLD/'reads'/digest([source['key'],request['opaque_view'],request['version']])/'decoded.json'
        record = read(decoded_path)
        call = OLD/'calls'/digest(record['physical_call_id'])
        original = read(call/'result.json')
        with sqlite3.connect('file:'+str(LEDGER)+'?mode=ro',uri=True) as db:
            ledger = db.execute('select status,source,result from calls where id=?',(record['physical_call_id'],)).fetchone()
        assert ledger[:2] == ('completed',source['key']) and json.loads(ledger[2]) == original
        response = {'content':json.dumps(reference_wire('OpenExempt',plan,card,v['source_units'])), 'finish_reason':'stop'}
        probe = decode_response(source,view,plan,response)
        assert not probe['production_errors'], (source['key'], request['opaque_view'], request['plan'])
        current = decode_response(source,view,plan,original)
        cases.append({'source':source,'role':row['role'],'view_id':request['opaque_view'],
            'view':view,'plan':plan,'request':request,'original_response':original,
            'physical_call_id':record['physical_call_id'],'old_call_directory':str(call.relative_to(ROOT)),
            'source_card':card,'native_views':{n:native[n] for n in names},
            'reference_probe':probe,'current_actual':current})
    assert len(cases) == 18
    # Exact program certificates are retained; current F/code must match those certificates.
    program = BASE/'offline_asset_module_v1/8801811b5d525a66ac767720a631710acb2078c9ac759e3d66d4a8da763ea9ef'
    old_protocol = read(program/'protocol.json')
    for name in ['legal_skill_guard/paired_interfaces/program_residual.py',
                 'legal_skill_guard/paired_interfaces/asset_interfaces.py']:
        assert sha(ROOT/name) == old_protocol['source_sha256'][name]
    bindings = {str(p.relative_to(ROOT)):sha(p) for p in sorted((ROOT/'legal_skill_guard/paired_interfaces').glob('*.py'))}
    for p in [Path(__file__),ROOT/'legal_skill_guard/skill_evolution/clients.py',ROOT/'legal_skill_guard/rr/client.py',
              ROOT/'legal_skill_guard/skill_evolution/native.py', ROOT/'legal_skill_guard/skill_evolution/ledger.py']:
        bindings[str(p.relative_to(ROOT))] = sha(p)
    protocol = {'name':'M1_fixed_original_OE_feasibility_v1','source_sha256':bindings,
        'source_manifest_sha256':sha(CARDS),'old_requests_sha256':sha(OLD/'requests.json'),
        'executor':read(BASE/'pilot_lock.json')['executor'],
        'source_ids':sorted(public),'development_mothers':1,'calibration_diagnostic_mothers':2,
        'not_independent_or_blind_test':True, 'original_reference_views_preserved':177,
        'arms':{'fixed':'records; frozen full ports',
                'M1':'choose records or automatically residualized local_records on development only',
                'ordinary_prompt':'choose records or records plus the one frozen generic prompt on development only'},
        'ordinary_prompt_variant':PROMPT,'candidates_per_selection_arm':2,
        'selection_rule':'strict increase in development mother-macro native grade; ties retain fixed records',
        'equal_allocated_budget_per_arm':{'development_reads':4,'diagnostic_reads':4,
            'max_output_tokens_per_read':8192,'max_context_tokens':32768,'teacher_reads':0},
        'fixed_arm_unused_search_budget_not_spent_as_dummy_calls':True,
        'actual_spending_not_claimed_equal':True,'existing_outputs_reused':18,'max_new_physical_calls':6,
        'new_calls_only_for_ordinary_prompt_variant':True,'all_same_source_units_and_public_context':True,
        'all_use_same_fixed_F_and_shared_decoder':True,
        'M1_alone_changes_F_read_set_and_paired_consumer_via_exact_static_context_transform':True,
        'reference_outputs_not_model_accuracy':True,'no_full_training_DEV_TEST':True,
        'no_gain_driven_extension_or_retry':True,
        'stop_decision':'no diagnostic improvement attributable to generated transformation => stop current M1 expansion; no new sources or prompt variants',
        'old_program_equivalence_checks':read(program/'checks.json')}
    immutable_json(OUT/'protocol.json',protocol)
    immutable_json(OUT/'offline_cases.json',cases)
    immutable_json(OUT/'offline_gate.json',{'reference_probes':18,'decode_rejects':0,
        'reference_native_handled':sum(v['handled'] for c in cases for v in c['reference_probe']['native'].values()),
        'actual_reused_native_handled':sum(v['handled'] for c in cases for v in c['current_actual']['native'].values()),
        'input_unknowns_and_F_coverage_gaps_not_filled':True,'new_calls':0})
    return protocol,cases


def prediction(case, name, response):
    plan = deepcopy(case['plan'])
    return {'source':case['source']['key'],'role':case['role'],'view':case['view_id'],'candidate':name,
            'decoded':decode_response(case['source'],case['view'],plan,response)}


def choose(development_rows):
    assert development_rows and all(r['role']=='development' for r in development_rows)
    def mean(name):
        values=[r['grade'] for r in development_rows if r['candidate']==name]
        assert len(values)==2 and all(v is not None for v in values)
        return sum(values)/len(values)
    base=mean('records')
    return {'fixed':'records','M1':'local_records' if mean('local_records')>base else 'records',
            'ordinary_prompt':'prompt_records' if mean('prompt_records')>base else 'records'}


def run():
    protocol,cases=prepare()
    # Mandatory publication-before-generation condition; not a bypass of formal gates.
    publication=read(BASE/'M1_feasibility_20261117/publication_verified.json')
    assert publication['status']=='uploaded_and_independently_verified'
    OUT.mkdir(parents=True,exist_ok=True)
    lock=(OUT/'driver.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    for n,h in protocol['source_sha256'].items(): assert sha(ROOT/n)==h,n
    with sqlite3.connect('file:'+str(LEDGER)+'?mode=ro',uri=True) as db:
        assert db.execute("select count(*) from calls where status='reserved'").fetchone()[0]==0
    run_id='M1_finite_feasibility_20261117_'+digest(protocol)[:16]
    sources={'train':protocol['source_ids'],'dev':[],'test':[]}
    ledger=EvolutionLedger(LEDGER,run_id=run_id,sources=sources,binding={'protocol':digest(protocol)})
    executor=FrozenExecutor(ledger,OUT,protocol['executor']);executor.exact_replay_roots=[OLD]
    immutable_json(OUT/'readiness.json',executor.readiness())
    predictions=[];used_calls=[]
    for c in cases:
        if c['plan']['name'] in ('records','local_records'):
            r=prediction(c,c['plan']['name'],c['original_response']);r.update(physical_call_id=c['physical_call_id'],cached_reanalysis=True)
            predictions.append(r)
    immutable_json(OUT/'reused_predictions_before_grading.json',predictions)
    def prompt_read(c):
        messages=deepcopy(c['request']['messages']);messages[0]['content']+=PROMPT
        call_id=run_id+':prompt:'+digest([c['source']['key'],c['view_id']])
        with ledger.transaction() as db:
            count=db.execute('select count(*) from calls where id like ?',(run_id+':%',)).fetchone()[0]
            exists=db.execute('select status from calls where id=?',(call_id,)).fetchone()
        if not exists and count>=6: raise RuntimeError('Locked six-call maximum reached')
        token=executor.tokenize(messages,thinking=False)
        assert token['count']+protocol['executor']['max_tokens']<=protocol['executor']['context_tokens']
        immutable_json(OUT/'tokenization'/(digest(call_id)+'.json'),{'input_tokens':token['count'],'max_output':8192})
        print(json.dumps({'dispatch':c['source']['key'],'view':c['view_id'],'role':c['role'],'call_id':call_id}),flush=True)
        response=executor.generate(call_id,source=c['source']['key'],purpose='skill_actor',messages=messages,thinking=False,schema=c['plan']['schema'])
        row=prediction(c,'prompt_records',response);row.update(physical_call_id=response.get('reused_physical_call_id',call_id),cached_reanalysis=bool(response.get('reused_physical_call_id')))
        immutable_json(OUT/'prompt_predictions'/(digest(call_id)+'.json'),row);used_calls.append(call_id);return row
    dev_cases=[c for c in cases if c['role']=='development' and c['plan']['name']=='records']
    dev_prompt=[prompt_read(c) for c in dev_cases]
    immutable_json(OUT/'development_prediction_seal.json',{'rows':[r for r in predictions if r['role']=='development']+dev_prompt})
    # Open development annotation only after all development predictions are sealed.
    grading_path=ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json'
    def grade(rows,eligible):
        annotations=read(grading_path);filtered={key:annotations[key] for key in eligible};del annotations
        results=[]
        for r in rows:
            c=next(c for c in cases if c['source']['key']==r['source'] and c['view_id']==r['view'])
            for task,v in r['decoded']['native'].items():
                metrics=grade_view('OpenExempt',c['native_views'][task],filtered[r['source']][task],v['answer']) if v['handled'] else {'grade':0.0,'unresolved_or_failed':True}
                results.append({k:r[k] for k in ('source','role','view','candidate','physical_call_id','cached_reanalysis')}|
                    {'task':task,'grade':metrics['grade'],'metrics':metrics,'handled':v['handled'],'answer':v['answer'],
                     'production_errors':r['decoded']['production_errors']})
        return results
    dev=grade([r for r in predictions if r['role']=='development']+dev_prompt,{c['source']['key'] for c in dev_cases})
    selection=choose(dev);immutable_json(OUT/'selection_before_calibration_grading.json',{'selection':selection,'development_scores':dev,'calibration_labels_used':False})
    cal_cases=[c for c in cases if c['role']=='calibration' and c['plan']['name']=='records']
    cal_prompt=[prompt_read(c) for c in cal_cases] if selection['ordinary_prompt']=='prompt_records' else []
    immutable_json(OUT/'all_prediction_seal.json',{'rows':predictions+dev_prompt+cal_prompt,'selection':selection})
    cal=grade([r for r in predictions if r['role']=='calibration']+cal_prompt,{c['source']['key'] for c in cal_cases})
    immutable_json(OUT/'native_scores.json',{'development':dev,'calibration_diagnostic':cal})
    result={}
    for arm,candidate in selection.items():
        rows=[r for r in cal if r['candidate']==candidate];assert len(rows)==4
        result[arm]={'candidate':candidate,'native_task_mean':sum(r['grade'] for r in rows)/4,'handled':sum(r['handled'] for r in rows),'per_source':{s:sum(r['grade'] for r in rows if r['source']==s)/2 for s in sorted({r['source'] for r in rows})}}
    with ledger.transaction() as db:
        actual=db.execute('select id,status,result from calls where id like ?',(run_id+':%',)).fetchall()
    totals={};
    for _,status,s in actual:
        assert status=='completed'
        for k,v in json.loads(s)['usage'].items():
            if type(v) in (int,float):totals[k]=totals.get(k,0)+v
    beneficial=result['M1']['native_task_mean']>max(result['fixed']['native_task_mean'],result['ordinary_prompt']['native_task_mean']) and selection['M1']=='local_records'
    summary={'selection':selection,'arms':result,'new_physical_calls':len(actual),'new_call_usage':totals,
        'old_responses_reanalyzed':18,'same_original_mothers_not_new_independent_trials':True,
        'actual_M1_transform_selected':selection['M1']=='local_records',
        'M1_specific_diagnostic_gain_over_both_controls':beneficial,
        'decision':'bounded_signal_requires_independent_confirmation_no_expansion_authorized' if beneficial else 'stop_current_M1_expansion',
        'independent_contribution_established':False,'full_Goal_complete':False,'M2_remains_stopped':True,
        'allocated_budgets_equal_actual_costs_reported_separately':True,
        'no_more_sources_variants_or_repeats_in_this_protocol':True}
    immutable_json(OUT/'terminal.json',summary);print(json.dumps(summary,ensure_ascii=False),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');a=p.parse_args()
    if a.prepare:
        protocol,cases=prepare();print(json.dumps({'prepared':str(OUT.relative_to(ROOT)), 'max_new_calls':6,'reference_probes':18,'offline_gate':read(OUT/'offline_gate.json')}))
    else: run()
