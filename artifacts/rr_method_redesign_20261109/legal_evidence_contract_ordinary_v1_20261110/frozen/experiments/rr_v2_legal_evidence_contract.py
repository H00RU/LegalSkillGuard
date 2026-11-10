"""Bounded source-only evidence-contract induction and ordinary source-search control.

This tests acquisition of the previously authored factual-boundary guidance. It
does not presume that an instruction table is an independent method contribution.
"""
import argparse,hashlib,json
from pathlib import Path
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.legal_predicate_skills import FACT,validate_case,run
from legal_skill_guard.rr.method_client import MethodExecutor
from legal_skill_guard.rr.method_ledger import MethodLedger
from legal_skill_guard.rr.semantic_frames import obj
from experiments.rr_v2_legal_auto_interface_fact_search import metadata

ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'artifacts/rr_method_redesign_20261109'
PREFIX='legal_evidence_contract_';DATE='_v1_20261110'
S={'type':'string'}
CONTRACT=obj({'entries':{'type':'array','items':obj({'predicate':S,'direct_evidence':S,
    'insufficient_evidence':{'type':'array','items':S},'source_quotes':{'type':'array','items':S}})},
    'unresolved':{'type':'array','items':S}})
FRAMES=obj({'cases':{'type':'array','items':obj({'ordinal':{'type':'integer'},
    'facts':{'type':'array','items':FACT},'unresolved':{'type':'array','items':S}})}})


def read(p):return json.loads(p.read_text())


def validate_contract(value,interface,policies):
    names={p['name'] for p in interface};rows=value['entries']
    if len(rows)!=len(names) or {r['predicate'] for r in rows}!=names:raise ValueError('Missing, duplicate or unknown contract predicate')
    for r in rows:
        if not r['direct_evidence'].strip():raise ValueError('Empty evidence description')
        if r['predicate']!='case_subject_year' and not r['source_quotes']:raise ValueError('No governing source quote')
        if any(not q or not any(q in p['rules'] for p in policies) for q in r['source_quotes']):raise ValueError('Contract quote absent from source')
    return {'source_quotes_checked':True,'source_semantic_correctness_not_proved':True,
        'no_predicate_globally_forbidden_because_it_is_a_rule_head':True}


def initial():
    source=read(BASE/'legal_auto_interface_cache_v1_20261110/seal.json')
    api=read(BASE/'legal_auto_interface_cache_v1_20261110/source.json')['value']['interface']
    return source,api


def make_messages(action,source,api):
    if action=='source':
        system=('Create reusable evidence-reading guidance from the supplied statutes and declared API only. '
            'There are no cases, questions, answers or hand-selected input-predicate names. For EVERY API predicate describe what an EXPLICIT case assertion would have to say to supply it directly, '
            'and which similar statements are insufficient without applying legal rules. A predicate may both be directly given in a case and be the head of a defeasible rule; do not globally ban it for that reason. '
            'Distinguish a stated legal status from merely meeting a referenced condition or subcondition. Resolve cited provisions using the actual statute; do not collapse a subcondition into a complete definition. '
            'Do not infer final amounts from entitlement wording or invent missing factual statuses. Keep the actual ordered roles and scope. '
            'The neutral case_subject_year roster supplies only explicitly named persons/annual years; structural identity/calendar metadata comes from the shared task adapter. '
            'Give exact governing statute quote substrings for every nonneutral predicate; use unresolved for ambiguity. '
            'This is evidence guidance, not a new law programme, case solution or rejection of explicitly given legal facts. Return only the schema object.')
        material={'policies':source['source_policies'],'interface':api}
        return [{'role':'system','content':system},{'role':'user','content':json.dumps(material,ensure_ascii=False)}]
    original=read(BASE/'legal_auto_interface_reader_v2_20261110/seal.json')
    common=('Perform ordinary fact search using the supplied API and its actual ordered roles. '
        'Read ONLY the fact texts for explicit assertions, not legal consequences. No questions or answers are supplied. '
        'Return each case in order. A legal status can be a direct premise if explicitly asserted; its being a rule head does not itself prohibit it. '
        'Do not infer composite status from one statutory subcondition or kinship alone. Missing evidence is omitted/unresolved, never false. '
        'Do not emit computed consequences in place of their factual premises. Each nonneutral quote must be a nonempty exact substring of that case fact text. '
        'Use case_subject_year to enumerate named people and explicit annual years. The common adapter supplies canonical-identity and annual-calendar metadata. '
        'No tools, code, outside knowledge, final answer or invented predicate. ')
    material={'interface':api,'cases':[{'ordinal':c['ordinal'],'facts':c['facts']} for c in original['material']]}
    if action=='guided':
        value=read(BASE/(PREFIX+'source'+DATE)/'result.json')
        if value['status']!='contract_captured_pending_semantic_review':raise ValueError('Source contract not structurally valid')
        material['source_learned_evidence_guidance']=value['value']
        system=common+'Use the source-learned guidance; it may be imperfect, so do not invent missing semantics from it.'
    else:
        material['policies']=source['source_policies']
        system=common+('Use the full source statute to look up the meaning of each cited provision and API definition. '
            'You may internally build your own evidence contract or use direct definition lookup. This ordinary source-search control is not restricted to a weaker literal-name match.')
    return [{'role':'system','content':system},{'role':'user','content':json.dumps(material,ensure_ascii=False)}]


