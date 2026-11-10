"""Fixed-key, source-unit evidence guidance after the recorded free-table failure."""
import argparse,hashlib,json,re
from pathlib import Path
from experiments.rr_v2_legal_evidence_contract import ROOT,BASE,FRAMES,initial,read
from experiments.rr_v2_legal_auto_interface_fact_search import metadata
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.legal_predicate_skills import validate_case,run
from legal_skill_guard.rr.method_client import MethodExecutor,MethodTeacher
from legal_skill_guard.rr.method_ledger import MethodLedger
from legal_skill_guard.rr.semantic_frames import obj

PREFIX='legal_evidence_contract_';SUFFIX='_v2_20261110';S={'type':'string'}


def source_units(policies):
    units=[]
    for p in policies:
        offset=0
        for text in p['rules'].split('\n\n'):
            if text.strip():units.append({'id':len(units),'section':p['section'],'start_character':offset,'end_character':offset+len(text),'text':text})
            offset+=len(text)+2
    return units


def schema(api,units):
    row=obj({'direct_assertion':S,'insufficient_without_inference':{'type':'array','items':S},
        'source_unit_ids':{'type':'array','items':{'type':'integer','enum':[u['id'] for u in units]}}})
    return obj({'contracts':obj({p['name']:row for p in api}),'unresolved':{'type':'array','items':S}})


def normalize(s):return ' '.join(re.findall(r'\w+',s.lower()))


def validate_guidance(value,api,units):
    if set(value['contracts'])!={p['name'] for p in api}:raise ValueError('Contract key coverage differs from actual API')
    index={u['id']:u for u in units};expanded=[]
    for name,r in value['contracts'].items():
        direct=normalize(r['direct_assertion'])
        if not direct:raise ValueError('Empty direct assertion criterion')
        if not r['source_unit_ids'] and name not in ['case_subject_year','different']:raise ValueError('Missing substantive governing source unit')
        if len(set(r['source_unit_ids']))!=len(r['source_unit_ids']):raise ValueError('Duplicate source unit')
        for bad in r['insufficient_without_inference']:
            b=normalize(bad)
            if len(b.split())>=8 and b in direct:raise ValueError('Same long assertion marked sufficient and insufficient')
        if any(i not in index for i in r['source_unit_ids']):raise ValueError('Unknown source unit')
        expanded.append({'predicate':name,**r,'source_quotes':[index[i] for i in r['source_unit_ids']]})
    return {'entries':expanded,'unresolved':value['unresolved'],'semantic_fidelity_proved':False}


def messages(action,source,api,units):
    if action=='teacher':
        system=('Acquire reusable linguistic criteria for reading EXPLICIT CASE PREMISES into the actual API. '
            'The statutes and API are your only scientific inputs. There are no cases, queries, labels, previous contracts or failed responses. '
            'For every predicate, describe what wording would DIRECTLY ASSERT that very status, with its ordered roles, polarity and temporal scope. '
            'This is distinct from listing sufficient legal conditions from which a rule engine could derive the status. '
            'For a predicate meaning that a named rule applies, direct evidence must assert applicability itself; merely satisfying its antecedents belongs in insufficient_without_inference even if the legal inference is valid. '
            'A rule-head status may still be explicitly stipulated; never globally ban it. Distinguish a whole qualification from a cited subcondition and explain safe citation aliases only when the statute supports them. '
            'A direct assertion of a terminal amount must actually state that amount for the correct subject/year. Entitlement alone is not an amount. '
            'Keep direct_assertion and insufficient_without_inference logically distinct. Do not invent paraphrases of source quotes: select source_unit_ids, whose original text is recovered deterministically. '
            'The common native adapter handles identity/calendar metadata; case_subject_year only names actual people/years. '
            'Keep unsupported aliases unresolved. Do not implement rules or solve a case. Return the exact fixed-key schema. No tools/browsing/commands.')
        material={'interface':api,'statute_units':units}
        return system,json.dumps(material,ensure_ascii=False)
    original=read(BASE/'legal_auto_interface_reader_v2_20261110/seal.json')['material']
    programme=read(BASE/'legal_auto_interface_audit_v1_20261110/frozen_library_and_cases.json')['warm_program']
    material={'interface':api,'cases':[{'ordinal':c['ordinal'],'facts':c['facts']} for c in original],
        'predicates_also_derived_by_rules':sorted({r['head']['predicate'] for r in programme['rules']})}
    system=('Perform only fact search into the supplied API using its actual ordered roles. No questions or answers are supplied. '
        'Return only explicit case premises with exact own-fact quotes. Do not materialize legal consequences as factual inputs, even if those consequences are true. '
        'A predicate also derived by a rule may nevertheless be a directly stipulated premise; do not globally ban rule-head predicates. '
        'A statement that a statutory condition is satisfied supplies that condition, not other consequences downstream of it. '
        'Missing facts remain omitted/unresolved, never false. Names/year roster and native calendar/identity metadata have their existing common task treatment. '
        'No invented predicates, dates, amounts, code, tools or final answers. Preserve case order81/86/72. ')
    if action=='guided':
        t=read(BASE/(PREFIX+'teacher'+SUFFIX)/'result.json')
        if t['status']!='source_guidance_captured_pending_semantic_review':raise ValueError('Teacher guidance structurally rejected')
        review=read(BASE/(PREFIX+'teacher'+SUFFIX)/'source_review.json')
        if not review['acceptable_for_bounded_reader_test']:raise ValueError('Source review did not authorize use of this artifact')
        material['source_learned_evidence_guidance']=t['expanded_guidance']
        system+='Use the source-learned criteria; do not invent missing distinctions.'
    else:
        old=read(BASE/'legal_evidence_contract_ordinary_v1_20261110/result.json')
        material['policies']=source['source_policies'];material['your_previous_candidate_frames']=old['value']
        system+=('Review your previous frames for confusing explicit status with derived consequences. '
            'Audit every substantive row against its own quote and source definitions. Remove unsupported inferences, keeping explicit premises and correctly cited conditions. '
            'Do not retain an assertion merely because it helps a query. Do not replace a whole status by a subcondition or infer a composite status from kinship alone. '
            'You may use direct role extraction, definition lookup or an internally constructed evidence contract; no candidate teacher guidance or expected frame is supplied.')
    return system,json.dumps(material,ensure_ascii=False)


