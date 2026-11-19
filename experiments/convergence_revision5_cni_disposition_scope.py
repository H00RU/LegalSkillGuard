"""Measure whether a synthesized end-trigger relation attaches to the right NDA obligation."""

import argparse
from collections import defaultdict
from functools import lru_cache
import hashlib
import inspect
import json
from pathlib import Path
import re
import sqlite3
from textwrap import dedent

import jsonschema

from experiments.convergence_formal_b1_observe import POINTER as FIRST_OBSERVE, load_roster
from experiments.convergence_formal_bootstrap import POINTER as BOOTSTRAP
from experiments.convergence_formal_train_observe import pointer as observe_pointer
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import residual
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view, record_schema
from legal_skill_guard.skill_evolution.objects import digest


DATASET = 'ContractNLI'
TASK = 'nda-16'
ARM = 'common_teacher_skill_learning'
RUNNER = 'experiments/convergence_revision5_cni_disposition_scope.py'
HOME = BASE/'revision5_CNI_disposition_scope_20261119'
POINTER = HANDOFF/'revision5_CNI_disposition_scope_current.json'
DONE = 'completed_revision5_CNI_disposition_scope_TRAIN'
ROLES = ('fixed_coordinates', 'synthesized_end_trigger')
# Reviewed from original complete TRAIN contracts, never passed to the reader.
# Positive sets bind a disposal and its governing end-of-relationship trigger.
# Request-only cases were examined for a separate closure-triggered disposal.
REVIEWS = {
    (1,2): ('request_only_split', False, (43,44,45)),
    (2,2): ('end_trigger_in_list', True, (31,37,38)),
    (4,2): ('request_only_inline', False, (13,)),
    (6,2): ('end_and_request_with_sibling_demand', True, (15,20,22)),
    (7,2): ('end_and_request_on_separate_events', True, (25,29,31)),
    (8,2): ('request_only_with_survival_clause', False, (21,22,35,36)),
}
DISPOSAL = re.compile(r'\b(?:return(?:s|ed|ing)?|destroy\w*|eras\w*|delet\w*|deliver(?:ed|s|ing)?)\b', re.I)
TIME = re.compile(r'\b(?:terminat\w*|expir\w*|request\w*|deman\w*|surviv\w*|withdraw\w*)\b', re.I)
INFO = re.compile(r'\b(?:information|materials?|copies|copy|records?)\b', re.I)
LIST_LEAD = re.compile(r'\b(?:shall|agrees to|is required to)\s*:\s*$', re.I)
COMMON = (
    'Review the complete NDA. The shared list of native span IDs identifies possible disposition and timing language. '
    'Trace only a requirement for the receiver to return, destroy, or erase at least some protected information. '
    'Return may be an option alongside destruction. Respect enumerated subclauses and exceptions. '
    'An obligation activated at agreement or covered relationship end qualifies, including if written request '
    'is an alternative. A separate survival clause, request, termination notice, departure of an affiliate, or agreement '
    'expiry mentioned elsewhere does not put this disposition at closure. Read each field literally. If several '
    'disposition obligations exist, choose one bound to closure if present. Otherwise describe the relevant '
    'request-only or other disposition and verify the rest of the document before declaring scope_complete. '
    'Use null for uncertain relations. For a bound end-trigger cite the native span IDs for the disposition and '
    'its trigger, adding the governing subject or list header where needed. For absent end-trigger return an '
    'empty evidence list. Return the specified JSON structure.'
)


def consume(v, context):
    if v['disposition'] == 'receiver_required':
        if v['condition'] == 'agreement_end' and v['applies_to_disposition'] == 'same_obligation':
            return {'classification':'Entailment'}
        if v['scope_complete'] is True:
            if v['condition'] == 'other_condition' or v['applies_to_disposition'] == 'different_obligation':
                return {'classification':'NotMentioned'}
    if v['disposition'] == 'no_relevant_requirement' and v['scope_complete'] is True:
        return {'classification':'NotMentioned'}
    return {'classification':None}


