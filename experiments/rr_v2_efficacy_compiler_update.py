"""Verified compiler-library evolution using fixed, earlier TRAIN material."""
import argparse
import base64
from datetime import datetime,timezone
import json
from pathlib import Path
import sqlite3
from legal_skill_guard.rr.atom_frontend import atom_prompt,atom_schema,decode_atom_response
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.learning import SkillLibrary
from legal_skill_guard.rr.method_run import MethodRun
from legal_skill_guard.rr.method_client import MethodExecutor
from legal_skill_guard.rr.method_ledger import MethodLedger
from legal_skill_guard.rr.model_horn import assess_model_horn
from legal_skill_guard.rr.preflight import science_files

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT/'artifacts/rr_method_runtime_20261107/method_runtime_reference_v10_20261109'
RUN='efficacy_compiler_updates_v1_20261109'
STAGE=ROOT/'artifacts/rr_method_efficacy_20261109'/RUN


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','run']);args=parser.parse_args()
    old=json.loads((OLD/'seal.json').read_text());public={s['key']:s for split in ('train','dev')
        for s in json.loads((ROOT/f'data/packets/rr_v2/public_{split}.json').read_text())['sources']}
    # Invoke the repaired production admission path, without starting MethodRun
    # or importing its previous results as a newly trained trajectory.
    learner=object.__new__(MethodRun);learner.root=ROOT;learner.seal=old;learner.config=old['config']
    library=SkillLibrary(stage='formal_train');admitted=[];libraries={}
    for ordinal,key in enumerate(old['sources']['train'],1):
        record=json.loads((OLD/'build/sources'/(digest(key)+'.json')).read_text())
        additions=learner.compiler_learning(public[key],record['prediction'])
        if record['learning'].get('learned_pattern'):library.add(record['learning']['learned_pattern'],source=key)
        for template in additions['templates']:
            assert template['source']['key']==key
            library.add_compiler_template(template)
            admitted.append({'ordinal':ordinal,'source':key,'template_hash':template['template_hash'],'origin':template['origin']})
        if ordinal in (16,128):
            name='B1' if ordinal==16 else 'B8'
            frozen=SkillLibrary(library.patterns,stage='formal_'+name,compiler_templates=library.compiler_templates)
            frozen.freeze(STAGE/(name+'.frozen.json'));libraries[name]=frozen.export()
    baseline=SkillLibrary.restore(OLD/'build/B8.frozen.json').export()
    target='ProofWriter_OWA_depth5:b5a9ae7450d09a26327b43ff2c4dd3146de4f816a797c2da4c11bfa67746dd7a'
    source=public[target];variants={}
    for name,lib in {'original4':baseline,**libraries}.items():
        messages=atom_prompt(source,lib,max_examples=1);schema=atom_schema(source)
        payload=json.loads(messages[1]['content'])
        variants[name]={'messages':messages,'schema':schema,'identity':digest([messages,schema]),
            'selected_examples':[x['template_hash'] for x in payload['compiler_training_examples']],
            'available_compiler_templates':len(lib['compiler_templates'])}
    files=science_files(ROOT)
    seal={'run_id':RUN,'files':files,'binding':{'code_hash':digest(files),'config_hash':digest(old['config'])},
        'fixed_TRAIN_material_run':OLD.name,'retrained_model_trajectory':False,'targets':[target],
        'config':old['config'],'variants':variants,'admission':admitted,
        'protocol_hash':digest((ROOT/'reports/method_efficacy_20261109/protocol.md').read_text()),
        'no_grade_used_in_admission_or_retrieval':True,'TEST_authorized':False,
        'shared_compilation_component_not_new_B_skill':True}
    immutable_json(STAGE/'seal.json',seal)
    print(json.dumps({'phase':args.action,'library_sizes':{k:v['available_compiler_templates'] for k,v in variants.items()},
        'selected':{k:v['selected_examples'] for k,v in variants.items()},'distinct_requests':len({v['identity'] for v in variants.values()})}),flush=True)
    if args.action=='prepare':return
    ledger=MethodLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,
        binding=seal['binding'],sources=old['sources'],authorization_hash=seal['protocol_hash'],
        question='Can newly admitted verified TRAIN compiler programs change subsequent DEV model translation? Fixed one-example retrieval, all groups share common components; not B graph learning.')
    executor=MethodExecutor(ledger,STAGE,old['config']['executor']);seen={}
    original=json.loads((OLD/'dev/journals/M11'/digest(target)/'request0.json').read_text())
    original_dispatch=json.loads(original['dispatch_json'])
    pred=json.loads((OLD/'dev/predictions/M11'/(digest(target)+'.json')).read_text())['prediction']
    for name,v in variants.items():
        path=STAGE/(name+'.json')
        if path.exists():
            result=json.loads(path.read_text());seen[v['identity']]=result['physical_response'];continue
        if v['messages']==original_dispatch['messages'] and v['schema']==original_dispatch['schema']:
            first=pred['calls'][0]
            with sqlite3.connect('file:'+str((ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3').resolve())+'?mode=ro',uri=True) as db:
                matches=db.execute("select id,result from calls where source=? and request_hash=? and status='completed'",(target,first['request_hash'])).fetchall()
            assert len(matches)==1
            origin,encoded=matches[0];wire=json.loads(encoded)
            assert wire['content']==first['raw_content']
            wire={**wire,'physical_origin_call_id':origin,'new_physical_call':False}
        elif v['identity'] in seen:
            wire={**seen[v['identity']],'new_physical_call':False}
        else:
            wire=executor.generate(RUN+':'+name+':0',source=target,purpose='method_transfer_diagnostic',
                messages=v['messages'],schema=v['schema'],thinking=False)
            wire={**wire,'new_physical_call':True}
        seen[v['identity']]=wire
        try:
            program,code=decode_atom_response(source,json.loads(wire['content']))
            assert not program.export()['missing_units']
            result=assess_model_horn(program,interface='ordinary_IO_local_binding_repair')
        except Exception as exc:result={'certificate_status':'rejected_model_translation','answer':None,'error_type':type(exc).__name__,'error':str(exc)}
        immutable_json(path,{'captured_utc':datetime.now(timezone.utc).isoformat(),'source':target,'variant':name,
            'result':result,'physical_response':wire,'selected_examples':v['selected_examples'],
            'no_native_label_or_DEV_program_in_library':True,'fallback_counted_as_core_success':False})
        print(json.dumps({'variant':name,'status':result['certificate_status'],'answer':result['answer'],
            'new_physical_call':wire['new_physical_call']}),flush=True)


if __name__=='__main__':main()