def prepare(action):
    source,api=initial();units=source_units(source['source_policies']);name=PREFIX+action+SUFFIX;stage=BASE/name
    protocol=ROOT/'reports/method_redesign_20261109/legal_evidence_contract_v2_protocol.md'
    paths=['experiments/rr_v2_legal_evidence_contract_v2.py','experiments/rr_v2_legal_evidence_contract.py',
        'experiments/rr_v2_legal_auto_interface_fact_search.py','legal_skill_guard/rr/legal_predicate_skills.py',
        'legal_skill_guard/rr/method_client.py','legal_skill_guard/rr/method_ledger.py','legal_skill_guard/rr/client.py']
    files={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths};system,user=messages(action,source,api,units)
    seal={'run_id':name,'config':source['config'],'sources':source['sources'],'source_ids':source['source_ids'],
        'api':api,'source_policies':source['source_policies'],'units':units,'system':system,'user':user,
        'schema':schema(api,units) if action=='teacher' else FRAMES,'files':files,
        'binding':{'code_hash':digest(files),'config_hash':digest(source['config'])},
        'protocol_sha256':hashlib.sha256(protocol.read_bytes()).hexdigest(),'no_query_or_label_in_prompt':True,'goal_complete':False}
    immutable_json(stage/'seal.json',seal)
    for p,h in files.items():
        raw=(ROOT/p).read_bytes();assert hashlib.sha256(raw).hexdigest()==h;dest=stage/'frozen'/p
        dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists():assert dest.read_bytes()==raw
        else:dest.write_bytes(raw)
    return seal,stage


def main(action,generate):
    stage=BASE/(PREFIX+action+SUFFIX);out=stage/'result.json'
    if generate and out.exists():print(json.dumps({'existing':str(out),'no_redispatch':True}));return
    s,stage=prepare(action)
    if not generate:print(json.dumps({'prepared':action,'new_model_calls':0}));return
    l=MethodLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=s['run_id'],binding=s['binding'],sources=s['sources'],
        authorization_hash=s['protocol_sha256'],question='Repair actual evidence-guidance serialization/contradiction failures, then compare case-free learned guidance against strong ordinary source-backed self-review. No new cases or labels, no independent contribution presumed.')
    if action=='teacher':w=MethodTeacher(l,stage,s['config']['teacher']).summarize(s['run_id']+':source',source_ids=s['source_ids'],system_prompt=s['system'],user_prompt=s['user'],output_schema=s['schema'])
    else:
        e=MethodExecutor(l,stage,s['config']['executor']);e.readiness()
        w=e.generate(s['run_id']+':reader',source=s['source_ids'][0],purpose='method_primitive_observation',
            messages=[{'role':'system','content':s['system']},{'role':'user','content':s['user']}],thinking=False,schema=s['schema'])
    result={'physical_response':w,'new_oracle_views':0,'new_native_grades':0,'goal_complete':False}
    try:
        value=w['value'] if action=='teacher' else json.loads(w['content']);result['value']=value
        if action=='teacher':
            result['expanded_guidance']=validate_guidance(value,s['api'],s['units']);result['status']='source_guidance_captured_pending_semantic_review'
        else:
            old=read(BASE/'legal_auto_interface_reader_v2_20261110/execution_closed_before_grading.json')
            materials=read(BASE/'legal_auto_interface_reader_v2_20261110/seal.json')['material']
            p=read(BASE/'legal_auto_interface_audit_v1_20261110/frozen_library_and_cases.json')['warm_program']
            if [c['ordinal'] for c in value['cases']]!=[81,86,72]:raise ValueError('Case order differs')
            result['cases']=[]
            for c,o,m in zip(value['cases'],old['cases'],materials):
                row={'ordinal':c['ordinal'],'raw_case':c,'query_reused_unchanged':o['raw_case']['query']}
                try:
                    case={**c,'query':o['raw_case']['query']};validate_case(case,m['facts'],{p['name']:p for p in s['api']})
                    meta=metadata(case);execution=run(p,{**case,'facts':case['facts']+meta});a=execution['answer']
                    if c['ordinal']==86 and a!='Entailment':a=None
                    row.update(status='executed_pending_semantic_review',metadata=meta,execution=execution,native_prediction=a)
                except Exception as exc:row.update(status='rejected',error_type=type(exc).__name__,error=str(exc))
                result['cases'].append(row)
            result['status']='frames_captured_pending_semantic_review'
    except Exception as exc:result.update(status='rejected',error_type=type(exc).__name__,error=str(exc))
    immutable_json(out,result)
    print(json.dumps({'action':action,'status':result['status'],'elapsed_seconds':w['elapsed_seconds'],'error':result.get('error'),
        'cases':[{'ordinal':r['ordinal'],'status':r['status'],'prediction':r.get('native_prediction')} for r in result.get('cases',[])]},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['teacher','guided','review']);p.add_argument('--generate',action='store_true');a=p.parse_args();main(a.action,a.generate)
