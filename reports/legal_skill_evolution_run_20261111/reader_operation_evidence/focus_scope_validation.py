"""Validate explicit focus/context separation on the actual failed scope read."""
import json

from repair_foregoing_context import prepare
from experiments import legal_skill_evolution_semantic_operations as study
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.runtime import decoder_schema
from legal_skill_guard.skill_evolution.semantic_operations import messages,RESPONSE,ground_answers,finish


if __name__=='__main__':
    folder,p,ledger,source,units,b,answers,q=prepare()
    prompt=messages(b['operations'],[q],units)
    original=json.loads(prompt[1]['content']);focused=json.loads(prompt[1]['content'])
    focused['current_queries'][0]['focus_unit_id']=q['unit_ids'][-1]
    assert focused['current_queries'][0]['focus_unit_id']==30
    restored=json.loads(json.dumps(focused));restored['current_queries'][0].pop('focus_unit_id');assert restored==original
    clarification='\nThe focus_unit_id identifies the clause to classify. Other supplied units are context for resolving its references, not additional effects to merge into that focus. Interpret only the retention scope asserted by the focus clause, using its actual context.'
    prompt[0]['content']+=clarification;prompt[1]['content']=json.dumps(focused,ensure_ascii=False)
    immutable_json(folder/'focus_scope_validation/offline_evidence.json',{
        'same_query_definition_examples_and_source_units':True,
        'metadata_only_change':'focus_unit_id=30, preceding29 is reference context',
        'remove_metadata_and_clarification_recovers_original_prompt':True,
        'no_semantic_choice_or_native_label_supplied':True,'prompt':prompt})
    wire,_=decoder_schema(RESPONSE)
    result=FrozenExecutor(ledger,folder,p['executor_profile']).generate(
        study.RUN+':focus_scope_validation:'+digest(prompt),source=source['key'],
        purpose='skill_replay',messages=prompt,thinking=False,schema=wire)
    assert result['finish_reason']=='stop'
    a=ground_answers(b['operations'],[q],units,json.loads(result['content']))
    replacement={v['id']:v for v in a};answers=[replacement.get(v['id'],v) for v in answers]
    raw=finish(b['program'],source['views'][0]['public']['source_text'],units,answers)
    immutable_json(folder/'focus_scope_validation/result.json',{'semantic_answers':answers,
        'actual_query':q,'result':result,'source_output':raw,'goal_complete':False})
    print(json.dumps({'choice':a[0]['choice'],'source_roots':len(raw['statements'])}))