@lru_cache(maxsize=1)
def module():
    source = dedent(inspect.getsource(consume))
    return residual.FiniteModule.build(
        'disposition_trigger_scope',
        {'disposition':['receiver_required','no_relevant_requirement',None],
         'condition':['agreement_end','other_condition',None],
         'applies_to_disposition':['same_obligation','different_obligation',None],
         'scope_complete':[True,False,None]},
        [{}], consume, consumer_sha256=hashlib.sha256(source.encode()).hexdigest(), program_source=source,
        protected_status_fields=('scope_complete',),
        source_scope={'source_fields':['source_text'],
                      'local_unit':'same-event trigger of a confidential information disposal duty',
                      'field_meanings':{
                          'disposition':'the receiver has a real obligation to return or destroy protected information or copies. Merely authorizing destruction does not qualify.',
                          'condition':'the governing condition of the relevant obligation describes the closing of the agreement or the expressly covered relationship; requests alone or survival are other conditions.',
                          'applies_to_disposition':'the condition governs the very same return or destruction of the same protected material; never transfer a condition from the separate confidentiality or survival clause.',
                          'scope_complete':'all local disposition and timing sites in the supplied complete contract were considered.',
                      }},
    )


@lru_cache(maxsize=1)
def layouts():
    spec = module()
    fixed = [{'name':field,'operation':'field','field':field} for field in spec.fields]
    wanted = {'condition','applies_to_disposition'}
    relation, = (f for f in residual.consumer_relations(spec)
                 if f['expression']['op'] == 'and' and set(f['consumer_dependencies']) == wanted)
    relation = {**relation, 'name':'end_condition_governs_same_disposition'}
    candidate = [f for f in fixed if f['field'] not in wanted]+[relation]
    result = (residual.compile_pair(spec,fixed,operation='fixed_coordinates',layout='anchored'),
              residual.compile_pair(spec,candidate,operation='consumer_relational_projection',layout='anchored'))
    for state in spec.states:
        for asset in result:
            obs = residual.encode(asset['features'],state)
            actual = residual.decode(asset,obs,{},module_binding=spec.binding)
            if not actual['valid'] or actual['outputs'] != consume(state,{}):
                raise ValueError('The synthesized link changed the certified consumer')
    return result


def spans_for(view):
    pub = view['public']; text = pub['source_text']
    return [text[a:b] for a,b in pub['sentence_spans']]


def source_payload(view):
    spans = spans_for(view)
    visible = set()
    for i,s in enumerate(spans):
        text = ' '.join(s.split())
        if TIME.search(text) or (DISPOSAL.search(text) and INFO.search(text)) or LIST_LEAD.search(text):
            visible.update(range(max(0,i-2),min(len(spans),i+3)))
    return {'complete_document':view['public']['source_text'],
            'indexed_clause_cues':[{'span_id':i,'text':spans[i]} for i in sorted(visible) if spans[i].strip()]}


def request(asset, case):
    n = len(spans_for(case['view']))
    coords = {f['name']:{'enum':asset['domains'][f['name']]} for f in asset['features']}
    schema = record_schema({'relations':record_schema(coords),
                           'evidence_spans':{'type':'array','maxItems':6,
                                             'items':{'type':'integer','minimum':0,'maximum':n-1}}})
    instructions = '\n'.join(residual.reader_prompt(asset,verbalize_relations=True).splitlines()[4:])
    messages = [{'role':'system','content':COMMON+'\n'+instructions},
                {'role':'user','content':json.dumps(case['payload'],ensure_ascii=False)}]
    return messages,schema


