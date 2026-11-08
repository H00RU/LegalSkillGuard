"""One original-TRAIN shared-law acquisition over the pinned teacher client.

The driver itself is hashed separately; existing frozen method files do not
change. No grader, source answers, DEV or TEST packet is opened here.
"""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.method_client import MethodTeacher,TEACHER_BINARY,TEACHER_SHA
from legal_skill_guard.rr.method_ledger import MethodLedger
from legal_skill_guard.rr.pal_frontend import pal_prompt,pal_schema,lower_pal,render_pal
from legal_skill_guard.rr.preflight import science_files,scientific_code_binding
from legal_skill_guard.rr.source_program import compile_source,source_theory
from legal_skill_guard.rr.compiler_templates import make_template


def main():
    run_id='reference_pal_teacher_openexempt1_v21_20261108'
    stage=ROOT/'artifacts/rr_method_runtime_20261107'/run_id
    cfg=json.loads((ROOT/'configs/rr_v2_preflight.json').read_text())
    manifest=json.loads((ROOT/cfg['source_manifest']).read_text())
    packet=ROOT/'data/packets/rr_v2/public_train.json'
    assert hashlib.sha256(packet.read_bytes()).hexdigest()==manifest['packet_sha256']['public_train']
    source=next(s for s in json.loads(packet.read_text())['sources'] if s['key']==manifest['formal_train_order'][0])
    assert source['dataset']=='OpenExempt'
    files=science_files(ROOT)
    offline=json.loads((ROOT/'reports/rr_method_runtime_20261107/offline_reference_frontend_v21_20261108.json').read_text())
    assert offline['files']==files and offline['exit_code']==0 and offline['network_blocked']
    assert hashlib.sha256(Path(TEACHER_BINARY).read_bytes()).hexdigest()==TEACHER_SHA
    controller=json.loads((ROOT/'artifacts/rr_method_runtime_20261107/method_runtime_reference_v5_20261108/controller.json').read_text())
    proc=Path('/proc')/str(controller['pid'])/'stat'
    if proc.exists():
        parts=proc.read_text().split(') ',1)[1].split()
        assert int(parts[19])==controller['start_ticks'] and parts[0] in {'T','t'},'Hold the existing controller at a settled boundary first'
    with sqlite3.connect('file:'+str((ROOT/cfg['ledger_path']).resolve())+'?mode=ro',uri=True) as db:
        assert not db.execute("select 1 from calls where status='reserved'").fetchone()
    messages=pal_prompt(source,None,full_template=True)
    messages[0]['content']+=(' The EC and EV public views repeat the same statutory text with separate factual regions. '
        'Provide their actual reusable statutory tests and guarded outputs, preserving ownership in both views. '
        'A declaration may cite multiple source units only when its actual definition translates each. '
        'Define query as an expression of guarded outputs, never as a direct native answer literal. '
        'Native citations are actual statutory identifiers from the supplied text, never sN source addresses. '
        'Use supplied typed collections and connectors when needed to preserve owner, period, unit, shared limits and allowance consumption. '
        'Do not copy one asset classification to a different asset or silently duplicate a shared allowance. '
        'Keep unavailable factual classifications as observations and missing legal semantics as explicit unresolved obligations.')
    sources={'train':manifest['formal_train_order'],'dev':[s['key'] for bank in manifest['split']['datasets'].values() for s in bank['dev']]}
    question='Can one source-faithful learned program for the identical public statutes replace repeated unguarded/truncated rewrites across the original32 OpenExempt TRAIN sources?'
    driver=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    config={'teacher':{**cfg['teacher'],'executable':TEACHER_BINARY},'driver_sha256':driver,'question':question}
    binding={'code_hash':scientific_code_binding(files),'config_hash':digest(config)}
    auth=json.loads((ROOT/'docs/rr_v2/method_runtime_authorization_20261107.json').read_text())
    immutable_json(stage/'seal.json',{'run_id':run_id,'source':source,'files':files,'config':config,
        'binding':binding,'driver_sha256':driver,'source_manifest_hash':digest(manifest),
        'messages':messages,'schema':pal_schema(),'no_labels_or_answers_used':True,'full_goal_complete':False})
    ledger=MethodLedger(ROOT/cfg['ledger_path'],run_id=run_id,binding=binding,sources=sources,
        authorization_hash=digest(auth),question=question)
    teacher=MethodTeacher(ledger,stage,config['teacher']);cid=run_id+':compile'
    paid=teacher.summarize(cid,source_ids=[source['key']],system_prompt=messages[0]['content'],
        user_prompt=messages[1]['content'],output_schema=pal_schema())
    with sqlite3.connect('file:'+str((ROOT/cfg['ledger_path']).resolve())+'?mode=ro',uri=True) as db:
        request_hash=db.execute('select request_hash from calls where id=?',(cid,)).fetchone()[0]
    result={'run_id':run_id,'source':source['key'],'teacher_usage':paid['invocation'].get('usage'),
        'elapsed_seconds':paid['elapsed_seconds'],'raw_program_preserved':True,'executor_core_success':False,
        'labels_read':False,'full_goal_complete':False,'driver_sha256':driver}
    try:
        program,adaptations=lower_pal(source,paid['value']['code']);compiled=compile_source(source,program)
        code=render_pal(program)
        assert lower_pal(source,code)[0]==program,'Canonical rendering must preserve the actual program'
        template=make_template(source,code,{'role':'teacher','call_id':cid,'request_hash':request_hash,
            'model':paid['model'],'canonical_code_is_semantics_preserving_rendering_of_actual_program':True})
        immutable_json(stage/'compiler_template.json',template)
        result.update(status='typed_teacher_material_saved',template_hash=template['template_hash'],
            untranslated_source_units=[r.source for r in source_theory(compiled).residuals if r.unknown_scope],
            deterministic_adaptations=adaptations)
    except Exception as exc:
        result.update(status='raw_teacher_program_rejected',error_type=type(exc).__name__,error=str(exc),
            diagnostics=getattr(exc,'diagnostics',None))
    assert science_files(ROOT)==files and hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==driver
    immutable_json(stage/'validation_result.json',result)
    immutable_json(ROOT/'reports/rr_method_runtime_20261107/reference_openexempt_teacher_v21_result.json',result)
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
