"""Finite original-TRAIN test of acquiring previously unsupported legal effects.

This isolates updates from one common actual acquired compiler. It does not
claim independent end-to-end acquisition or establish a new contribution.
"""
import argparse
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import fcntl
import hashlib
import json
from pathlib import Path
import sqlite3

import jsonschema

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view,source_spans
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.runtime import decoder_schema
from legal_skill_guard.skill_evolution.scoped_grammar import material_public,parse
from legal_skill_guard.skill_evolution.scoped_reader import apply_current
from legal_skill_guard.skill_evolution.scoped_source_program import run_source
from legal_skill_guard.skill_evolution.source_effect_update import PROPOSAL,materialize
from legal_skill_guard.skill_evolution.source_schema import LABELS
from legal_skill_guard.skill_evolution.span_compiler import execute_json,execution_source_units,expand_unit_support,METHODS
from legal_skill_guard.skill_evolution.teacher_transport import INSTRUCTION,pack
from experiments.legal_skill_evolution_role_TRAIN import physical_snapshot
from experiments.legal_skill_evolution_span_compiler import warm_base
from experiments.legal_skill_evolution_scoped_acquisition import PROGRAM_RESULT

RUN='legal_skill_evolution_open_effect_acquisition_20261113'
ARMS=('SourceEffect','IndependentOpen')
read=lambda p:json.loads(Path(p).read_text())
WIRE,HOST=decoder_schema(PROPOSAL)
COMMON='''Learn a reusable external legal skill update. Both language models remain frozen. You receive the complete same original TRAIN contracts, native supervision for their four hypotheses, and a common actual prior compiler with its ontology, source program and consumer. This comparison isolates acquiring additional effects from a common actual library, not independent initial acquisition. No held-out reuse source is supplied. Do not use source/company IDs or an answer table; do not encode Entailment/Contradiction/NotMentioned in source facts. Literal native answers belong only in a decision program.
The old library handles disclosure questions nda-5/7 and does not implement nda-16 (return/destruction on termination) or nda-20 (retention after return/destruction). Correct fallback answers are not evidence that those effects were acquired. Learn the actual source-supported legal norms, including trigger, actor, relevant information/copies and exception scope. A return-on-request clause does not by itself establish a termination-triggered duty; a descriptive retention mention is not necessarily a legal exception. Read the actual sources and native annotations together. Do not invent rules to fit labels. Unknown stays unknown; unsupported means handled=false. Full source and all prior code are available to both arms, including cross-clause definitions and conditions.
You may choose architecture=compiler or program as permitted by the arm. For compiler, extend the old constructor list with new_constructors (name,meaning,sort,arguments); old meanings are preserved. source_functions and decision_functions each contain only the complete definitions you replace or add; include def apply(inputs,premises) if changing the entry point. Unchanged functions are inherited. Ordinary helpers are allowed. Constructors are open: do not shoehorn return/retention into a disclosure or label-valued node. Source input={source_text,source_spans:[id,field,start,end,text,...]}; adjacent physical fragments are joined at common punctuation boundaries and whitespace is folded. Unit IDs are source anchors, not necessarily dense. A source function returns {statements:[{term:closed JSON constructor term,support_ids:[current unit IDs]}],complete:bool,unresolved:[reasons]}. Every term is type-checked and each witness expanded to the original source spans. Consumer input={task_id,question}; premises={nodes:[{id,sort,term,support_ids,child_ids,ambiguous:false}],roots:[ids],...}. It receives no raw source. It returns {handled:bool,answer:Entailment|Contradiction|NotMentioned|null,used_nodes:[actual root IDs]}. A handled decision needs a relevant root proof. A missing node is not evidence of a legal absence. Source examples contain source,source_span_ids (ORIGINAL raw IDs below),occurrence (zero-based within cited range),quote (exact source words/case/punctuation, whitespace may vary),term_json (JSON term as a string). Supply representative real source interpretations of newly acquired effects, not hypothetical laws. Set direct_program=null.
For architecture=program, independently acquire a complete direct source program and set the four update/example arrays empty. direct_program defines apply(inputs,premises), with inputs={task_id,question}, premises={source_text,source_spans:current units}. Return {handled:bool,answer:Entailment|Contradiction|NotMentioned|null,used_span_ids:[actual current unit IDs]}. It may use any internal decomposition or local edit strategy and all raw source, history and tools. You may choose the same compiler architecture instead. Do not weaken the control.
Both architectures use the same pure Python engine: no imports, nested functions, decorators, recursion, globals, filesystem, network or introspection. Builtins min,max,sum,len,abs,round,sorted,all,any,int,float,bool,str,list,dict,set,tuple,range,enumerate,zip,isinstance,ValueError,KeyError,TypeError; prebound re and structural bind_scope are available. Allowed attributes are listed below. Preserve real source distinctions and earlier valid behavior; all acquisition/failure/repair costs are charged. Neither schema success, literal source cache nor fallback counts as a new learned mechanism. This is a finite first check, not full training or a claimed innovation.'''