def decode(asset, schema, spans, content, finish_reason):
    try:
        if finish_reason != 'stop':
            raise ValueError('Nonterminal response')
        raw=json.loads(content)
        jsonschema.validate(raw,schema)
        evidence = raw['evidence_spans']
        if len(evidence)!=len(set(evidence)) or any(not spans[i].strip() for i in evidence):
            raise ValueError('Evidence must refer to distinct nonempty original spans')
        outcome=residual.decode(asset,raw['relations'],{},module_binding=module().binding)
        if not outcome['valid']:
            raise ValueError('Reading is outside certified support')
        label=outcome['outputs']['classification']
        if label=='Entailment' and not evidence:
            raise ValueError('An affirmative disposition requires its evidence')
        return {'answer':label,'evidence': sorted(evidence) if label=='Entailment' else [],'wire_valid':True}
    except (ValueError,jsonschema.ValidationError):
        return {'answer':None,'evidence':[],'wire_valid':False}


def materials():
    root=ROOT/read(BOOTSTRAP)['artifact_root']
    spec=read(root/'binding.json')
    roster=load_roster(spec)
    journal=TrainingJournal(root,spec,roster)
    cases=[]
    grade={}
    observations=[]
    for batch in sorted({b for b,_ in REVIEWS}):
        stage=ROOT/read(FIRST_OBSERVE if batch==1 else observe_pointer(batch))['artifact_root']
        prior=read(stage/'binding.json')
        path=prior['native_grade_paths'][DATASET]
        grade[path]=prior['native_grade_sha256'][path]
        cert=journal._observations(ARM,batch)
        observations.append(sha(stage/'terminal.json'))
        same=[s for s in roster[batch-1] if s['dataset']==DATASET]
        for pos,source in enumerate(same):
            if (batch,pos) not in REVIEWS:
                continue
            view, = [v for v in source['views'] if v['id']==TASK]
            old=read(journal.directory(ARM,batch)/'predictions'/(digest(source['key'])+'.json'))
            if digest(old)!=cert['predictions'][source['key']] or source['project_split']!='train':
                raise ValueError('Use only bound original TRAIN mothers')
            case={'pos':[batch,pos],'source':source['key'],'view':view,'prior':old,'payload':source_payload(view)}
            stratum,positive,ids=REVIEWS[batch,pos]
            visible={v['span_id'] for v in case['payload']['indexed_clause_cues']}
            if not set(ids)<=visible or not all(spans_for(view)[i].strip() for i in ids):
                raise ValueError('A reviewed span is absent from the shared anchor inventory')
            cases.append(case)
    path,=grade
    files={RUNNER,'legal_skill_guard/paired_interfaces/residual.py',
           'legal_skill_guard/rr/client.py','legal_skill_guard/skill_evolution/clients.py',
           'legal_skill_guard/skill_evolution/ledger.py','legal_skill_guard/skill_evolution/native.py'}
    bind={'study':'revision5_CNI_disposition_end_trigger_TRAIN','binding_sha256':module().binding,
          'consumer_states':len(module().states),'candidate_asset_versions':[a['version'] for a in layouts()],
          'actor_config':spec['executor'],'case_set_sha256':digest(cases),'original_observation_sha256':observations,
          'grade_path':path,'grade_sha256':grade[path],'source_sha256':{f:sha(ROOT/f) for f in sorted(files)},
          'paired_calls':2*len(cases),'primary':'unconditional native exact and evidence F1',
          'selection':'six retrospective source-reviewed contrasting TRAIN contracts','TRAIN_only':True}
    return bind,cases


def score(cases, records, grades):
    output=defaultdict(list)
    for case, pair in zip(cases,records,strict=True):
        group,positive,_=REVIEWS[tuple(case['pos'])]
        for who,o in pair.items():
            value=grade_view(DATASET,case['view'],grades[case['source']][TASK],o['answer'],o['evidence'])
            # Some audited positive clauses also contain request-only siblings. Their
            # review sets record coverage, so concrete citation sufficiency is audited separately.
            output[who].append({'structure':group,'exact':bool(value['grade']),'f1':value['evidence_f1'],
                                'native_label':o['answer'],'wire_valid':o['wire_valid'],
                                'source_review_agrees_on_label':o['answer']==('Entailment' if positive else 'NotMentioned')})
    return dict(output)