def prepare(action):
    source,api=initial();name=PREFIX+action+DATE;stage=BASE/name
    protocol=ROOT/'reports/method_redesign_20261109/legal_evidence_contract_protocol.md'
    paths=['experiments/rr_v2_legal_evidence_contract.py','experiments/rr_v2_legal_auto_interface_fact_search.py',
        'legal_skill_guard/rr/legal_predicate_skills.py','legal_skill_guard/rr/method_client.py',
        'legal_skill_guard/rr/method_ledger.py','legal_skill_guard/rr/client.py']
    files={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
    seal={'run_id':name,'config':source['config'],'sources':source['sources'],'source_ids':source['source_ids'],
        'api':api,'source_policies':source['source_policies'],'messages':make_messages(action,source,api),
        'schema':CONTRACT if action=='source' else FRAMES,'files':files,
        'binding':{'code_hash':digest(files),'config_hash':digest(source['config'])},
        'protocol_sha256':hashlib.sha256(protocol.read_bytes()).hexdigest(),'thinking':False,
        'no_case_or_query_or_label_in_source_acquisition':action=='source',
        'no_handselected_legal_input_predicate_list_or_status_mapping':True,'goal_complete':False}
    immutable_json(stage/'seal.json',seal)
    for p,h in files.items():
        raw=(ROOT/p).read_bytes();assert hashlib.sha256(raw).hexdigest()==h
        dest=stage/'frozen'/p;dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists():assert dest.read_bytes()==raw
        else:dest.write_bytes(raw)
    return seal,stage


def main(action,generate):
    stage=BASE/(PREFIX+action+DATE);out=stage/'result.json'
    if generate and out.exists():print(json.dumps({'existing':str(out),'no_redispatch':True}));return
    s,stage=prepare(action)
    if not generate:print(json.dumps({'prepared':action,'new_model_calls':0}));return
    l=MethodLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=s['run_id'],binding=s['binding'],
        sources=s['sources'],authorization_hash=s['protocol_sha256'],
        question='Can case-free source-learned evidence guidance replace authored legal-status boundaries, and is any effect beyond strong ordinary source-backed fact search? Fixed original81/86/72, no labels, no new mechanism presumed.')
    e=MethodExecutor(l,stage,s['config']['executor']);e.readiness()
    w=e.generate(s['run_id']+':'+action,source=s['source_ids'][0],purpose='method_primitive_observation',messages=s['messages'],thinking=False,schema=s['schema'])
    result={'physical_response':w,'goal_complete':False,'new_oracle_views':0,'new_native_grades':0}
    try:
        value=json.loads(w['content']);result['value']=value
        if action=='source':
            result['structural_validation']=validate_contract(value,s['api'],s['source_policies'])
            result['status']='contract_captured_pending_semantic_review'
        else:
            old=read(BASE/'legal_auto_interface_reader_v2_20261110/execution_closed_before_grading.json')
            original=read(BASE/'legal_auto_interface_reader_v2_20261110/seal.json')['material']
            programme=read(BASE/'legal_auto_interface_audit_v1_20261110/frozen_library_and_cases.json')['warm_program']
            if [c['ordinal'] for c in value['cases']]!=[81,86,72]:raise ValueError('Case order changed')
            result['cases']=[]
            for c,o,m in zip(value['cases'],old['cases'],original):
                row={'ordinal':c['ordinal'],'raw_case':c,'query_reused_unchanged':o['raw_case']['query']}
                try:
                    case={**c,'query':o['raw_case']['query']};validate_case(case,m['facts'],{p['name']:p for p in s['api']})
                    meta=metadata(case);execution_case={**case,'facts':case['facts']+meta};execution=run(programme,execution_case)
                    answer=execution['answer']
                    if c['ordinal']==86 and answer!='Entailment':answer=None
                    row.update(status='executed_pending_semantic_review',metadata=meta,execution=execution,native_prediction=answer)
                except Exception as exc:row.update(status='rejected',error_type=type(exc).__name__,error=str(exc))
                result['cases'].append(row)
            result['status']='frames_captured_pending_semantic_review'
    except Exception as exc:result.update(status='rejected',error_type=type(exc).__name__,error=str(exc))
    immutable_json(out,result)
    print(json.dumps({'action':action,'status':result['status'],'elapsed_seconds':w['elapsed_seconds'],
        'cases':[{'ordinal':r['ordinal'],'status':r['status'],'prediction':r.get('native_prediction'),'error':r.get('error')} for r in result.get('cases',[])],
        'error':result.get('error'),'goal_complete':False},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['source','guided','ordinary']);p.add_argument('--generate',action='store_true')
    a=p.parse_args();main(a.action,a.generate)
