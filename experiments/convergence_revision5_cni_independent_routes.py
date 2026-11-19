"""Compare bound exceptions for independent development and third-party receipt."""

import argparse
import base64
from collections import Counter
from functools import lru_cache
import hashlib
import inspect
import json
from pathlib import Path
import re
import sqlite3
from statistics import mean

import jsonschema

from experiments.convergence_formal_train_observe import load_roster, pointer
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision5_cni_disposition_scope import ARM, DATASET, TrainingJournal, spans_for
from experiments.convergence_revision5_cni_oral_scope import verify_prediction
from legal_skill_guard.paired_interfaces import residual
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view, record_schema
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE/'revision5_CNI_independent_routes_20261119'
POINTER = HANDOFF/'revision5_CNI_independent_routes_current.json'
DONE = 'completed_revision5_CNI_independent_routes_TRAIN'
TASKS = {'development':'nda-12','receipt':'nda-13'}
ROLES = ('fixed','synthesized')
YES, UNKNOWN = 'Entailment', 'NotMentioned'
# Major evidence paths noted from the full contracts. These are verification
# anchors for the diagnostic, and never enter either model request.
REVIEWS = {
    (2,1): ('prior_only_development_then_third_party_receipt',(26,28),(26,29,32),(False,True)),
    (2,2): ('one_disjunction_under_exception_header',(51,52),(51,52,56),(True,True)),
    (5,0): ('prior_knowledge_and_third_party_without_independent_development',(),(13,16),(False,True)),
    (6,1): ('nested_sibling_prior_possession_vs_any_time_development',(18,21,23,25),(18,21,26),(True,True)),
    (6,2): ('operative_exception_and_separate_future_right',(29,33,64,65,66),(29,32,64,65,66),(True,True)),
    (8,2): ('independent_development_subject_to_written_proof',(23,27),(23,26),(True,True)),
}
CUES = re.compile(
    r'\bindependent\w*|\bthird[- ]part(?:y|ies)\b|\bprior to (?:receipt|disclosure)\b'
    r'|\b(?:secrecy|confidentiality|non[- ]disclosure)\b.{0,80}\b(?:except|extend|apply|limit|include)\b',re.I)
COMMON = (
    'Read the complete NDA and the indexed original spans. Identify the two possible qualification routes '
    'for the receiving party. The first is development independent of the disclosed information. The second '
    'is lawful receipt from a separate source authorized to disclose it. Mark an operative route only when '
    'the exception to confidentiality or an express permission actually governs that same act and recipient. '
    'Keep the time qualifiers on their own clause. An exception confined to work completed before the original '
    'disclosure does not establish a path extending beyond that point. Past-tense wording or a requirement '
    'to prove independent development is insufficient by itself to impose a cutoff. Prior possession, '
    'public availability, onward disclosure by the recipient and disclosure by the original discloser are '
    'separate routes. Check for an applicable path anywhere in the document. If there is one, cite the '
    'operative act, its qualifying language and any governing lead-in from the indexed native spans. '
    'Use false for a verified contrary fact or verified absence after checking the full NDA, and null for '
    'unresolved scope or evidence. Preserve both routes and return the specified JSON structure.'
)
DOMAINS = (
    'dev_is_independent_work_by_receiver','dev_act_governed_by_exception','dev_not_confined_before_disclosure',
    'receipt_is_lawful_independent_receipt','receipt_act_governed_by_exception','receipt_not_confined_before_disclosure',
)


def consume(v, _):
    dev, receipt = None, None
    if v['dev_is_independent_work_by_receiver'] == True and v['dev_act_governed_by_exception'] == True:
        if v['dev_not_confined_before_disclosure'] is not None:
            dev = YES if v['dev_not_confined_before_disclosure'] else UNKNOWN
    if v['dev_is_independent_work_by_receiver'] == False or v['dev_act_governed_by_exception'] == False:
        dev = UNKNOWN
    if v['receipt_is_lawful_independent_receipt'] == True and v['receipt_act_governed_by_exception'] == True:
        if v['receipt_not_confined_before_disclosure'] is not None:
            receipt = YES if v['receipt_not_confined_before_disclosure'] else UNKNOWN
    if v['receipt_is_lawful_independent_receipt'] == False or v['receipt_act_governed_by_exception'] == False:
        receipt = UNKNOWN
    return {'development':dev,'receipt':receipt}


