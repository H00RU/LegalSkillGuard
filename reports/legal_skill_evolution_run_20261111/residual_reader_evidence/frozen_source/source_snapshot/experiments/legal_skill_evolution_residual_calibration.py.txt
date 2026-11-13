"""Current-reader TRAIN calibration for a bounded independent-update comparison.

No closed reuse parent is re-executed. Validation parents are fixed from the
original TRAIN manifest by identity only and excluded from acquisition input.
"""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path

import jsonschema

from experiments.legal_skill_evolution_focused_reader import material
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import source_spans,grade_view
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.residual_reader import execute
from legal_skill_guard.skill_evolution.scoped_grammar import constructors,material_public,term_sort
from legal_skill_guard.skill_evolution.scoped_reader import apply_current
from legal_skill_guard.skill_evolution.scoped_source_program import OUTPUT
from legal_skill_guard.skill_evolution.span_compiler import execution_source_units,expand_unit_support

ROOT=Path(__file__).resolve().parents[1]
RUN='legal_skill_evolution_residual_reader_20261113'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()


def prepare():
    parent,p,previous,public,b=material();out=ROOT/'artifacts'/RUN
    path=out/'protocol.json'
    if path.exists():
        protocol=read(path)
    else:
        with previous.transaction() as db:
            rows=[list(r) for r in db.execute('select * from calls order by id')]
        assert not any(r[6]=='reserved' for r in rows)
        exposure=read(ROOT/'artifacts/legal_skill_evolution_open_effect_acquisition_20261113/protocol.json')
        excluded=set(exposure['teacher_sources']+exposure['reuse_sources']+p['teacher_sources']+p['reuse_sources'])
        # Selection depends only on the pre-existing native TRAIN order/IDs.
        ordered=read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')
        validation=[s['key'] for s in ordered if s['dataset']=='ContractNLI' and s['key'] not in excluded][:2]
        assert len(validation)==2
        paths=[Path(__file__).resolve(),ROOT/'legal_skill_guard/skill_evolution/residual_reader.py',
               ROOT/'tests/test_skill_evolution_residual_reader.py']
        protocol={'same_goal':True,'goal_complete':False,'run_id':RUN,'train_sources':p['teacher_sources'],
            'validation_sources':validation,'validation_selection':'First2 original native TRAIN identities outside common8-source acquisition and prior closed reuse. Historical full-study exposure retained; not a new blind TEST.',
            'closed_reuse_not_repeated':p['reuse_sources']+exposure['reuse_sources'],
            'inherited_initial_acquisition_exposure':exposure['teacher_sources'],
            'executor_profile':p['executor_profile'],'teacher_profile':p['teacher_profile'],
            'seed_bundle_sha256':digest(b['LearnedOperations']),
            'current_known_train_result':str((parent/'focused_execution_v2/smoke/LearnedOperations'/(p['teacher_sources'][0].replace(':','_')+'.json')).relative_to(ROOT)),
            'calibration_sources':p['teacher_sources'][1:],'source_sha256':{str(q.relative_to(ROOT)):sha(q) for q in paths},
            'public_manifest_sha256':sha(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'),
            'workload':'Current-reader calibration on the original3 acquisition parents not yet executed by that frozen reader; reuse the already settled fourth TRAIN result. Then review actual active source contradictions. Only if unresolved current cases exist, compare one constrained residual-program update with an unrestricted reflective reader update from the same seed and supervision. Both can use residuals; the unrestricted arm can also change G/operations or use pure code. Freeze before the fixed2 original-TRAIN validation. No additional sources/seeds/round search.',
            'learning_object':'Reusable conditional residual source-interpretation program; repairs must have current-source witnesses and change consumed semantics. Not automatically a contribution.',
            'feedback':'Acquired examples are positive-only, not exhaustive labels. Explicit source-negative judgments, legal-equivalence uncertainty and observed consumption remain separate. Old already-fixed354 errors are not new update targets.',
            'controls':'Same-info unrestricted reflection, unchanged seed, exact original-source error/repair cache. Shared initial acquisition is not independent end-to-end acquisition.',
            'no_new_mechanical_call_cap':True,'no_full_training_DEV_TEST_or_paper':True}
        immutable_json(path,protocol);immutable_json(out/'ledger_before.json',{'rows':rows})
        immutable_json(out/'seed.json',b['LearnedOperations'])
        for q in paths:
            dst=out/'source_snapshot'/q.relative_to(ROOT);dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(q.read_bytes())
    for name,h in protocol['source_sha256'].items():
        assert sha(ROOT/name)==h,'Current calibration source changed after freeze'
    assert digest(b['LearnedOperations'])==protocol['seed_bundle_sha256']
    ledger=EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,
        sources={'train':protocol['train_sources']+protocol['validation_sources'],'dev':[],'test':[]},binding=digest(protocol))
    return out,protocol,ledger,public,b['LearnedOperations'],parent