def prepare(root):
    folder=root/'artifacts'/RUN
    if (folder/'protocol.json').exists():return folder,read(folder/'protocol.json')
    prior=read(root/'artifacts/legal_skill_evolution_scoped_acquisition_v5_20261113/protocol.json')
    old=read(root/'artifacts/legal_skill_evolution_source_program_acquisition_20261113/protocol.json')
    sources=read(root/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')
    keys=prior['initial_sources']+prior['update_sources']
    exposed=set(keys+prior['reuse_sources']+old['fixed_TRAIN_reuse_sources'])
    reuse=[s['key'] for s in sources if s['dataset']=='ContractNLI' and s['key'] not in exposed][:2]
    assert len(reuse)==2
    counts=physical_snapshot(root/'artifacts/rr_v2_preflight/research_ledger.sqlite3')
    if any(v.get('reserved',0) for v in counts.values()):raise ValueError('Reconcile live requests first')
    paths=[*sorted((root/'legal_skill_guard/skill_evolution').glob('*.py')),
           *sorted((root/'tests').glob('test_skill_evolution*.py')),Path(__file__).resolve(),
           root/'experiments/legal_skill_evolution_role_TRAIN.py',
           root/'experiments/legal_skill_evolution_span_compiler.py',
           root/'experiments/legal_skill_evolution_scoped_acquisition.py']
    protocol={'run_id':RUN,'same_goal':True,'goal_complete':False,'teacher_sources':keys,
        'reuse_sources':reuse,'excluded_mechanism_parents':sorted(exposed),
        'reuse_selection':'First2 remaining original TRAIN parents in preserved order, fixed before generation or grading; prior full-study exposure retained, not fresh blind data.',
        'history':prior['history'],'teacher_profile':prior['teacher_profile'],'executor_profile':prior['executor_profile'],
        'scope':'Finite new-effect acquisition/update feasibility with strong independent update control. Same8 sources and four original views; no full study. Two prior non-target labels now supplied equally. No new sources outside original128.',
        'question':'Can source-grounded open ontology/compiler updates acquire return/destruction and retention semantics and actually reuse them, compared with an unrestricted independent open update?',
        'not_a_novelty_or_completion_claim':True,'shared_initial_asset_not_independent_end_to_end':True,
        'workload':'One independent teacher update per arm, deterministic8 development and2 fixed TRAIN reuse, then a literal source-cache execution control. No executor source reads, seed sweep, adaptive reuse repair or full matrix.',
        'no_new_mechanical_call_cap':True,'automatic_retries':0,'ledger_before':counts,
        'source_snapshot':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}
    basepath=root/'artifacts/legal_skill_evolution_scoped_acquisition_v5_20261113/phase2/ScopedGrammar/adapted_proposal.json'
    protocol['base_sha256']=hashlib.sha256(basepath.read_bytes()).hexdigest()
    protocol['base_value_digest']=digest(read(basepath))
    data=[root/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json',
          root/'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json',
          root/'artifacts/legal_skill_evolution_fragment_program_update_20261112/completed.json',
          *[root/f'artifacts/legal_skill_evolution_20261111/formal_v5/NoSkill/initial_B{i}.json' for i in range(1,9)]]
    protocol['data_sha256']={str(f.relative_to(root)):hashlib.sha256(f.read_bytes()).hexdigest() for f in data}
    immutable_json(folder/'base.json',read(basepath));immutable_json(folder/'protocol.json',protocol)
    for path in protocol['source_snapshot']:
        dst=folder/'source_snapshot'/path;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes((root/path).read_bytes())
    with sqlite3.connect(root/'artifacts/rr_v2_preflight/research_ledger.sqlite3') as c:
        immutable_json(folder/'ledger_rows_before.json',{'rows':c.execute('select * from calls order by id').fetchall()})
    return folder,protocol


def setup(root):
    folder,p=prepare(root)
    for f,h in p['source_snapshot'].items():
        if hashlib.sha256((root/f).read_bytes()).hexdigest()!=h:raise ValueError('Bound source changed: '+f)
    for f,h in p['data_sha256'].items():
        if hashlib.sha256((root/f).read_bytes()).hexdigest()!=h:raise ValueError('Bound data changed: '+f)
    if digest(read(folder/'base.json'))!=p['base_value_digest']:raise ValueError('Initial acquired library changed')
    ledger=EvolutionLedger(root/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,
        sources={'train':p['teacher_sources']+p['reuse_sources'],'dev':[],'test':[]},binding=digest(p),teacher_concurrency=2)
    public={s['key']:s for s in read(root/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
    return folder,p,ledger,public


def acquire(root):
    folder,p,ledger,public=setup(root)
    grading=read(root/'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
    task={'common_actual_library':read(folder/'base.json'),
          'training':[{'source':k,'source_spans':source_spans(material_public(public[k]['views'][0]['public'])),
             'tasks':{v['id']:{'question':v['public']['question'],'native_annotation':grading[k][v['id']]}
                      for v in public[k]['views']}} for k in p['teacher_sources']],
          'shared_diagnosis':'The existing consumer does not handle nda-16/20. Existing native-correct disclosure paths do not demonstrate these effects. The public fragment/unit adapter repairs known physical split/whitespace defects; do not present that as learning. No peer update is supplied.'}
    user=json.dumps(pack(task),ensure_ascii=False)
    assert not any(k in user for k in p['reuse_sources'])
    def one(arm):
        dst=folder/arm/'teacher.json'
        if dst.exists():return
        instruction=('Use architecture=compiler. Acquire new source effects and reusable source recognition plus consumer updates, with real grounded examples. Source rules and query projection remain separate.' if arm=='SourceEffect' else 'Choose the strongest economical architecture independently. Complete direct code, open predicate invention/verification/reuse as in ADVENT, the same compiler tools, or local function updates are all permitted. You see identical evidence. Do not choose a weaker strategy merely to differ.')
        system=INSTRUCTION+'\n'+COMMON+'\n'+instruction+'\nAllowed attributes: '+','.join(sorted(METHODS))
        immutable_json(folder/arm/'teacher_input.json',{'system':system,'user':user,'logical_schema':PROPOSAL,'wire_schema':WIRE,'host_constraints':HOST})
        call=RUN+':teacher:'+digest({'arm':arm,'system':system,'user':user,'schema':WIRE})
        value=FrozenTeacher(ledger,folder,p['teacher_profile']).propose(call,source_ids=p['teacher_sources'],system_prompt=system,user_prompt=user,output_schema=WIRE)
        immutable_json(dst,value)
    errors=[]
    with ThreadPoolExecutor(max_workers=2) as pool:
        for job in [pool.submit(one,a) for a in ARMS]:
            try:job.result()
            except Exception as e:errors.append(type(e).__name__+': '+str(e))
    immutable_json(folder/'teachers_settled.json',{'errors':errors,'ledger':physical_snapshot(ledger.path)})
    if errors:raise ValueError(str(errors))


def compiled(folder,p,public,arm):
    proposal=read(folder/arm/'teacher.json')['value'];jsonschema.validate(proposal,PROPOSAL)
    if arm=='SourceEffect' and proposal['architecture']!='compiler':raise ValueError('Missing source compiler update')
    bundle,grammar=materialize(read(folder/'base.json'),proposal,{k:public[k]['views'][0]['public'] for k in p['teacher_sources']})
    immutable_json(folder/arm/'compiled.json',bundle)
    if grammar is not None:immutable_json(folder/arm/'induced_grammar.json',grammar)
    return bundle,grammar


def evaluate(root,reuse=False,cache=False):
    folder,p,ledger,public=setup(root)
    if any(v.get('reserved',0) for v in physical_snapshot(ledger.path).values()):raise ValueError('Wait for existing teachers')
    bundles={a:compiled(folder,p,public,a) for a in ARMS}
    if reuse:
        if not (folder/'development/completed.json').exists():raise ValueError('Complete development and freeze before reuse')
        immutable_json(folder/'reuse_freeze.json',{'bundle_hashes':{a:digest(b) for a,(b,g) in bundles.items()},'reuse_sources':p['reuse_sources'],'no_adaptive_repair':True})
    if cache:
        if not (folder/'reuse/completed.json').exists():raise ValueError('Freeze and finish real reuse before the shared-asset cache control')
        bundles={'SharedRuleCache':bundles['SourceEffect']}
    keys=p['reuse_sources'] if reuse else p['teacher_sources'];stage=('cache_' if cache else '')+('reuse' if reuse else 'development')
    grading=read(root/'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json');base=warm_base(root,p)
    for arm,(bundle,grammar) in bundles.items():
        rows=[]
        for key in keys:
            dst=folder/stage/arm/(key.replace(':','_')+'.json')
            if dst.exists():rows.append(read(dst));continue
            source=public[key];spans=source_spans(material_public(source['views'][0]['public']));units,supports=execution_source_units(source['views'][0]['public']['source_text'],spans)
            interpretation,error=None,None
            if grammar is not None:
                try:
                    if cache:
                        literal=deepcopy(grammar);literal['disabled_rules']=[r['id'] for r in literal['rules'] if r['induced']]
                        literal['scope_patterns']=[]
                        nodes=parse(literal,source['views'][0]['public']['source_text'])
                        nodes=[{**n,'support_ids':[s['id'] for s in spans if n['start']<s['end'] and s['start']<n['end']],
                                'child_ids':[]} for n in nodes if not n['ambiguous']]
                        nodes=[{**n,'id':i} for i,n in enumerate(nodes)]
                        interpretation={'nodes':nodes,'roots':[n['id'] for n in nodes],
                            'complete':False,'unresolved':['Literal matches do not establish global source coverage'],
                            'shared_acquired_rules_and_consumer':True,'not_independent_acquisition':True}
                    else:
                        interpretation,_=run_source(bundle['source_program'],bundle['grammar'],grammar,source)
                        if not interpretation['complete'] or interpretation['unresolved']:raise ValueError('Source remains unresolved')
                except Exception as e:error={'type':type(e).__name__,'message':str(e)}
            inherited={v['view']:v for v in base[key]['views']};views=[]
            for view in source['views']:
                result=None;failure=error;proof=[]
                if failure is None:
                    try:
                        if grammar is not None:
                            result=apply_current(bundle['grammar'],grammar,interpretation,view)
                            ids=sorted({s for n in result['value']['used_nodes'] for s in interpretation['nodes'][n]['support_ids']})
                        else:
                            raw=execute_json(bundle['program'],{'task_id':view['id'],'question':view['public']['question']},{'source_text':source['views'][0]['public']['source_text'],'source_spans':units},allow_helpers=True)
                            jsonschema.validate(raw,PROGRAM_RESULT);ids=expand_unit_support(raw['used_span_ids'],supports)
                            if raw['handled'] and (raw['answer'] is None or not ids):raise ValueError('Handled direct result needs source proof')
                            result={'value':{**raw,'used_span_ids':ids},'source_unit_output':raw}
                        proof=sorted({spans[i]['public_sentence_id'] for i in ids if 'public_sentence_id' in spans[i]})
                    except Exception as e:failure={'type':type(e).__name__,'message':str(e)}
                core=failure is None and result is not None and result['value']['handled']
                answer=result['value']['answer'] if core else inherited[view['id']]['execution']['answer']
                score=grade_view(source['dataset'],view,grading[key][view['id']],answer,proof) if core else inherited[view['id']]['score']
                views.append({'view':view['id'],'core_executed':core,'fallback':not core,'answer':answer,'score':score,'execution':result,'proof_sentence_ids':proof,'error':failure})
            row={'source':key,'arm':arm,'interpretation':interpretation,'views':views,'source_semantic_review_pending':True,'goal_complete':False}
            immutable_json(dst,row);rows.append(row)
            print(json.dumps({'stage':stage,'arm':arm,'source':key,'core':sum(v['core_executed'] for v in views),'correct':sum(v['core_executed'] and v['score']['correct'] for v in views),'source_error':error}),flush=True)
        immutable_json(folder/stage/arm/'completed.json',{'results':rows,'goal_complete':False})
    immutable_json(folder/stage/'completed.json',{'ledger':physical_snapshot(ledger.path),'review_pending':True,'goal_complete':False})


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['prepare','acquire','evaluate']);parser.add_argument('--reuse',action='store_true');parser.add_argument('--cache',action='store_true');args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    with (root/'artifacts/rr_v2_preflight/current_open_effect_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        if args.stage=='prepare':print(prepare(root)[0])
        elif args.stage=='acquire':acquire(root)
        else:evaluate(root,args.reuse,args.cache)
