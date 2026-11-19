"""Compare a consumer-derived designation relation on original CNI TRAIN contracts."""

import argparse
from collections import Counter
from functools import lru_cache
import inspect
import json
from pathlib import Path
import re
import sqlite3

import jsonschema

from experiments.convergence_formal_b1_observe import POINTER as FIRST_OBSERVE
from experiments.convergence_formal_train_observe import load_roster, pointer
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision5_cni_disposition_scope import ARM, DATASET, TrainingJournal, spans_for
from experiments.convergence_revision5_m2_cumulative_audit import physical_wire
from legal_skill_guard.paired_interfaces import residual
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view, record_schema
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE/'revision5_CNI_designation_coverage_20261119'
POINTER = HANDOFF/'revision5_CNI_designation_current.json'
DONE = 'completed_revision5_CNI_designation_TRAIN'
TASK = 'nda-1'
ROLES = ('fixed', 'synthesized')
E, C, N = 'Entailment', 'Contradiction', 'NotMentioned'
TARGET = 'governs_original_confidential_status'
OPTION = 'admits_without_express_designation'
MANDATORY = 'designation_required_for_every_qualification_route'
CUES = re.compile(r'\b(?:Confidential Information|mark(?:ing|ed)|designat\w*|identif\w*|legend)\b', re.I)
COMMON = (
    'Read the complete NDA and its indexed clause cues. Inspect the conditions for information to qualify as '
    'confidential at the point it is disclosed or created. Use one candidate alternative and decide whether it '
    'governs that qualification and lets at least some information qualify without express identification by '
    'the disclosing party. If any such operative alternative exists, choose it. A rule for marking copies, '
    'a receiving party notice obligation, or a heading that names a protected subset does not by itself govern '
    'qualification of the original information. If the contract contains no such alternative, examine whether '
    'each way information can qualify affirmatively requires express designation. Mark false on the universal '
    'condition only if you have checked the full definition and its incorporated clauses. Keep unresolved '
    'facts null. Cite the smallest set of original span IDs supporting your finding, including the lead-in '
    'and coordinated conditions if their link is needed. Return only the specified structure.'
)


def consume(v, _context):
    if v['governs_original_confidential_status'] == True and v['admits_without_express_designation'] == True:
        return {'classification': C}
    if v['governs_original_confidential_status'] == False or v['admits_without_express_designation'] == False:
        if v['designation_required_for_every_qualification_route'] is True:
            return {'classification': E}
        if v['designation_required_for_every_qualification_route'] is False:
            return {'classification': N}
    return {'classification': None}


@lru_cache(maxsize=1)
def layouts():
    procedure = inspect.getsource(consume)
    meanings = {
        TARGET: 'the selected clause is operative for whether the original information qualifies for confidentiality',
        OPTION: 'the same selected clause provides a real route by which covered information can qualify even '
                'without express identification. Mere silence within that clause is insufficient for true',
        MANDATORY: 'every clause that provides a way to qualify expressly requires designation by the disclosing '
                   'party, taking account of all routes, including oral and created information',
    }
    spec = residual.FiniteModule.build(
        'confidentiality_designation_scope', {field: [True, False, None] for field in meanings}, [{}], consume,
        consumer_sha256=digest(procedure), program_source=procedure, protected_status_fields=(MANDATORY,),
        source_scope={'source_fields':['source_text'], 'local_unit':'operative qualification of information',
                      'field_meanings':meanings})
    fixed = [{'name':f,'operation':'field','field':f} for f in spec.fields]
    joined, = (f for f in residual.consumer_relations(spec) if f['expression']['op']=='and'
               and set(f['consumer_dependencies'])=={TARGET,OPTION})
    joined = {**joined,'name':'qualification_route_admits_undesignated_information'}
    variants = [
        residual.compile_pair(spec,fixed,operation='fixed_coordinates',layout='anchored'),
        residual.compile_pair(spec,[joined,fixed[-1]],operation='consumer_relational_projection',layout='anchored'),
    ]
    for state in spec.states:
        for asset in variants:
            decoded = residual.decode(asset,residual.encode(asset['features'],state),{},module_binding=spec.binding)
            assert decoded['valid'] and decoded['outputs']==consume(state,{})
    return spec, variants