def source_record(bundle,source,result):
    pub=source['views'][0]['public'];spans=source_spans(material_public(pub))
    units,supports=execution_source_units(pub['source_text'],spans)
    raw=result['source_output'];jsonschema.validate(raw,OUTPUT);schema=constructors(bundle['spec'])
    nodes=[{'id':i,'sort':term_sort(r['term'],schema),'term':r['term'],
        'support_ids':expand_unit_support(r['support_ids'],supports),'child_ids':[],
        'ambiguous':False,'source_semantics_verified':False} for i,r in enumerate(raw['statements'])]
    interpretation={'nodes':nodes,'roots':list(range(len(nodes))),'complete':raw['complete'],
        'unresolved':raw['unresolved'],'source_program_output':raw}
    grading=read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
    views=[]
    for view in source['views']:
        r=apply_current(bundle['spec'],{'rules':[],'disabled_rules':[],'acquired_pairs':[]},interpretation,view)
        core=r['value']['handled'];proof=sorted({spans[s]['public_sentence_id'] for n in r['value']['used_nodes']
            for s in nodes[n]['support_ids'] if 'public_sentence_id' in spans[s]})
        score=grade_view(source['dataset'],view,grading[source['key']][view['id']],r['value']['answer'],proof) if core else None
        views.append({'view':view['id'],'core_executed':core,'fallback':not core,'execution':r,'score':score,
            'proof_sentence_ids':proof,'fallback_not_executed':not core})
    return {'source':source['key'],'runtime':result,'interpretation':interpretation,'views':views,
        'source_semantic_review_pending':True,'goal_complete':False}


def calibrate():
    out,p,ledger,public,bundle,parent=prepare()
    old=read(ROOT/p['current_known_train_result'])
    immutable_json(out/'calibration/previous_current_train_result.json',{'original_result':p['current_known_train_result'],
        'original_sha256':sha(ROOT/p['current_known_train_result']),'source':old['source'],
        'new_physical_requests':0,'already_fixed_case_not_new_negative':True})
    client=FrozenExecutor(ledger,out,p['executor_profile']);client.exact_replay_roots=(out,parent)
    client.readiness()
    for key in p['calibration_sources']:
        dst=out/'calibration'/(key.replace(':','_')+'.json')
        if dst.exists():continue
        source=public[key];pub=source['views'][0]['public'];spans=source_spans(material_public(pub))
        units,_=execution_source_units(pub['source_text'],spans)
        def save(event):immutable_json(out/'calibration/events'/(digest(event['call_id'])+'.json'),event)
        result=execute(client,RUN+':calibration:'+key,key,bundle,pub['source_text'],units,
            scope='focus_last',lookup='_sr_get',save_event=save)
        row=source_record(bundle,source,result);immutable_json(dst,row)
        print(json.dumps({'source':key,'planned':result['planned_queries'],'read':result['answered_queries'],
            'core':sum(v['core_executed'] for v in row['views']),
            'correct':sum(bool(v['score'] and v['score']['correct']) for v in row['views']),
            'new_physical':sum(not e['result'].get('cache_hit',False) for e in result['events'] if e['kind']=='neural')}),flush=True)
    immutable_json(out/'calibration/completed.json',{'sources':p['calibration_sources'],
        'previous_result_reused':old['source'],'current_error_review_pending':True,'goal_complete':False})


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['prepare','calibrate']);args=parser.parse_args()
    with (ROOT/'artifacts/rr_v2_preflight/current_residual_reader_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        if args.stage=='prepare':print(prepare()[0])
        else:calibrate()
