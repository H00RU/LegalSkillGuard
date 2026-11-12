"""Probe unchanged acquired helpers on actual source units; no model or labels."""
import ast
import json
from pathlib import Path

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import source_spans
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.scoped_grammar import material_public
from legal_skill_guard.skill_evolution.source_effect_update import function_update
from legal_skill_guard.skill_evolution.span_compiler import execute_json,execution_source_units

ROOT=Path(__file__).resolve().parents[3]
RUN=ROOT/'artifacts/legal_skill_evolution_open_effect_acquisition_20261113'
read=lambda p:json.loads(p.read_text())


if __name__=='__main__':
    protocol=read(RUN/'protocol.json')
    public={s['key']:s for s in read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
    bundle=read(RUN/'SourceEffect/compiled.json');code=bundle['source_program']
    probe=function_update(code,["def apply(inputs,premises):\n    out=[]\n    parse_disposal(inputs['text'],inputs['ids'],out)\n    return {'statements':out,'trigger':disposal_trigger(inputs['text'].casefold())}"])
    findings=[]
    for key,span_id in [(protocol['reuse_sources'][0],75),(protocol['reuse_sources'][1],32),
                        (protocol['teacher_sources'][4],51)]:
        source=public[key];spans=source_spans(material_public(source['views'][0]['public']))
        units,mapping=execution_source_units(source['views'][0]['public']['source_text'],spans)
        unit=next(u for u in units if u['id']==span_id)
        actual=execute_json(probe,{'text':unit['text'],'ids':[unit['id']]},{},allow_helpers=True,trace=True)
        stage='reuse' if key in protocol['reuse_sources'] else 'development'
        saved=read(RUN/stage/'SourceEffect'/(key.replace(':','_')+'.json'))
        saved_rows=[n for n in saved['interpretation']['source_program_output']['statements']
                    if n['support_ids']==[span_id] and n['term'][0] in
                    ('disposal_obligation','retention_permission','retention_prohibition')]
        assert actual['result']['statements']==saved_rows
        findings.append({'source':key,'unit':unit,'original_support_ids':mapping[span_id],
            'original_source_spans':[spans[i] for i in mapping[span_id]],
            'probe_result':actual['result'],'exact_match_with_original_saved_effect_output':True,
            'trace':actual})
    ast_loads=[{'function':n.name,'premises_loaded':any(isinstance(x,ast.Name) and x.id=='premises' and isinstance(x.ctx,ast.Load) for x in ast.walk(n))}
               for n in ast.parse(code).body if isinstance(n,ast.FunctionDef) and any(a.arg=='premises' for a in n.args.args)]
    immutable_json(Path(__file__).with_name('actual_failure_localization.json'),{
        'new_physical_requests':0,'native_or_dev_test_labels_loaded':False,
        'original_compiled_program_unchanged':True,'original_program_digest':digest(code),
        'only_probe_entrypoint_changed_to_call_unchanged_acquired_helpers':True,
        'findings':findings,'actual_source_premises_use':ast_loads,
        'no_reuse_repair_or_new_score':True,'goal_complete':False})
    print(json.dumps([{'source':f['source'],'ids':f['original_support_ids'],'result':f['probe_result']} for f in findings]))