def source_payload(view):
    spans = spans_for(view)
    indices = {j for i,text in enumerate(spans) if CUES.search(text)
               for j in range(max(0,i-1),min(len(spans),i+3)) if spans[j].strip()}
    return {'complete_document':view['public']['source_text'],
            'indexed_clause_cues':[{'span_id':i,'text':spans[i]} for i in sorted(indices)]}


def bind_request(asset, case):
    fields = {f['name']:{'enum':asset['domains'][f['name']]} for f in asset['features']}
    schema = record_schema({'relations':record_schema(fields),
                            'evidence_spans':{'type':'array','maxItems':8,
                                              'items':{'type':'integer','minimum':0,
                                                       'maximum':len(spans_for(case['view']))-1}}})
    prompt = '\n'.join(residual.reader_prompt(asset,verbalize_relations=True).splitlines()[4:])
    messages = [{'role':'system','content':COMMON+'\n'+prompt},
                {'role':'user','content':json.dumps(case['payload'],ensure_ascii=False)}]
    return messages,schema


def decode(asset, case, schema, raw):
    try:
        if raw['finish_reason']!='stop':
            raise ValueError('Unsettled output')
        observed = json.loads(raw['content'])
        jsonschema.validate(observed,schema)
        evidence = sorted(observed['evidence_spans'])
        source = spans_for(case['view'])
        if len(evidence)!=len(set(evidence)) or any(not source[i].strip() for i in evidence):
            raise ValueError('Evidence must use distinct nonempty source spans')
        compiled = residual.decode(asset,observed['relations'],{},module_binding=layouts()[0].binding)
        if not compiled['valid']:
            raise ValueError('Outside the compiled support')
        answer = compiled['outputs']['classification']
        if answer in (E,C) and not evidence:
            raise ValueError('An asserted marking rule requires source evidence')
        return {'answer':answer,'evidence':evidence if answer in (E,C) else [],
                'relations':observed['relations'],'wire_valid':True}
    except (ValueError,jsonschema.ValidationError):
        return {'answer':None,'evidence':[],'wire_valid':False}


def physical_prediction(db, cohort, source, before, view, verified):
    entry, = before['result']['reads']
    trace, = entry['execution']['traces']
    identity=trace['physical_call_id']
    verified.add(identity)
    physical_wire(db,cohort,identity,source)
    body, = db.execute('select result from calls where id=?',(identity,)).fetchone()
    actual = json.loads(body)
    assert actual['content']==trace['raw_content']
    request = read(Path(actual['artifact_directory'])/'request.json')['payload']
    user = request['messages'][-1]['content']
    assert view['public']['question'] in user
    assert json.dumps(view['public']['source_text'],ensure_ascii=False)[1:-1] in user or (
        json.dumps(view['public']['source_text'],ensure_ascii=True)[1:-1] in user)
    raw = json.loads(actual['content'])['value'][TASK]
    old = before['result']['native'][TASK]
    assert old['answer']==raw['answer'] and old['evidence_sentence_ids']==raw['evidence_sentence_ids']
    return {'answer':old['answer'],'evidence':old['evidence_sentence_ids'],'wire_valid':old['handled']}


