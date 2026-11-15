"""Learned source checks produce exclusions and fresh evidence-based readings.

The original and every subsequent observation are retained. A refutation is a
fallible neural judgment, not a host supplied fact or a replacement answer.
"""
from copy import deepcopy
import json

from .objects import digest
from .refutation_learning import instantiate,messages as check_messages,canonical_evidence
from .runtime import decoder_schema
from .semantic_execution import operation_groups,DEMAND
from .source_evidence_codec import schema,decode,messages as reading_messages
from .source_python import plan,finish,probe_program


def _check_one(client,prefix,source,bank,cases,operations,units,feedback=None):
    ops={o['name']:o for o in operations};probes=[];definitions=[];focus={};binding={}
    rows=[]
    for case in cases:
        for test in bank:
            item=instantiate(test,case,ops[case['operation']],units)
            if item is None:continue
            op,q=item;probes.append(q);definitions.append(op);focus[q['id']]=case['focus_unit_id']
            binding[q['id']]={'case':case['id'],'test':test['name'],'candidate_choice':case['candidate_choice'],
                'exclusion_on':test['exclusion_on']}
    if not probes:return {},None
    prompt=check_messages(definitions,probes,units,focus)
    if feedback:prompt[1]['content']=json.dumps({'current':json.loads(prompt[1]['content']),
        'same_TRAIN_source_feedback':feedback},ensure_ascii=False)
    wire,_=decoder_schema(schema(definitions,probes))
    r=client.generate(prefix+':'+digest(prompt),source=source,purpose='skill_replay',
        messages=prompt,thinking=False,schema=wire)
    if r['finish_reason']!='stop':raise ValueError('Incomplete source check; no implicit retry')
    content,adapted=canonical_evidence(r['content'])
    _,answers=decode(definitions,probes,units,content)
    rejected={}
    for a in answers:
        row={**binding[a['id']],'verdict':a['choice'],'answer':a,
             'exclude_candidate':a['choice']==binding[a['id']]['exclusion_on']}
        rows.append(row)
        if row['exclude_candidate']:rejected.setdefault(row['case'],[]).append(row)
    return rejected,{'kind':'source_check','result':r,'checks':rows,'queries':probes,
                     'deterministic_evidence_adaptation':adapted,
                     'fallible_neural_judgments_not_certificates':True}


def check(client,prefix,source,bank,cases,operations,units,feedback=None):
    rejected={};events=[]
    for test in bank:
        found,event=_check_one(client,prefix,source,[test],cases,operations,units,feedback)
        for key,rows in found.items():rejected.setdefault(key,[]).extend(rows)
        if event:events.append(event)
    return rejected,events