def run(execute):
    binding,cases=materials()
    stage=HOME/digest(binding)
    if (stage/'terminal.json').exists():
        print(json.dumps(read(stage/'terminal.json'),sort_keys=True),flush=True)
        return
    if execute and (not POINTER.exists() or ROOT/read(POINTER)['artifact_root']!=stage):
        raise ValueError('Prepare the exact comparison first')
    immutable_json(stage/'binding.json',binding)
    immutable_json(stage/'cases.json',cases)
    if not execute:
        if POINTER.exists() and read(POINTER)['status']=='running':
            raise ValueError('Preserve the live binding')
        write_status(stage,{'status':'prepared','planned_calls':binding['paired_calls']},POINTER)
        print(json.dumps({'stage':str(stage.relative_to(ROOT)),'matched_pairs':len(cases),
                          'consumer_states':binding['consumer_states']}),flush=True)
        return
    for name,tag in binding['source_sha256'].items():
        dest=stage/'source_snapshot'/name
        dest.parent.mkdir(parents=True,exist_ok=True)
        if not dest.exists():
            with dest.open('xb') as stream:
                stream.write((ROOT/name).read_bytes())
        if sha(dest)!=tag:
            raise ValueError('The archived source differs from the bound version')
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        if db.execute("select 1 from calls where status='reserved'").fetchone():
            raise ValueError('Reconcile the previous reservation')
    run_id='convergence-revision5-CNI-disposition-'+stage.name[:16]
    ledger=EvolutionLedger(LEDGER,run_id=run_id,sources={'train':[c['source'] for c in cases],'dev':[],'test':[]},
                           binding=binding)
    reader=FrozenExecutor(ledger,stage,binding['actor_config'])
    reader.readiness()
    records,identities,tokens=[],[],0
    write_status(stage,{'status':'running','completed_pairs':0},POINTER)
    for case in cases:
        native=case['prior']['result']['native'][TASK]
        pair={'earlier_common_program':{'answer':native['answer'],'evidence':native['evidence_sentence_ids'],'wire_valid':True}}
        for role,asset in zip(ROLES,layouts(),strict=True):
            messages,schema=request(asset,case)
            call_id=f'{run_id}:{digest(case["source"])}:{role}'
            out=reader.generate(call_id,source=case['source'],purpose='skill_actor',messages=messages,thinking=False,schema=schema)
            pair[role]={**decode(asset,schema,spans_for(case['view']),out['content'],out['finish_reason']),
                        'physical_call_id':call_id}
            identities.append(call_id)
            tokens+=out['usage']['total_tokens']
        records.append(pair)
        write_status(stage,{'status':'running','completed_pairs':len(records)},POINTER)
    immutable_json(stage/'paired_reads.json',records)
    with ledger.transaction() as db:
        rows=db.execute('select id,status from calls where id like ?',(run_id+':%',)).fetchall()
    if set(rows)!={(i,'completed') for i in identities} or len(identities)!=binding['paired_calls']:
        raise ValueError('Every paired observation must settle as an actual response')
    path=ROOT/binding['grade_path']
    if sha(path)!=binding['grade_sha256']:
        raise ValueError('Original TRAIN grading changed')
    done={'status':DONE,'scores':score(cases,records,read(path)),'executor_calls':len(identities),
          'executor_tokens':tokens,'teacher_calls':0,'DEV_or_TEST_opened':False}
    immutable_json(stage/'terminal.json',done)
    write_status(stage,{'status':DONE,'physical_reads':len(identities)},POINTER)
    print(json.dumps(done,sort_keys=True),flush=True)


if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('phase',choices=('prepare','run'))
    run(cli.parse_args().phase=='run')
