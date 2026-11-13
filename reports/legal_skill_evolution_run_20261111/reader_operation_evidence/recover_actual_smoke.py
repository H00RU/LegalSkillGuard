"""Two concrete repairs on the already-executed TRAIN smoke, not a new pilot.

The finite retry changes mixed-operation batching into one operation per request.
It supplies no corrected labels or new source examples. The deterministic code
repair lowers an acquired, explicit absence of any qualification to no exception;
unknown still does not lower. Raw teacher code and all first responses remain.
"""
import argparse
from copy import deepcopy
import importlib.util
import json
from pathlib import Path

from experiments import legal_skill_evolution_semantic_operations as study
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.native import source_spans,grade_view
from legal_skill_guard.skill_evolution.scoped_grammar import material_public,constructors,term_sort
from legal_skill_guard.skill_evolution.scoped_reader import apply_current
from legal_skill_guard.skill_evolution.semantic_operations import finish,read_semantics
from legal_skill_guard.skill_evolution.source_effect_update import function_update
from legal_skill_guard.skill_evolution.span_compiler import execution_source_units,expand_unit_support,execute_json


def setup():
    folder,p,ledger,public=study.setup();key=p['teacher_sources'][0];source=public[key]
    pub=source['views'][0]['public'];spans=source_spans(material_public(pub));units,supports=execution_source_units(pub['source_text'],spans)
    bundle=study.read(folder/'LearnedOperations/compiled.json');name=key.replace(':','_')
    answers=study.read(folder/'smoke/LearnedOperations'/(name+'_semantic.json'))['answers']
    queries=study.read(folder/'smoke/LearnedOperations'/(name+'_plan.json'))['queries']
    return folder,p,ledger,source,spans,units,supports,bundle,answers,queries


def code_fix(folder,bundle,units,answers):
    fixed=deepcopy(bundle)
    before="if qual=='no_express_exception_or_retention':"
    after="if qual in ('no_express_exception_or_retention','no_disposal_retention_qualification'):"
    assert fixed['program'].count(before)==1
    fixed['program']=fixed['program'].replace(before,after)
    # Replay every declared qualification plus unknown through the actual
    # acquired helper. Only the explicit no-qualification label may change.
    op=next(o for o in bundle['operations'] if o['name']=='disposal_retention_qualification')
    wrapper="def apply(inputs,premises):\n    return _sr_exceptions(inputs['choice'],['receiving_party'],['confidential_information'])"
    evidence=[]
    for choice in [c['name'] for c in op['choices']]+['unknown']:
        original=execute_json(function_update(bundle['program'],[wrapper]),{'choice':choice},{},allow_helpers=True)
        corrected=execute_json(function_update(fixed['program'],[wrapper]),{'choice':choice},{},allow_helpers=True)
        if choice=='no_disposal_retention_qualification': assert original is None and corrected==['no_exceptions']
        else: assert original==corrected
        evidence.append({'choice':choice,'before':original,'after':corrected})
    immutable_json(folder/'lowering_repair/bundle.json',fixed)
    immutable_json(folder/'lowering_repair/offline_evidence.json',{
        'actual_failed_choice':'no_disposal_retention_qualification',
        'acquired_meaning':next(c['meaning'] for c in op['choices'] if c['name']=='no_disposal_retention_qualification'),
        'reason':'An explicitly asserted absence of qualifications entails absence of exceptions; this is not unknown or missing information. The existing caller reaches this helper only for an operative disposal effect.',
        'actual_helper_regression':evidence,'raw_teacher_and_first_answers_unchanged':True,
        'no_native_labels_or_new_semantic_judgments_used':True,'new_model_requests':0})
    return fixed


def run(retry):
    folder,p,ledger,source,spans,units,supports,bundle,answers,queries=setup()
    fixed=code_fix(folder,bundle,units,answers)
    if retry:
        selected=['sr_3_actor','sr_3_retention_info']
        client=FrozenExecutor(ledger,folder,p['executor_profile']);replacement={}
        for query in [q for q in queries if q['id'] in selected]:
            op=next(o for o in fixed['operations'] if o['name']==query['operation'])
            immutable_json(folder/'isolated_operation_repair'/(query['id']+'_input.json'),{
                'exact_original_query':query,'exact_original_operation_definition':op,
                'current_units_unchanged':[u for u in units if u['id'] in query['unit_ids']],
                'change':'One operation/query instead of the actual mixed12-row batch; no labels or examples added.',
                'selected_by':'Actual operative-retention frame lacked actor/information. Not selected by native answer labels.'})
            dst=folder/'isolated_operation_repair'/(query['id']+'_result.json')
            if dst.exists(): result=study.read(dst)
            else:
                a,e=read_semantics(client,study.RUN+':isolated_operation_repair:'+query['id'],source['key'],fixed['operations'],[query],units)
                result={'answers':a,'events':e};immutable_json(dst,result)
            replacement.update({a['id']:a for a in result['answers']})
        answers=[replacement.get(a['id'],a) for a in answers]
    raw=finish(fixed['program'],source['views'][0]['public']['source_text'],units,answers)
    schema=constructors(fixed['spec']);nodes=[]
    for i,r in enumerate(raw['statements']):
        nodes.append({'id':i,'sort':term_sort(r['term'],schema),'term':r['term'],
            'support_ids':expand_unit_support(r['support_ids'],supports),'child_ids':[],
            'ambiguous':False,'source_semantics_verified':False})
    interpretation={'nodes':nodes,'roots':list(range(len(nodes))),'source_program_output':raw,
        'complete':raw['complete'],'unresolved':raw['unresolved']}
    grading=study.read(study.ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json');views=[]
    for v in source['views']:
        r=apply_current(fixed['spec'],{'rules':[],'disabled_rules':[],'acquired_pairs':[]},interpretation,v);core=r['value']['handled']
        proof=sorted({spans[i]['public_sentence_id'] for n in r['value']['used_nodes'] for i in nodes[n]['support_ids'] if 'public_sentence_id' in spans[i]})
        score=grade_view(source['dataset'],v,grading[source['key']][v['id']],r['value']['answer'],proof) if core else None
        views.append({'view':v['id'],'core_executed':core,'fallback':not core,'execution':r,'score':score,'proof_sentence_ids':proof})
    stage='isolated_operation_repair' if retry else 'lowering_repair'
    immutable_json(folder/stage/'result.json',{'source':source['key'],'interpretation':interpretation,
        'semantic_answers':answers,'views':views,'source_semantic_review_pending':True,
        'same_original_TRAIN_smoke_not_new_transfer':True,'goal_complete':False})
    print(json.dumps({'stage':stage,'nodes':len(nodes),'core':sum(v['core_executed'] for v in views),
        'native_correct':sum(bool(v['score'] and v['score']['correct']) for v in views)}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--retry',action='store_true');args=parser.parse_args();run(args.retry)