def materials():
    preflight = read(HOME/'source_only_preflight.json')
    scoped = {tuple(r['pos']):r for r in preflight['source_only_local_conclusions']
              if r['exclusive_designation_semantic_label'] is not None}
    observed = ROOT/read(pointer(3))['artifact_root']
    reference = read(observed/'binding.json')
    checkpoint = ROOT/reference['checkpoint_root']
    study = read(checkpoint/'binding.json')
    roster = load_roster(study)
    assert preflight['TRAIN_only'] and preflight['roster_sha256']==digest(roster)
    journal = TrainingJournal(checkpoint,study,roster)
    cohort = {s['key'] for batch in roster for s in batch if s['dataset']==DATASET}
    cases, prior, verified, frozen_receipts = [], [], set(), []
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        for number,batch in enumerate(roster,1):
            stage = ROOT/read(FIRST_OBSERVE if number==1 else pointer(number))['artifact_root']
            binding = read(stage/'binding.json')
            terminal = read(stage/'terminal.json')
            assert not terminal['TEST_opened'] and stage.name==digest(binding)
            assert all(sha(stage/'source_snapshot'/p)==h for p,h in binding['source_sha256'].items())
            history = journal._observations(ARM,number)
            assert terminal['observation_receipts'][ARM]==history['train_observation_sha256']
            frozen_receipts.append(sha(stage/'terminal.json'))
            for index,source in enumerate(s for s in batch if s['dataset']==DATASET):
                key = source['key']
                view, = (v for v in source['views'] if v['id']==TASK)
                save = read(journal.directory(ARM,number)/'predictions'/(digest(key)+'.json'))
                assert source['project_split']=='train' and history['predictions'][key]==digest(save)
                old = physical_prediction(db,cohort,key,save,view,verified)
                prior.append({'source':key,'answer':old['answer'],'evidence':old['evidence'],'view':view})
                row = scoped.get((number,index))
                if row is None:
                    continue
                spans = spans_for(view)
                assert row['id']==key and all(digest(spans[int(i)])==h for i,h in row['span_hashes'].items())
                payload = source_payload(view)
                assert set(row['anchor_ids'])<={r['span_id'] for r in payload['indexed_clause_cues']}
                cases.append({'source':key,'view':view,'payload':payload,'prior':old,
                              'review_stratum':row['stratum'],'expected_source_label':row['exclusive_designation_semantic_label'],
                              'review_ids':row['anchor_ids'],'source_benchmark_scope_ambiguous':(number,index)==(6,2)})
    assert len(cases)==len(scoped)==6 and len(prior)==len(verified)==24
    files = {'experiments/convergence_revision5_cni_designation.py',
             'experiments/convergence_revision5_m2_cumulative_audit.py',
             'experiments/convergence_revision5_cni_disposition_scope.py',
             'legal_skill_guard/paired_interfaces/residual.py','legal_skill_guard/skill_evolution/native.py',
             'legal_skill_guard/skill_evolution/clients.py','legal_skill_guard/skill_evolution/ledger.py',
             'legal_skill_guard/rr/client.py'}
    grade = reference['native_grade_paths'][DATASET]
    assert '/train/' in grade
    protocol = {'study':'revision5_CNI_consumer_designation_scope',
                'cases_sha256':digest(cases),'prior_sha256':digest(prior),'prior_observations':frozen_receipts,
                'source_review_sha256':sha(HOME/'source_only_preflight.json'),
                'grade_path':grade,'grade_sha256':reference['native_grade_sha256'][grade],
                'source_sha256':{p:sha(ROOT/p) for p in sorted(files)},'executor':study['executor'],
                'consumer_states':len(layouts()[0].states),'candidate_versions':[a['version'] for a in layouts()[1]],
                'paired_calls':2*len(cases),'TRAIN_only':True}
    return protocol,cases,prior


