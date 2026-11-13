"""One-call direct role/field extraction with the exact learned field meanings.

All acquired examples, full current source, candidate focuses and the same
deterministic finisher are shared. This is an execution control, not independent
acquisition. The model receives no native labels or corrected field values.
"""
from collections import OrderedDict
import json

from repair_foregoing_context import prepare
from experiments import legal_skill_evolution_semantic_operations as study
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.native import record_schema,grade_view,source_spans
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.runtime import decoder_schema
from legal_skill_guard.skill_evolution.scoped_grammar import constructors,term_sort,material_public
from legal_skill_guard.skill_evolution.scoped_reader import apply_current
from legal_skill_guard.skill_evolution.semantic_operations import ground_answers,finish,prepare_queries
from legal_skill_guard.skill_evolution.span_compiler import expand_unit_support

SYSTEM='''Jointly extract the acquired semantic fields for each CURRENT focus
clause. You receive the exact learned operation meanings/choices/TRAIN examples
and the complete current source. Each candidate's LAST unit is its focus; earlier
units and the rest of the document are reference context. Classify the effect
asserted by the focus, using context to resolve its actor and information scope.
Do not merge another clause's independent effect into this focus. Keep the fields
mutually consistent and distinguish disposal information from retained information.
An operative prohibition of retention has an actor and prohibited information
when the source states them; an unrelated clause has no such operative effect.
Unknown stays unknown, not a negative. For every non-unknown choice quote short,
exact CURRENT words supporting the judgment; do not copy old example facts.
Use only the supplied choice names. Return all and only the requested frames and
fields, pure JSON. Do not answer a downstream native hypothesis.'''


if __name__=='__main__':
    folder,p,ledger,source,units,b,previous,ignored=prepare()
    text=source['views'][0]['public']['source_text'];queries=prepare_queries(b['program'],b['operations'],text,units)
    groups=OrderedDict()
    for q in queries: groups.setdefault(tuple(q['unit_ids']),[]).append(q)
    ops={o['name']:o for o in b['operations']};properties={};candidates=[]
    for i,(window,qs) in enumerate(groups.items()):
        fields={}
        for q in qs:
            fields[q['operation']]=record_schema({'choice':{'type':'string','enum':[c['name'] for c in ops[q['operation']]['choices']]+['unknown']},
                'evidence':{'type':'array','items':record_schema({'unit_id':{'type':'integer','enum':[u['id'] for u in units]},'quote':{'type':'string','minLength':1}})}})
        properties['frame_'+str(i)]=record_schema(fields)
        candidates.append({'frame':'frame_'+str(i),'focus_unit_id':window[-1],'local_context_unit_ids':list(window)})
    schema=record_schema(properties);wire,_=decoder_schema(schema)
    content={'exact_acquired_operations_and_TRAIN_examples':b['operations'],
             'current_candidates':candidates,'complete_current_source_units':units}
    prompt=[{'role':'system','content':SYSTEM},{'role':'user','content':json.dumps(content,ensure_ascii=False)}]
    immutable_json(folder/'joint_field_control/pre_dispatch.json',{'system':SYSTEM,'content':content,'schema':schema,
        'same_learned_field_meanings_and_examples':True,'same_deterministic_finisher':True,
        'all_queries_represented_once':sum(len(qs) for qs in groups.values())==len(queries),
        'no_native_labels_or_corrected_field_values_supplied':True,'not_independent_acquisition':True})
    result=FrozenExecutor(ledger,folder,p['executor_profile']).generate(study.RUN+':joint_field_control:'+digest(prompt),
        source=source['key'],purpose='skill_replay',messages=prompt,thinking=False,schema=wire)
    immutable_json(folder/'joint_field_control/raw_result.json',result)
    if result['finish_reason']!='stop': raise ValueError('Incomplete joint control; no automatic retry')
    values=json.loads(result['content']);import jsonschema;jsonschema.validate(values,schema)
    raw_answers=[]
    for i,(window,qs) in enumerate(groups.items()):
        frame=values['frame_'+str(i)]
        for q in qs: raw_answers.append({'id':q['id'],**frame[q['operation']]})
    # Full source is available to this strong control. Preserve whatever actual
    # context it cites, rather than forcing it into the candidate's local window.
    allowed=[{**q,'unit_ids':[u['id'] for u in units]} for q in queries]
    answers=ground_answers(b['operations'],allowed,units,{'answers':raw_answers})
    raw=finish(b['program'],text,units,answers)
    spans=source_spans(material_public(source['views'][0]['public']));unit_supports={}
    from legal_skill_guard.skill_evolution.span_compiler import execution_source_units
    _,unit_supports=execution_source_units(text,spans)
    cs=constructors(b['spec']);nodes=[]
    for i,r in enumerate(raw['statements']): nodes.append({'id':i,'sort':term_sort(r['term'],cs),'term':r['term'],
        'support_ids':expand_unit_support(r['support_ids'],unit_supports),'child_ids':[],'ambiguous':False,'source_semantics_verified':False})
    interpretation={'nodes':nodes,'roots':list(range(len(nodes))),'source_program_output':raw,
                    'complete':raw['complete'],'unresolved':raw['unresolved']}
    grading=study.read(study.ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json');views=[]
    for v in source['views']:
        r=apply_current(b['spec'],{'rules':[],'disabled_rules':[],'acquired_pairs':[]},interpretation,v);core=r['value']['handled']
        proof=sorted({spans[s]['public_sentence_id'] for n in r['value']['used_nodes'] for s in nodes[n]['support_ids'] if 'public_sentence_id' in spans[s]})
        score=grade_view(source['dataset'],v,grading[source['key']][v['id']],r['value']['answer'],proof) if core else None
        views.append({'view':v['id'],'core_executed':core,'fallback':not core,'execution':r,'score':score,'proof_sentence_ids':proof})
    immutable_json(folder/'joint_field_control/result.json',{'source':source['key'],'semantic_answers':answers,
        'interpretation':interpretation,'views':views,'not_independent_acquisition':True,
        'source_semantic_review_pending':True,'goal_complete':False})
    print(json.dumps({'nodes':len(nodes),'core':sum(v['core_executed'] for v in views),
        'correct':sum(bool(v['score'] and v['score']['correct']) for v in views),'seconds':result['elapsed_seconds']}))
