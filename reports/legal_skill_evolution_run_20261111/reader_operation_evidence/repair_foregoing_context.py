"""Restore textual antecedent context on the same actual TRAIN smoke.

The code only exposes a preceding source unit when the focus says 'foregoing'.
The model must still judge the information scope; the host supplies no referent,
legal value or label. Original interpretations and answers remain immutable.
"""
from copy import deepcopy
import json

from recover_actual_smoke import setup
from experiments import legal_skill_evolution_semantic_operations as study
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.semantic_operations import prepare_queries,finish,read_semantics


def prepare():
    folder,p,ledger,source,spans,units,supports,b,old_answers,old_queries=setup()
    fixed=study.read(folder/'lowering_repair/bundle.json')
    previous=study.read(folder/'isolated_operation_repair/result.json');answers=previous['semantic_answers']
    patched=deepcopy(fixed)
    before="    raw=_sr_text(spans[i])\n    if i>0 and _sr_heading(_sr_text(spans[i-1])):\n        ids.append(spans[i-1].get('id'))"
    after="    raw=_sr_text(spans[i])\n    if i>0 and (re.search(r'\\bforegoing\\b',raw,re.I) is not None or _sr_heading(_sr_text(spans[i-1]))):\n        ids.append(spans[i-1].get('id'))"
    assert patched['program'].count(before)==1
    patched['program']=patched['program'].replace(before,after)
    text=source['views'][0]['public']['source_text']
    queries=prepare_queries(patched['program'],patched['operations'],text,units)
    old=next(q for q in old_queries if q['id']=='sr_3_retention_info')
    new=next(q for q in queries if q['id']=='sr_3_retention_info')
    assert old['unit_ids']==[30] and new['unit_ids']==[29,30]
    a=finish(fixed['program'],text,units,answers)
    z=finish(patched['program'],text,units,answers)
    assert [r['term'] for r in a['statements']]==[r['term'] for r in z['statements']]
    immutable_json(folder/'foregoing_context_repair/bundle.json',patched)
    immutable_json(folder/'foregoing_context_repair/offline_evidence.json',{
        'actual_referring_words':next(u['text'] for u in units if u['id']==30),
        'preceding_source_context':next(u['text'] for u in units if u['id']==29),
        'old_query':old,'new_query':new,'all_semantic_terms_unchanged_by_context_patch':True,
        'no_antecedent_value_or_rule_invented':True,'model_scope_judgment_still_required':True,
        'raw_previous_responses_unchanged':True,'new_model_requests_for_offline_check':0})
    return folder,p,ledger,source,units,patched,answers,new


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--validate',action='store_true');args=parser.parse_args()
    folder,p,ledger,source,units,b,answers,query=prepare()
    if args.validate:
        value,events=read_semantics(FrozenExecutor(ledger,folder,p['executor_profile']),
            study.RUN+':foregoing_context_repair',source['key'],b['operations'],[query],units)
        replacement={a['id']:a for a in value};answers=[replacement.get(a['id'],a) for a in answers]
        raw=finish(b['program'],source['views'][0]['public']['source_text'],units,answers)
        immutable_json(folder/'foregoing_context_repair/result.json',{
            'semantic_answers':answers,'actual_query':query,'events':events,'source_output':raw,
            'full_source_semantics_not_certified_by_grounding':True,'goal_complete':False})
        print(json.dumps({'scope_choice':value[0]['choice'],'source_roots':len(raw['statements'])}))
    else: print(json.dumps({'offline_terms_preserved':True,'actual_new_query':query}))