def execute(client,prefix,source,bundle,text,units,*,bank=(),feedback=None,direct_feedback=False,save_event=None):
    queries=plan(bundle['program'],bundle['operations'],text,units);by_id={q['id']:q for q in queries}
    probe=probe_program(bundle['program'],'_sr_get');answers={};events=[];rounds=[];history=[]
    excluded={};audit_done=set();original_queries={q['id']:deepcopy(q) for q in queries}
    def save(event):
        events.append(event)
        if save_event:save_event(event)
    while True:
        provisional=finish(probe,text,units,list(answers.values()))
        wanted=list(dict.fromkeys(x[len(DEMAND):] for x in provisional['unresolved'] if x.startswith(DEMAND)))
        if not set(wanted)<=set(by_id) or set(wanted)&set(answers):raise ValueError('Invalid acquired demand')
        if not wanted:break
        rounds.append(wanted)
        for batch in operation_groups([by_id[i] for i in wanted]):
            prompt=reading_messages(bundle['operations'],batch,units,scope='focus_last')
            if direct_feedback and any(q['operation']=='disposal_retention_clause_role' for q in batch):
                prompt[1]['content']=json.dumps({'current':json.loads(prompt[1]['content']),
                    'same_TRAIN_source_feedback':feedback},ensure_ascii=False)
            wire,_=decoder_schema(schema(bundle['operations'],batch))
            identity=prefix+':read:'+digest(prompt)
            r=client.generate(identity,source=source,purpose='skill_replay',messages=prompt,thinking=False,schema=wire)
            if r['finish_reason']!='stop':raise ValueError('Incomplete reading; no implicit retry')
            content,adapted=canonical_evidence(r['content'])
            _,read=decode(bundle['operations'],batch,units,content)
            for a in read:answers[a['id']]=a;history.append({'query':deepcopy(by_id[a['id']]),'answer':a,'kind':'initial'})
            save({'kind':'neural','call_id':identity,'result':r,'query_ids':[q['id'] for q in batch],
                  'deterministic_evidence_adaptation':adapted})
            pending=[a['id'] for a in read if a['choice']!='unknown' and a['operation']=='disposal_retention_clause_role']
            while pending and bank:
                cases=[]
                for qid in pending:
                    a=answers[qid];key=(qid,a['choice'],tuple(by_id[qid]['unit_ids']))
                    if key in audit_done:continue
                    audit_done.add(key)
                    cases.append({'id':qid,'operation':a['operation'],'candidate_choice':a['choice'],
                        'focus_unit_id':original_queries[qid]['unit_ids'][-1],'unit_ids':by_id[qid]['unit_ids']})
                if not cases:break
                rejected,check_events=check(client,prefix+':audit',source,bank,cases,bundle['operations'],units,
                    feedback if not direct_feedback else None)
                for event in check_events:save(event)
                pending=[]
                for qid,witnesses in rejected.items():
                    old=answers[qid];forbidden=excluded.setdefault(qid,set())
                    if old['choice'] in forbidden:raise ValueError('Repeated unchanged exclusion')
                    forbidden.add(old['choice'])
                    q=deepcopy(by_id[qid]);focus=original_queries[qid]['unit_ids'][-1]
                    context=set(q['unit_ids'])
                    for w in witnesses:context.update(x['unit_id'] for x in w['answer']['evidence'])
                    q['unit_ids']=sorted(context-{focus})+[focus];by_id[qid]=q
                    prompt=reading_messages(bundle['operations'],[q],units,scope='focus_last')
                    state={'excluded_current_source_choices':sorted(forbidden),
                        'actual_refutation_observations':witnesses,
                        'instruction':'Re-read the same operation with the newly obtained current-source evidence and exclusions. A negative constraint does not supply another positive meaning. Return unknown if remaining interpretations are unsupported.'}
                    prompt[1]['content']=json.dumps({'current':json.loads(prompt[1]['content']),'refutation_state':state},ensure_ascii=False)
                    raw=schema(bundle['operations'],[q]);choices=raw['properties']['answers']['properties'][qid]['anyOf'][0]['properties']['choice']['enum']
                    kept=[x for x in choices if x not in forbidden]
                    variants=raw['properties']['answers']['properties'][qid]['anyOf']
                    if kept:variants[0]['properties']['choice']['enum']=kept
                    else:variants.pop(0)
                    wire,_=decoder_schema(raw);identity=prefix+':reread:'+digest(prompt)
                    r=client.generate(identity,source=source,purpose='skill_replay',messages=prompt,thinking=False,schema=wire)
                    if r['finish_reason']!='stop':raise ValueError('Incomplete constrained reading; no implicit retry')
                    content,adapted=canonical_evidence(r['content'])
                    _,result=decode(bundle['operations'],[q],units,content);new=result[0]
                    if new['choice'] in forbidden:raise ValueError('Regenerated explicitly excluded choice')
                    answers[qid]=new;history.append({'query':q,'answer':new,'kind':'constrained_reread'})
                    save({'kind':'constrained_reread','call_id':identity,'result':r,'query':q,
                        'before':old,'after':new,'exclusions':sorted(forbidden),'witnesses':witnesses,
                        'deterministic_evidence_adaptation':adapted,
                        'no_positive_answer_inferred_from_exclusion':True})
                    if new['choice']!='unknown':pending.append(qid)
    raw=finish(bundle['program'],text,units,list(answers.values()))
    return {'source_output':raw,'semantic_answers':list(answers.values()),'events':events,
        'query_plan':queries,'effective_reading_queries':list(by_id.values()),'demand_rounds':rounds,
        'observation_history':history,'exclusions':{k:sorted(v) for k,v in excluded.items()},
        'source_semantics_certified':False,'planned_queries':len(queries),'answered_queries':len(answers),
        'old_source_program_supports_not_silently_replaced':True}
