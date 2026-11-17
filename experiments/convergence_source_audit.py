"""TRAIN-only independent clause audit under the current teacher binding.

No native labels, candidate interfaces or model predictions enter an audit.
This is source supervision shared by all arms, not method efficacy evidence.
The immutable request manifest and actual continuous ledger support recovery.
"""
import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import time

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.objects import digest

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/legal_skill_convergence_20261117'
TEACHER_PROFILE=ROOT/'configs/legal_skill_convergence_teacher_v1.json'
TEXT={'type':'string'}
TEXTS={'type':'array','items':TEXT}
SYSTEM=('Audit only the supplied TRAIN contract text. Do not browse, run commands, '
    'open files, or infer any benchmark label. This is an independent source audit '
    'for all comparison arms, not a proposal from either learned method. Identify '
    'operative effects and each exception\'s actual attachment. An effect_id names '
    'an obligation in this text, never a question\'s answer. Every quote must be an '
    'exact contiguous substring of the referenced document. Retain only '
    'source-supported scope alternatives, together as complete target sets; do not '
    'invent uncertainty. If the fragment or its definitions are insufficient, say '
    'so and list the missing references. A syntactic full section is not necessarily '
    'legally closed. Return the specified JSON only.')
SCHEMA=record_schema({
    'effects':{'type':'array','items':record_schema({'effect_id':TEXT,'document_id':TEXT,
        'kind':{'type':'string','enum':['ordinary_course','negative_interim','consent_requirement','knowledge_definition','other','unresolved']},
        'actor_quote':TEXT,'operative_quote':TEXT,'action_description':TEXT})},
    'exceptions':{'type':'array','items':record_schema({'exception_id':TEXT,'document_id':TEXT,
        'condition_quote':TEXT,'condition_kind':{'type':'string','enum':['pandemic','law_required','consent','other','unresolved']},
        'scope_options':{'type':'array','items':TEXTS},
        'scope_status':{'type':'string','enum':['explicit','genuine_source_ambiguity','unresolved_missing_context']},
        'attachment_quote':TEXT,'reason':TEXT})},
    'knowledge':record_schema({'standard':{'type':'string','enum':['actual','constructive','unresolved']},
        'document_id':TEXT,'evidence_quote':TEXT}),
    'scope_complete':{'type':'boolean'},'missing_references':TEXTS,
    'uncertainty_explanation':TEXT})