@lru_cache(maxsize=1)
def layouts():
    procedure = inspect.getsource(consume)
    meanings = dict(zip(DOMAINS, (
        'the cited development route is work by or for the receiver that is independent of the disclosed information',
        'an operative permission or confidentiality exception governs the exact cited development route',
        'the operative development route is available beyond development explicitly limited to before receipt',
        'the cited receipt route is lawful receipt by the receiver from a separate authorized third party',
        'an operative permission or confidentiality exception governs the exact cited receipt route',
        'the operative receipt route is available beyond receipt explicitly limited to before original disclosure',
    ), strict=True))
    module = residual.FiniteModule.build(
        'independent_development_and_external_receipt', {f:[True,False,None] for f in DOMAINS}, [{}], consume,
        consumer_sha256=digest(procedure),program_source=procedure,
        protected_status_fields=(DOMAINS[2],DOMAINS[5]),
        source_scope={'source_fields':['source_text'],'local_unit':'operative independent information source',
                      'field_meanings':meanings})
    fixed = [{'name':f,'operation':'field','field':f} for f in DOMAINS]
    links = residual.consumer_relations(module)
    merged = []
    for group,start in (('development',0),('receipt',3)):
        fields = set(DOMAINS[start:start+2])
        link, = (r for r in links if r['expression']['op']=='and' and set(r['consumer_dependencies'])==fields)
        merged.extend(({**link,'name':'operative_'+group+'_route'},fixed[start+2]))
    pair = (residual.compile_pair(module,fixed,operation='fixed_coordinates',layout='anchored'),
            residual.compile_pair(module,merged,operation='consumer_relational_projection',layout='anchored'))
    for state in module.states:
        for asset in pair:
            observed = residual.encode(asset['features'],state)
            output = residual.decode(asset,observed,{},module_binding=module.binding)
            assert output['valid'] and output['outputs']==consume(state,{})
    return module,pair


def materials():
    stage = ROOT/read(pointer(8))['artifact_root']
    training = read(stage/'binding.json')
    assert stage.name==digest(training) and not read(stage/'terminal.json')['TEST_opened']
    cp = ROOT/training['checkpoint_root']
    study = read(cp/'binding.json')
    roster = load_roster(study)
    journal = TrainingJournal(cp,study,roster)
    cases, bank, known_reads, originals = [], {}, set(), []
    # Audit all baseline labels from their settled physical source. The site
    # selection and both prompts use the specified clause witnesses alone.
    train = {r['key']:r for batch in roster for r in batch if r['dataset']==DATASET and r['project_split']=='train'}
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        for j,batch in enumerate(roster,1):
            obs = ROOT/read(HANDOFF/'formal_b1_observe_current.json' if j==1 else pointer(j))['artifact_root']
            obs_binding = read(obs/'binding.json')
            end = read(obs/'terminal.json')
            assert obs.name==digest(obs_binding) and not end['TEST_opened']
            assert all(sha(obs/'source_snapshot'/f)==h for f,h in obs_binding['source_sha256'].items())
            history=journal._observations(ARM,j)
            assert end['observation_receipts'][ARM]==history['train_observation_sha256']
            originals.append(sha(obs/'terminal.json'))
            for n,source in enumerate(s for s in batch if s['dataset']==DATASET):
                key=source['key']
                assert key in train
                views={k:next(v for v in source['views'] if v['id']==q) for k,q in TASKS.items()}
                view=views['development']
                stored=read(journal.directory(ARM,j)/'predictions'/(digest(key)+'.json'))
                assert history['predictions'][key]==digest(stored)
                skill = digest(journal.library(ARM,j-1)['programs'][DATASET])
                # The verification helper also checks the physical source
                # bundle and original program before returning all tasks.
                anchor = next(v for v in source['views'] if v['id']=='nda-3')
                previous = verify_prediction(db,train,key,anchor,stored['result'],known_reads,skill)
                bank[key]={'views':views,'native':{q:previous[q] for q in TASKS.values()}}
                if (j,n) not in REVIEWS:
                    continue
                stratum,dev,rcv,labels=REVIEWS[j,n]
                spans=spans_for(view)
                indices={i for k,t in enumerate(spans) if CUES.search(t) for i in range(max(0,k-4),min(len(spans),k+3)) if spans[i].strip()}
                # Add headings and split continuations on every source, never
                # a per-case disclosure of the reviewed path to either arm.
                assert set(dev+rcv)<=indices
                payload={'complete_document':view['public']['source_text'],
                         'indexed_clause_cues':[{'span_id':i,'text':spans[i]} for i in sorted(indices)]}
                cases.append({'source':key,'stratum':stratum,'views':views,'payload':payload,
                              'independent_witnesses':[list(dev),list(rcv)],
                              'independent_expected':{k:YES if b else UNKNOWN for k,b in zip(TASKS,labels,strict=True)}})
    assert len(cases)==len(REVIEWS) and len(bank)==len(known_reads)==24
    grade=training['native_grade_paths'][DATASET]
    assert 'train' in Path(grade).parts
    files = [Path(__file__).resolve().relative_to(ROOT),
             'experiments/convergence_revision5_cni_oral_scope.py',
             'legal_skill_guard/paired_interfaces/residual.py','legal_skill_guard/skill_evolution/clients.py',
             'legal_skill_guard/skill_evolution/ledger.py','legal_skill_guard/rr/client.py']
    protocol={'study':'source_bound_CNI_independent_routes',
              'cases_sha256':digest(cases),'old_native_bank_sha256':digest(bank),'old_observations_sha256':originals,
              'sources_sha256':{str(p):sha(ROOT/p) for p in files},'executor':study['executor'],
              'grade_path':grade,'grade_sha256':training['native_grade_sha256'][grade],
              'states':len(layouts()[0].states),'asset_versions':[a['version'] for a in layouts()[1]],
              'native_hypotheses':list(TASKS.values()),'TRAIN_only':True,'pairs':len(cases)}
    return protocol,cases,bank