def score(cases, records, prior, grade):
    comparison=[]
    for case, pair in zip(cases,records,strict=True):
        target=grade[case['source']][TASK]
        row={}
        for role,p in {'earlier_common':case['prior'],**pair}.items():
            out=grade_view(DATASET,case['view'],target,p['answer'],p['evidence'])
            row[role]={'native_exact':out['grade'],'native_evidence_f1':out['evidence_f1'],
                       'joint_native_evidence_f1':out['evidence_f1']*out['grade'],
                       'source_polarity':p['answer']==case['expected_source_label'],
                       'overlaps_reviewed_spans':bool(set(p['evidence'])&set(case['review_ids'])),
                       'wire_valid':p['wire_valid'],'answer':p['answer']}
        comparison.append({'stratum':case['review_stratum'],'scores':row,
                           'source_benchmark_scope_ambiguous':case['source_benchmark_scope_ambiguous']})
    return {'prior_labels':dict(Counter(p['answer'] for p in prior)),
            'prior_native_correct':sum(p['answer']==grade[p['source']][TASK]['answer'] for p in prior),
            'prior_native_gold':dict(Counter(grade[p['source']][TASK]['answer'] for p in prior)),
            'paired_scores':comparison}


def run(execute):
    protocol,cases,prior = materials()
    stage = HOME/digest(protocol)
    immutable_json(stage/'binding.json',protocol)
    immutable_json(stage/'cases.json',cases)
    if (stage/'terminal.json').exists():
        print(json.dumps(read(stage/'terminal.json'),sort_keys=True),flush=True)
        return
    if not execute:
        if POINTER.exists() and read(POINTER)['status']=='running':
            raise ValueError('Preserve the live bound comparison')
        write_status(stage,{'status':'prepared','pairs':len(cases),'planned_calls':protocol['paired_calls']},POINTER)
        print(str(stage),flush=True)
        return
    assert ROOT/read(POINTER)['artifact_root']==stage
    for path, expected in protocol['source_sha256'].items():
        dest=stage/'source_snapshot'/path
        dest.parent.mkdir(parents=True,exist_ok=True)
        if not dest.exists():
            with dest.open('xb') as file:
                file.write((ROOT/path).read_bytes())
        assert sha(dest)==expected
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        if db.execute("select 1 from calls where status='reserved'").fetchone():
            raise ValueError('Settle earlier reservations first')
    run_id='convergence-revision5-CNI-designation-'+stage.name[:16]
    roster=[c['source'] for c in cases]
    ledger=EvolutionLedger(LEDGER,run_id=run_id,sources={'train':roster,'dev':[],'test':[]},binding=protocol)
    executor=FrozenExecutor(ledger,stage,protocol['executor'])
    executor.readiness()
    data, identities, tokens = [], set(), 0
    write_status(stage,{'status':'running','completed_pairs':0},POINTER)
    for case in cases:
        key=case['source']
        pair={}
        for role,asset in zip(ROLES,layouts()[1],strict=True):
            messages,schema=bind_request(asset,case)
            identity=f'{run_id}:{digest(key)}:{role}'
            out=executor.generate(identity,source=key,purpose='skill_actor',messages=messages,thinking=False,schema=schema)
            pair[role]={**decode(asset,case,schema,out),'physical_call_id':identity}
            tokens+=out['usage']['total_tokens']
            identities.add(identity)
        data.append(pair)
        immutable_json(stage/'pairs'/(digest(key)+'.json'),pair)
        write_status(stage,{'status':'running','completed_pairs':len(data)},POINTER)
        print(json.dumps({'completed_pairs':len(data)}),flush=True)
    immutable_json(stage/'paired_reads.json',data)
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        assert set(db.execute('select id,status from calls where id like ?',(run_id+':%',)))=={
            (identity,'completed') for identity in identities}
    grade=ROOT/protocol['grade_path']
    assert len(identities)==protocol['paired_calls'] and sha(grade)==protocol['grade_sha256']
    result={'status':DONE,'executor_calls':len(identities),'executor_tokens':tokens,'teacher_calls':0,
            'TRAIN_only':True,**score(cases,data,prior,read(grade))}
    immutable_json(stage/'terminal.json',result)
    write_status(stage,{'status':DONE,'physical_reads':len(identities)},POINTER)
    print(json.dumps(result,sort_keys=True),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=('prepare','run'))
    run(parser.parse_args().phase=='run')
