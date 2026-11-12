"""One fixed source-neutral acquisition/update and independent free control."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.client import WireError
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.neural_span_compiler import read_records as read_old_records
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.relational_compiler import (
    SCHEMA, compile_skill, read_records, apply, text_policy)
from legal_skill_guard.skill_evolution.runtime import FrozenReads
from legal_skill_guard.skill_evolution.source_schema import TASKS
from legal_skill_guard.skill_evolution.span_compiler import execute
from legal_skill_guard.skill_evolution.teacher_transport import pack, unpack, INSTRUCTION
from experiments.legal_skill_evolution_role_TRAIN import physical_snapshot
from experiments.legal_skill_evolution_span_compiler import warm_base

RUN='legal_skill_evolution_relational_acquisition_20261113'
ARMS=('ScopedAcquisition','FreeAcquisition')
COMMON='''Update or reacquire one reusable external skill from the same original TRAIN information and shared previously acquired compiler. Both neural models remain frozen. Do not use source IDs, party/company names or per-source answer lookup as decision features. Native labels and evidence are TRAIN supervision, not source atoms to be copied at runtime. The actual previous responses are fallible examples, not gold source fields.
Choose relational_rule, program or text_policy as permitted by your arm. For relational_rule acquire up to four source-neutral frames. Each frame has a legal meaning and named finite semantic fields. Each field has a meaning, string or array type, and a finite domain of identifier-like legal concepts, never Entailment/Contradiction/NotMentioned or quoted source sentences. No legal fields, owners, rules or scopes are pre-supplied by the host. Learn the distinctions actually needed from the original text: for example actor-relative ownership, direct recipient versus someone inside a qualification, permission versus another legal action, and the scope of a linked provision where applicable. Do not create irrelevant fields just to fill the schema.
At runtime one frozen executor reads all frame instances from complete current public source spans in one request, without old source examples or downstream hypotheses. It returns each instance's supporting span IDs and each field's canonical value plus current support IDs contained within that instance. Values may be null; null means unresolved, not False, empty set or absence. Fields with unknown values are omitted from values and listed in unresolved_fields. A known empty array requires an explicit source basis. Several semantic fields may cite the same clause when supported; they are propositions about that clause, not disjoint string captures. Neither types nor citation existence proves the field's meaning.
The runtime record is {kind:FRAME_NAME, values:{known_field:canonical_value}, unresolved_fields:[names], support_ids:[ids], field_support_ids:{name:[ids]}, source_evidence:[actual_span_records], relation_semantics_verified:false}. Use the known semantic values for legal reasoning, not literal wording of source_evidence. An unknown field cannot be read through indexing, get/default, membership, stringification, pop or whole-map observation: accessing it raises and safely falls back. You can explicitly inspect unresolved_fields to skip an unusable record. Known fields may be used independently without observing unrelated unknowns. No match is not legal absence; do not return NotMentioned or Contradiction simply because a permission record is missing. A source-supported NotMentioned requires an actual recognized structure supporting its applicability, rather than a catch-all default.
For relational_rule/program emit exactly one complete Python def apply(inputs, premises). inputs has task_id and question only. relational_rule gets premises.records; program gets premises.source_text and can parse the entire current source directly. Return {handled:bool,answer:LABEL,used_records:[indices]}; LABEL is Entailment, Contradiction or NotMentioned. Relational handled=true requires actual used record indices. No source ID is supplied. Use only pure basic Python, loops/comprehensions and prebound re. No imports, nested functions, recursion, files, network or introspection. Allowed builtins min,max,sum,len,abs,round,sorted,all,any,int,float,bool,str,list,dict,set,tuple,range,enumerate,zip,isinstance,ValueError,KeyError,TypeError; common string, dict/list and re methods are available. For program use frames=[]; for both set policy_text=null. For text_policy set frames=[],procedure=null and provide a reusable policy_text; the frozen executor applies it jointly to both current hypotheses. This is a fully permitted strong control, not fallback.
source_examples contain only exact source quotes with provenance from the supplied TRAIN, used for acquisition validation and replay; they are never included in runtime relation extraction. Do not hide old source values in frame meanings or concept vocabularies. Both arms receive identical source text, native annotations, shared prior asset and real failed reads; both use the same code tools, source/unknown checks and unchanged native/history criterion. Do not knowingly weaken a control or claim an empirical advantage before executing. Keep the proposed artifact compact and complete.'''


def read(p):return json.loads(Path(p).read_text())


def prepare(root):
    folder=root/'artifacts'/RUN;folder.mkdir(exist_ok=True)
    if (folder/'protocol.json').exists():return folder,read(folder/'protocol.json')
    old=read(root/'artifacts/legal_skill_evolution_span_compiler_20261112/protocol.json')
    flat=read(root/'artifacts/legal_skill_evolution_schema_induction_20261112/protocol.json')
    public=read(root/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')
    bykey={s['key']:s for s in public}
    training=[*old['teacher_sources'],old['frozen_TRAIN_probes'][0]]
    previously_exposed=set(training+old['frozen_TRAIN_probes']+flat['frozen_TRAIN_probes'])
    nextkey=next(s['key'] for s in public if s['dataset']=='ContractNLI' and s['key'] not in previously_exposed)
    probes=[old['frozen_TRAIN_probes'][1],nextkey]
    paths=list((root/'legal_skill_guard/skill_evolution').glob('*.py'))
    paths += list((root/'tests').glob('test_skill_evolution*.py'))+[Path(__file__).resolve()]
    hashes={}
    for p in sorted(paths):
        rel=p.relative_to(root);q=folder/'source_snapshot'/rel;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(p.read_bytes())
        hashes[str(rel)]=hashlib.sha256(p.read_bytes()).hexdigest()
    profile=read(root/'configs/legal_skill_evolution_formal_v5_20261111.json')
    protocol={'run_id':RUN,'created_utc':datetime.now(timezone.utc).isoformat(),'same_goal':True,'goal_complete':False,
        'learning_object':'Acquired source-neutral relation meanings, finite participant/scope fields, binding contracts, source examples and executable consequence program.',
        'update_algorithm':'Use the shared prior skill and actual failed instance reads to request an independently acquired revision of relation definitions, scope vocabulary and procedure. Runtime emits source-supported local semantic records without old factual examples. Replay all eight fixed TRAIN parents, preserve each of the original four history grades, and require the original three-trigger strict native mean gain before admission. No prototype labels or fields are repaired by the host.',
        'teacher_sources':training,'history':old['history'],'trigger':old['trigger'],'frozen_TRAIN_probes':probes,
        'probe_selection':'de427 remains the uncalled prior neural diagnostic; the other is the first remaining original ContractNLI TRAIN parent in original public order after excluding prior acquisition/diagnostic cohorts. Neither enters the teacher input. Prior original TRAIN exposure is not relabeled as blind DEV.',
        'independent_acquisition_arms':list(ARMS),'execution_only_control':'NoExamplesSameP: delete old example payloads only, keep the old acquired frames, lexicons and program; no new teacher. It isolates the trivial prompt-cleanup explanation and is not an independent acquisition comparison.',
        'workload':'One independent teacher update per arm, then one source extraction/joint policy request per source per neural arm as needed; program arms execute without a model source read. Eight fixed calibration parents plus two fixed original TRAIN reuse parents. Signature-only control runs the same ten parents. No retry without a concrete fix, parameter search, new source pool or full study.',
        'executor_profile':profile['executor'],'teacher_profile':profile['teacher'],
        'automatic_retries':0,'source_snapshot':hashes,'ledger_before':physical_snapshot(root/'artifacts/rr_v2_preflight/research_ledger.sqlite3'),
        'no_new_full_training_DEV_TEST_or_paper':True,'old_failed_candidates_preserved':True}
    if any(x.get('reserved',0) for x in protocol['ledger_before'].values()):raise ValueError('Pending physical request')
    asset=read(root/'reports/legal_skill_evolution_run_20261111/span_compiler_evidence/shared_compiler_baseline_v1.json')
    immutable_json(folder/'shared_prior_asset.json',asset)
    grading=read(root/'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
    errors=[]; prior=root/'artifacts/legal_skill_evolution_neural_span_compiler_v2_20261113'
    for p in sorted((prior/'LocalBindings').glob('*.json')):
        row=read(p);errors.append({'source':row['source'],'actual_returned_bindings':row['source_event']['bindings'],
            'rejections':row['source_event']['rejected_bindings'],'actual_views':row['views']})
    task={'training':[{'source':k,'source_text':bykey[k]['views'][0]['public']['source_text'],
            'native_tasks':{v['id']:{'hypothesis':v['public']['question'],'native_annotation':grading[k][v['id']]}
                for v in bykey[k]['views'] if v['id'] in TASKS}} for k in training],
        'shared_prior_specification':asset['spec'],'actual_imperfect_prior_bindings':errors}
    packed=pack(task);assert unpack(packed)==task
    immutable_json(folder/'teacher_evidence.json',packed)
    immutable_json(folder/'protocol.json',protocol)
    with sqlite3.connect(root/'artifacts/rr_v2_preflight/research_ledger.sqlite3') as db:
        immutable_json(folder/'ledger_rows_before.json',db.execute('select * from calls order by id').fetchall())
    return folder,protocol


def setup(root):
    folder,protocol=prepare(root)
    ledger=EvolutionLedger(root/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,
        sources={'train':protocol['teacher_sources']+protocol['frozen_TRAIN_probes'],'dev':[],'test':[]},
        binding=digest(protocol),teacher_concurrency=2)
    return folder,protocol,ledger


def acquire(root):
    folder,protocol,ledger=setup(root);user=json.dumps(read(folder/'teacher_evidence.json'),ensure_ascii=False)
    def one(arm):
        p=folder/arm/'teacher.json'
        if p.exists():return read(p)
        instruction=('Acquire relational_rule. Learn compact local semantic relation frames with explicit participant ownership and action/qualification scope where needed, then the corresponding executable program. Correct acquisition objects, not merely old wording patterns. Preserve source-neutrality and source uncertainty.' if arm=='ScopedAcquisition' else
            'Independently choose the strongest economical reusable skill: relational_rule with the same tools, direct full-source program, or joint text_policy. You can acquire the same architecture if it is best. Aim for actual generalization and correct source scope, not a deliberately weak keyword baseline.')
        system=INSTRUCTION+'\n'+COMMON+'\n'+instruction
        call=RUN+':teacher:'+digest({'arm':arm,'system':system,'user':user,'schema':SCHEMA})
        result=FrozenTeacher(ledger,folder,protocol['teacher_profile']).propose(call,source_ids=protocol['teacher_sources'],
            system_prompt=system,user_prompt=user,output_schema=SCHEMA)
        immutable_json(p,result);return result
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs=[pool.submit(one,a) for a in ARMS]
        errors=[]
        for job in jobs:
            try:job.result()
            except Exception as e:errors.append(type(e).__name__+': '+str(e))
    immutable_json(folder/'teacher_settlement.json',{'ledger':physical_snapshot(ledger.path),'errors':errors})
    if errors:raise ValueError('Teacher settlement retained: '+str(errors))


def evaluate(root):
    folder,protocol,ledger=setup(root)
    if (folder/'completed.json').exists():return read(folder/'completed.json')
    if any(x.get('reserved',0) for x in physical_snapshot(ledger.path).values()):raise ValueError('Wait for actual pending requests')
    public={s['key']:s for s in read(root/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
    grading=read(root/'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
    materials={k:public[k]['views'][0]['public']['source_text'] for k in protocol['teacher_sources']}
    compiled,invalid={},{}
    for arm in ARMS:
        try:compiled[arm]=compile_skill(read(folder/arm/'teacher.json')['value'],materials,restricted=arm=='ScopedAcquisition')
        except Exception as e:invalid[arm]=type(e).__name__+': '+str(e)
    immutable_json(folder/'compile_receipt.json',{'valid':list(compiled),'invalid':invalid})
    executor=FrozenExecutor(ledger,folder,protocol['executor_profile']);executor.readiness();reads=FrozenReads(executor)
    old=read(root/'artifacts/legal_skill_evolution_span_compiler_20261112/protocol.json');base=warm_base(root,old)
    prior=read(folder/'shared_prior_asset.json');oldspec=prior['spec']
    from legal_skill_guard.skill_evolution.neural_span_compiler import frames_from_rules
    stripped=[{k:v for k,v in f.items() if k!='example'} for f in frames_from_rules(oldspec,prior['rules'])]
    results={};updates={}
    for arm in [*compiled,'NoExamplesSameP']:
        spec=compiled.get(arm);rows=[]
        for key in protocol['teacher_sources']+protocol['frozen_TRAIN_probes']:
            p=folder/arm/'results'/(key.replace(':','_')+'.json')
            if p.exists():rows.append(read(p));continue
            source=public[key];event=None;records=[];outputs={};failure=None
            try:
                if arm=='NoExamplesSameP':
                    records,event=read_old_records(reads,source,oldspec,stripped)
                    for record in records:
                        record['unresolved_fields']=[n for n,v in record['values'].items() if v is None]
                        record['values']={n:v for n,v in record['values'].items() if v is not None}
                elif spec['kind']=='relational_rule':records,event=read_records(reads,source,spec)
                elif spec['kind']=='text_policy':
                    raw,event=text_policy(reads,source,spec)
                    for task,value in raw.items():outputs[task]={'handled':value['answer'] is not None and bool(value['support_ids']),
                        'answer':value['answer'],'used_records':[],'support_ids':value['support_ids']}
            except WireError:raise
            except (ValueError,TypeError,KeyError) as e:failure=type(e).__name__+': '+str(e)
            inherited={v['view']:v for v in base[key]['views']};views=[]
            for view in source['views']:
                value=outputs.get(view['id']);error=failure
                if view['id'] in TASKS and error is None and not (spec and spec['kind']=='text_policy'):
                    try:
                        value=(execute(oldspec['procedure'],{'task_id':view['id'],'question':view['public']['question']},{'records':records})
                            if arm=='NoExamplesSameP' else apply(spec,source,view,records))
                    except (ValueError,TypeError,KeyError) as e:error=type(e).__name__+': '+str(e)
                core=value is not None and value['handled'] and error is None
                answer=value['answer'] if core else inherited[view['id']]['execution']['answer']
                score=grade_view(source['dataset'],view,grading[key][view['id']],answer) if core else inherited[view['id']]['score']
                views.append({'view':view['id'],'answer':answer,'score':score,'core_executed':core,'fallback':not core,
                    'execution':value,'error':error,'fallback_basis':None if core else 'Preserved actual common warm-library/NoSkill result; not new-core success'})
            result={'arm':arm,'source':key,'views':views,'records':records,'source_event':event,
                'native_grade':sum(v['score']['grade'] for v in views)/len(views),
                'core_views':sum(v['core_executed'] for v in views),'core_correct':sum(v['core_executed'] and v['score']['correct'] for v in views),
                'source_semantic_review_pending':True}
            immutable_json(p,result);rows.append(result)
            print(json.dumps({'arm':arm,'source':key,'core':result['core_views'],'correct':result['core_correct'],'grade':result['native_grade']}),flush=True)
        results[arm]=rows
        bykey={r['source']:r for r in rows};gain=sum(bykey[k]['native_grade']-base[k]['native_grade'] for k in protocol['trigger'])/len(protocol['trigger'])
        history=all(bykey[k]['native_grade']>=base[k]['native_grade'] for k in protocol['history'])
        updates[arm]={'strict_trigger_gain':gain,'history_nonregression':history,'numeric_admission':gain>0 and history,
            'semantic_admission_pending':True,'independent_acquisition':arm in ARMS}
    completed={'protocol_hash':digest(protocol),'results':results,'updates':updates,'invalid_proposals':invalid,
        'ledger_before':protocol['ledger_before'],'ledger_after':physical_snapshot(ledger.path),'goal_complete':False,
        'semantic_and_contribution_review_pending':True}
    immutable_json(folder/'completed.json',completed);return completed


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['prepare','acquire','evaluate']);args=p.parse_args()
    root=Path(__file__).resolve().parents[1]
    if args.stage=='prepare':print(prepare(root)[0])
    elif args.stage=='acquire':acquire(root)
    else:evaluate(root)