def contract(asset, case):
    evidence={'type':'array','maxItems':12,'items':{'type':'integer','minimum':0,
              'maximum':len(spans_for(case['views']['development']))-1}}
    coords={f['name']:{'enum':asset['domains'][f['name']]} for f in asset['features']}
    schema=record_schema({'relations':record_schema(coords),'evidence':record_schema(dict.fromkeys(TASKS,evidence))})
    prompts='\n'.join(residual.reader_prompt(asset,verbalize_relations=True).splitlines()[4:])
    return [{'role':'system','content':COMMON+'\n'+prompts},
            {'role':'user','content':json.dumps(case['payload'],ensure_ascii=False,sort_keys=True)}],schema


def decode(asset, case, response):
    _, schema = contract(asset,case)
    try:
        if response['finish_reason']!='stop':
            raise ValueError('Incomplete reading')
        wire=json.loads(response['content'])
        jsonschema.validate(wire,schema)
        receipt=residual.decode(asset,wire['relations'],{},module_binding=layouts()[0].binding)
        if not receipt['valid']:
            raise ValueError('Reading outside the certified domain')
        spans=spans_for(case['views']['development'])
        for evidence in wire['evidence'].values():
            if len(evidence)!=len(set(evidence)) or any(not spans[i].strip() for i in evidence):
                raise ValueError('Evidence must use distinct nonempty spans')
        return {k:{'answer':v,'raw_evidence':sorted(wire['evidence'][k]),
                   'evidence':sorted(wire['evidence'][k]) if v==YES else []}
                for k,v in receipt['outputs'].items()}
    except (ValueError,jsonschema.ValidationError) as error:
        return {k:{'answer':None,'raw_evidence':[],'evidence':[],'error':type(error).__name__}
                for k in TASKS}


def verify_pair(db, identity, case, asset, result):
    row = db.execute('select status,role,source,purpose,request_hash,result from calls where id=?',(identity,)).fetchone()
    assert row[:4]==('completed','executor',case['source'],'skill_actor')
    actual=json.loads(row[5])
    folder=Path(actual['artifact_directory'])
    request,wire=(read(folder/p) for p in ('request.json','wire_request.json'))
    raw=base64.b64decode(wire['body_b64'],validate=True)
    assert hashlib.sha256(raw).hexdigest()==wire['body_sha256'] and json.loads(raw)==request['payload']
    assert read(folder/'result.json')==actual and request['id']==identity and request['request_hash']==row[4]
    messages,schema=contract(asset,case)
    payload=request['payload']
    assert payload['messages']==messages and payload['response_format']['json_schema']['schema']==schema
    assert payload['model']=='Qwen/Qwen3-8B' and payload['chat_template_kwargs']['enable_thinking'] is False
    assert actual['thinking_requested'] is False and decode(asset,case,actual)==result
    return actual['usage']['total_tokens']