def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def pilot_selection(public,scope_receipts):
    """Freeze20 using public structure, never scores or native annotations."""
    by_dataset=defaultdict(list)
    expanded={r['source']:sum(bool(v.get('expanded')) for v in r['scope_receipts']) for r in scope_receipts}
    for s in public:by_dataset[s['dataset']].append(s)
    selected=[]
    for dataset,rows in sorted(by_dataset.items()):
        def structure(s):
            texts=[v['public'].get('source_text',v['public'].get('original_input','')) for v in s['views']]
            if dataset=='LegalBench_Diversity':return s['native_config']
            if dataset=='MAUD':return 'expanded'+str(expanded.get(s['key'],0))
            # Length quartiles plus predeclared native task inventory are public
            # input structure. No semantic reference answer enters selection.
            return str(sum(len(t) for t in texts)//12000)
        buckets=defaultdict(list)
        for s in rows:buckets[structure(s)].append(s)
        for values in buckets.values():values.sort(key=lambda s:digest({'seed':45,'source':s['key']}))
        chosen=[]
        while len(chosen)<4:
            for key in sorted(buckets,reverse=True):
                if buckets[key] and len(chosen)<4:chosen.append(buckets[key].pop(0))
        selected.extend(chosen)
    if len(selected)!=20:raise ValueError('Exactly4 per fixed library required')
    return [{'source':s['key'],'dataset':s['dataset'],'public_sha256':digest(s),
        'public_structure':structure_for_receipt(s,expanded)} for s in selected]


def structure_for_receipt(source,expanded):
    return {'native_tasks':[v['id'] for v in source['views']],
        'public_character_counts':[sum(len(str(v)) for v in t['public'].values()) for t in source['views']],
        'section_expanded_tasks':expanded.get(source['key'],0),'native_config':source.get('native_config')}


def public_documents(source):
    documents={};tasks={}
    for view in source['views']:
        body=view['public']['source_text'];key='document:'+hashlib.sha256(body.encode()).hexdigest()
        documents[key]=body;tasks[view['id']]=key
    return {'documents':documents,'native_task_contexts':tasks,
        'instruction':'Audit effects, conditions and attachment; no native labels are supplied.'}


def study_teacher_configuration():
    """Bind the study condition independently of the orchestrator's defaults."""
    frozen = read(TEACHER_PROFILE)
    profile = {key: frozen[key] for key in ('transport', 'model', 'reasoning_effort')}
    config = {key: frozen[key] for key in ('model', 'reasoning_effort', 'retries', 'timeout_seconds')}
    config['executable'] = '/home/yndx/.local/share/codex-npm/bin/codex'
    return profile, config


def prepare():
    summary=read(BASE/'handoff/normalized_inputs_current.json');data=ROOT/summary['artifact_root']
    public=read(data/'train/public.json');scope=read(data/'scope_receipts.json')
    pilot=pilot_selection(public,scope)
    profile,config=study_teacher_configuration()
    by_source={s['key']:s for s in public}
    # First shared audit is a public-structure-selected MAUD pilot source with
    # expanded context. Further audit work consumes the same locked pilot20.
    targets=sorted((r for r in pilot if r['dataset']=='MAUD'),key=lambda r:(
        -r['public_structure']['section_expanded_tasks'],digest({'source':r['source'],'seed':45})))
    requests=[{'source':r['source'],'source_public_sha256':digest(by_source[r['source']]),
        'system':SYSTEM,'user':json.dumps(public_documents(by_source[r['source']]),ensure_ascii=False,sort_keys=True),
        'schema':SCHEMA} for r in targets[:1]]
    source_paths=['experiments/convergence_source_audit.py','legal_skill_guard/skill_evolution/clients.py',
        'legal_skill_guard/skill_evolution/ledger.py','legal_skill_guard/inference/codex_cli_client.py',
        str(TEACHER_PROFILE.relative_to(ROOT))]
    binding={'name':'convergence_TRAIN_independent_source_audit_01','plan_commit':'37a76ffdf9490d7d213f5a9e67553a174416d84c',
        'normalized_inputs_root':summary['artifact_root'],'source_sha256':{p:sha(ROOT/p) for p in source_paths},
        'teacher_profile':profile,'teacher_config':config,'requests_sha256':digest(requests),
        'pilot20_sha256':digest(pilot),'native_labels_provided':False,
        'all_arms_allowed_same_audit_at_its_TRAIN_prefix':True,'reference_audit_not_method_improvement':True}
    out=BASE/'source_audit_01'/digest(binding)
    immutable_json(out/'binding.json',binding);immutable_json(out/'pilot20.json',pilot)
    immutable_json(out/'requests.json',requests)
    (BASE/'handoff/source_audit_current.json').write_text(json.dumps({'artifact_root':str(out.relative_to(ROOT)),
        'status':'prepared_not_started','requests':len(requests),'pilot20':20,'new_model_calls':0},indent=2)+'\n')
    print(json.dumps({'prepared':str(out.relative_to(ROOT)),'pilot20':20,'audit_requests':len(requests),
        'teacher_profile':profile,'no_generation_dispatched':True}),flush=True)


def validate(result,documents):
    issues=[];effects={}
    for row in result['effects']:
        if row['effect_id'] in effects:issues.append('duplicate effect identity')
        effects[row['effect_id']]=row
        text=documents.get(row['document_id'],'')
        if not row['operative_quote'] or row['operative_quote'] not in text:issues.append('ungrounded operative quote')
        if row['actor_quote'] and row['actor_quote'] not in text:issues.append('ungrounded actor quote')
    for row in result['exceptions']:
        text=documents.get(row['document_id'],'')
        for key in ('condition_quote','attachment_quote'):
            if not row[key] or row[key] not in text:issues.append('ungrounded '+key)
        options=row['scope_options']
        if not options:issues.append('empty admissible binding family')
        if any(any(target not in effects for target in option) for option in options):issues.append('dangling exception target')
        if row['scope_status']=='explicit' and len(options)!=1:issues.append('explicit scope has multiple bindings')
        if row['scope_status']=='genuine_source_ambiguity' and len(options)<2:issues.append('ambiguous scope lacks alternatives')
    k=result['knowledge'];text=documents.get(k['document_id'],'')
    if k['standard']!='unresolved' and (not k['evidence_quote'] or k['evidence_quote'] not in text):issues.append('ungrounded knowledge quote')
    return {'grounding_checks_passed':not issues,'issues':issues,
        'source_only_teacher_audit':True,'independent_human_verification':False,
        'source_semantics_or_method_effect_certified_by_quote_contiguity':False}


def run():
    pointer=read(BASE/'handoff/source_audit_current.json');out=ROOT/pointer['artifact_root']
    binding=read(out/'binding.json');requests=read(out/'requests.json')
    for path,expected in binding['source_sha256'].items():
        if sha(ROOT/path)!=expected:raise ValueError('Bound audit source changed: '+path)
    if digest(requests)!=binding['requests_sha256']:raise ValueError('Frozen audit requests changed')
    data=ROOT/binding['normalized_inputs_root']
    identities=read(data/'identity_metadata.json')
    sources={p:[r['source'] for r in identities if r['project_split']==p] for p in ('train','dev','test')}
    ledger=EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',
        run_id='convergence-source-audit-'+digest(binding)[:16],sources=sources,binding=binding)
    teacher=FrozenTeacher(ledger,out,binding['teacher_config'],authorized_profile=binding['teacher_profile'])
    ready=teacher.adapter.preflight();immutable_json(out/'teacher_preflight.json',ready)
    if not ready['ready']:raise ValueError('Configured teacher authentication is unavailable; no generation requested')
    status={'artifact_root':str(out.relative_to(ROOT)),'status':'running','pid':os.getpid(),
        'started_at':time.time(),'binding_sha256':digest(binding),'requests':len(requests)}
    (BASE/'handoff/source_audit_current.json').write_text(json.dumps(status,indent=2)+'\n')
    completed=[]
    try:
        for request in requests:
            call_id=ledger.run_id+':source-audit:'+digest(request)
            response=teacher.propose(call_id,source_ids=[request['source']],system_prompt=request['system'],
                user_prompt=request['user'],output_schema=request['schema'])
            value=response['value'];documents=json.loads(request['user'])['documents']
            receipt=validate(value,documents)
            row={'source':request['source'],'call_id':call_id,'source_public_sha256':request['source_public_sha256'],
                'audit':value,'grounding_receipt':receipt,'usage':response.get('usage'),
                'cache_hit':bool(response.get('ledger_cache_hit') or response.get('cache_hit'))}
            immutable_json(out/'audit_results'/(digest(request['source'])+'.json'),row)
            completed.append({'source':request['source'],'call_id':call_id,
                'grounding_checks_passed':receipt['grounding_checks_passed'],'issues':receipt['issues'],
                'effects':len(value['effects']),'exceptions':len(value['exceptions']),
                'scope_complete':value['scope_complete'],'missing_references':len(value['missing_references'])})
        immutable_json(out/'terminal.json',{'status':'completed','completed':completed,'not_model_effect_evidence':True})
        status.update({'status':'completed','completed':completed,'ended_at':time.time()})
    except Exception as error:
        status.update({'status':'failed','error':type(error).__name__+': '+str(error),'completed':completed,'ended_at':time.time()})
        (out/'terminal_failure.json').write_text(json.dumps(status,indent=2)+'\n');raise
    finally:(BASE/'handoff/source_audit_current.json').write_text(json.dumps(status,indent=2)+'\n')
    print(json.dumps(status,ensure_ascii=False),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','run']);a=p.parse_args()
    prepare() if a.action=='prepare' else run()