def score(cases, records, bank, grades):
    totals={}
    for role in ('original',*ROLES):
        totals[role]={k:[] for k in TASKS}
    for case,record in zip(cases,records,strict=True):
        key=case['source']
        for kind,task in TASKS.items():
            old=bank[key]['native'][task]
            reads={'original':{'answer':old['answer'],'evidence':old['evidence_sentence_ids']},
                   **{role:record[role]['observation'][kind] for role in ROLES}}
            for role,observed in reads.items():
                r=grade_view(DATASET,case['views'][kind],grades[key][task],observed['answer'],observed['evidence'])
                totals[role][kind].append({'exact':r['grade'],'joint_evidence':r['grade']*r['evidence_f1'],
                   'source_polarity':case['independent_expected'][kind]==observed['answer']})
    return {role:{kind:{m:mean(r[m] for r in rows) for m in rows[0]}
                  for kind,rows in tasks.items()} for role,tasks in totals.items()}


def run(execute):
    binding,cases,bank=materials()
    out=HOME/digest(binding)
    immutable_json(out/'binding.json',binding)
    immutable_json(out/'cases.json',cases)
    if (out/'terminal.json').exists():
        print(json.dumps(read(out/'terminal.json'),sort_keys=True),flush=True)
        return
    if not execute:
        assert not POINTER.exists() or read(POINTER)['status']!='running'
        write_status(out,{'status':'prepared','pairs':len(cases),'planned_calls':2*len(cases)},POINTER)
        print(str(out.relative_to(ROOT)),flush=True)
        return
    assert ROOT/read(POINTER)['artifact_root']==out
    for path,expected in binding['sources_sha256'].items():
        dest=out/'source_snapshot'/path
        dest.parent.mkdir(parents=True,exist_ok=True)
        if not dest.exists():
            with dest.open('xb') as f:
                f.write((ROOT/path).read_bytes())
        assert sha(dest)==expected
    run_id='convergence-revision5-CNI-independent-routes-'+out.name[:16]
    ledger=EvolutionLedger(LEDGER,run_id=run_id,
                           sources={'train':[c['source'] for c in cases],'dev':[],'test':[]},binding=binding)
    executor=FrozenExecutor(ledger,out,binding['executor'])
    executor.readiness()
    records=[]
    write_status(out,{'status':'running','settled_pairs':0},POINTER)
    for case in cases:
        pair={}
        for role,asset in zip(ROLES,layouts()[1],strict=True):
            identity=f'{run_id}:{digest(case["source"])}:{role}'
            messages,schema=contract(asset,case)
            response=executor.generate(identity,source=case['source'],purpose='skill_actor',messages=messages,thinking=False,schema=schema)
            pair[role]={'physical_call_id':identity,'observation':decode(asset,case,response)}
        records.append(pair)
        immutable_json(out/'paired_reads'/(digest(case['source'])+'.json'),pair)
        write_status(out,{'status':'running','settled_pairs':len(records)},POINTER)
        print(json.dumps({'settled_pairs':len(records)}),flush=True)
    immutable_json(out/'predictions.json',records)
    tokens=Counter()
    ids=set()
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        for case,pair in zip(cases,records,strict=True):
            for role,asset in zip(ROLES,layouts()[1],strict=True):
                row=pair[role]
                identity=row['physical_call_id']
                ids.add(identity)
                tokens[role]+=verify_pair(db,identity,case,asset,row['observation'])
        assert not db.execute("select 1 from calls where status='reserved'").fetchone()
        counts=dict(db.execute('select status,count(*) from calls group by status'))
    assert len(ids)==2*len(cases)
    path=ROOT/binding['grade_path']
    assert sha(path)==binding['grade_sha256']
    grades=read(path)
    summary={'status':DONE,'pairs':len(cases),'verified_original_TRAIN_responses':len(bank),
             'states_preserved':binding['states'],'new_executor_requests':len(ids),'new_teacher_requests':0,
             'tokens_by_role':dict(tokens),'TEACHER_and_TEST_used':False,'ledger':counts,
             'matched':score(cases,records,bank,grades),
             'original_24_TRAIN_native_correct':{t:sum(v['native'][t]['answer']==grades[k][t]['answer'] for k,v in bank.items()) for t in TASKS.values()},
             'runner_sha256':sha(Path(__file__))}
    immutable_json(out/'terminal.json',summary)
    write_status(out,{'status':DONE,'settled_pairs':len(records)},POINTER)
    print(json.dumps(summary,sort_keys=True),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=('prepare','run'))
    run(parser.parse_args().phase=='run')
