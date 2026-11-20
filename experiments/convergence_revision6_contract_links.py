"""Fit and reuse the contract interface that cites permission and definition separately."""

import argparse
import json
from pathlib import Path
import re

import jsonschema

from experiments import convergence_revision5_cni_colocated_citation as citations
from experiments import convergence_revision5_cni_linked_evidence as linked
from experiments import convergence_revision6_contract_fit as first
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import relational_program
from legal_skill_guard.paired_interfaces.formal_actors import verify_physical_response
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.paired_interfaces.formal_training import RelationalInterfaceLibrary
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest

HOME = BASE / 'revision6_formal_contract_linked_evidence'
POINTER = HANDOFF / 'revision6_contract_links_current.json'
ROLES = ('fixed','synthesized')


def reader_input(view):
    return {'document':view['public']['source_text'],
            'native_spans':[{'id':i,'text':text} for i,text in enumerate(linked.span_inventory(view))]}


def candidate_view(source):
    native, = (v for v in source['views'] if v['id']==linked.TASK)
    spans = linked.span_inventory(native)
    candidates = []
    for role,asset in zip(ROLES,linked.disclosure.assets(),strict=True):
        _, schema, instructions = linked.plan(asset,spans)
        program = relational_program.sealed({
            'units': {linked.disclosure.UNIT:{'asset':asset,'asset_sha256':digest(asset),
                                            'module_binding':asset['module_binding'],'context':{}}},
            'outputs': {linked.TASK:{'local':[linked.disclosure.UNIT,'classification']}},
        })
        relational_program.verify(program)
        p = {'name':role,'choices':{'cross_clause_recipient_binding':role},
             'is_correct_fixed_raw_control':role=='fixed','reader_kind':'consumer_relational_program',
             'relational_program':program,'schema':schema,'system':instructions,
             'source_public_sha256':digest(source),
             'reader_template_sha256':digest({'asset':digest(asset),'instructions':instructions,
                                              'citation_contract':'original_permission_and_definition_slots'})}
        candidates.append({**p,'version':digest(p)})
    return {'view':'cross_clause_recipient_binding','source':source['key'],'native_tasks':[linked.TASK],
            'plans':candidates,'read_input':reader_input(native),'spans':spans}


class LinkedReader:
    def __init__(self,executor,out,code):
        self.executor, self.out, self.code = executor,out,code

    def channel_version(self,plan):
        return digest({'plan':plan['version'],'code':self.code,'executor':self.executor.config})

    def measure(self,source,view,plan,purpose):
        if (plan not in view['plans'] or source['key']!=view['source']
                or digest(source)!=plan['source_public_sha256']):
            raise ValueError('The recipient reader must bind its original contract and interface')
        messages=[{'role':'system','content':plan['system']},
                  {'role':'user','content':json.dumps(view['read_input'],ensure_ascii=False)}]
        logical=f"{self.executor.ledger.run_id}:{digest(source['key'])}:{plan['name']}"
        task={'source':source['key'],'purpose':purpose,'messages':messages,'schema':plan['schema'],
              'channel_version':self.channel_version(plan)}
        immutable_json(self.out/'wire_tasks'/(digest(logical)+'.json'),task)
        result=self.executor.generate(logical,source=source['key'],purpose=purpose,messages=messages,
                                      schema=plan['schema'],thinking=False)
        physical=result.get('reused_physical_call_id',logical)
        content_sha=digest(result['content'])
        verify_physical_response(self.executor,identity=physical,source=source['key'],purpose=purpose,
            content_sha256=content_sha,usage=result['usage'],finish_reason=result['finish_reason'])
        variant, = plan['relational_program']['units'].values()
        try:
            if result['finish_reason']!='stop':
                raise ValueError('Incomplete response')
            value=json.loads(result['content'])
            jsonschema.validate(value,plan['schema'])
            canonical=citations.canonical_citations(value)
            native=linked.decode((variant['asset'],plan['schema'],plan['system']),view['spans'],
                                 json.dumps(canonical))
        except (ValueError,jsonschema.ValidationError):
            native={'answer':None,'evidence':[],'permission_spans':[],'definition_span':None,'wire_valid':False}
        proof={'source':source['key'],'view':view['view'],'raw_read_version':plan['version'],
               'channel_version':self.channel_version(plan),'physical_call_id':physical,
               'reused_paid_response':physical!=logical,'response_content_sha256':content_sha,
               'response_finish_reason':result['finish_reason'],'usage':result['usage'],'native':native}
        immutable_json(self.out/'measured_reads'/(digest(logical)+'.json'),proof)
        return proof


def fidelity(observation, review):
    stratum, definition, required, allowed = review
    spans = set(observation['permission_spans'])
    grounded = (observation['wire_valid'] and observation['answer']=='Entailment'
                and bool(required) and required<=spans<=allowed and observation['definition_span']==definition)
    return {'all_local_relations_source_faithful':grounded,
            'native_labels_used_to_complete_unknowns':False,
            'reference_evidence_sha256':digest([stratum,definition,sorted(required),sorted(allowed)])}


def native(row):
    return {'answer':row['answer'],'evidence_sentence_ids':row['evidence']}


def direct_source(view):
    """Source-only comparator from the prior reviewed representative-definition forms."""
    spans = [' '.join(s.split()) for s in linked.span_inventory(view)]
    definitions=[i for i,s in enumerate(spans) if linked.DEFINITION.search(s) and EMPLOYEES.search(s)]
    matches=[[i] for i,s in enumerate(spans) if EXPLICIT.search(s)]
    matches += [[i,i+1] for i in range(len(spans)-1)
                if EXCEPTION.search(spans[i]) and AUDIENCE.search(spans[i+1])]
    if len(matches)==len(definitions)==1:
        return {'answer':'Entailment','evidence_sentence_ids':sorted(set(definitions+matches[0]))}
    return None


EMPLOYEES=re.compile(r'\bemployees?\b',re.I)
EXPLICIT=re.compile(r'\bmay\s+(?:reveal|disclose|share)\s+(?:the\s+)?(?:confidential\s+)?'
                    r'information\s+to\s+their\s+representatives\b',re.I)
EXCEPTION=re.compile(r'\brestrictions\b.{0,140}\bdo not apply to the disclosure of '
                     r'(?:confidential|target confidential) information\b',re.I)
AUDIENCE=re.compile(r'^(?:\d+(?:\.\d+)*\.?\s+)?to\s+each party[’\']s\s+(?:respective )?representatives\b',re.I)


def materials():
    binding,cases=linked.materials()
    source_root=ROOT/read(linked.POINTER)['artifact_root']
    old=read(source_root/'terminal.json')
    if (digest(binding)!=source_root.name or binding!=read(source_root/'binding.json')
            or old['status']!=linked.DONE or digest(read(source_root/'cases.json'))!=binding['pair_inputs_sha256']):
        raise ValueError('Use the original source-audited TRAIN pairs')
    checkpoint,study,batches=first.release.cni.base.archive.archive_context()
    cohort,_,study_dev,_=first.release.formal.common.archive()
    if study_dev!=study or digest(study)!=checkpoint.name:
        raise ValueError('Bind the original ordered TRAIN and fixed DEV')
    dev=[s for s in cohort if s['dataset']==linked.DATASET]
    views={'train':{c['source']['key']:candidate_view(c['source']) for c in cases.values()},
           'dev':{s['key']:candidate_view(s) for s in dev if linked.in_cohort(linked.span_inventory(
               next(v for v in s['views'] if v['id']==linked.TASK)))}}
    linked.preflight(linked.disclosure.assets())
    expected={pos for pos,c in cases.items() if direct_source(c['view']) is not None}
    if expected!={pos for pos,review in linked.REVIEWS.items() if review[0]=='linked'}:
        raise ValueError('The matched source comparator must retain its original TRAIN coverage')
    parent,terminal,_=first.release.stage(first.release.POINTER)
    code_files=(Path(__file__).resolve(),Path(linked.__file__),Path(citations.__file__),Path(first.__file__),
                Path(relational_program.__file__))
    spec={'stage':'revision6_contract_M1_linked_scope','executor':binding['executor'],
          'source_sha256':{str(p.relative_to(ROOT)):sha(p) for p in code_files},
          'original_linked_TRAIN_terminal_sha256':sha(source_root/'terminal.json'),
          'paired_TRAIN_read_sha256':sha(source_root/'paired_reads.json'),
          'TRAIN_grading_file':binding['grading_file'],'TRAIN_grade_sha256':binding['grading_file_sha256'],
          'parent_DEV_terminal_sha256':terminal['terminal_sha256'],'views_sha256':digest(views),
          'TRAIN_mothers':len(cases),'DEV_mothers':len(dev),'DEV_eligible':len(views['dev']),'TEST_opened':False}
    return spec,cases,views,source_root,study,batches,dev,parent,terminal


def run(execute=False):
    spec,cases,views,history,study,batches,dev,parent,terminal=materials()
    out=HOME/digest(spec)
    immutable_json(out/'binding.json',spec)
    immutable_json(out/'views.json',views)
    if (out/'terminal.json').exists():
        print(out,flush=True)
        return
    if not execute:
        write_status(out,{'status':'prepared','DEV_eligible':spec['DEV_eligible']},POINTER)
        print(out,flush=True)
        return
    if ROOT/read(POINTER)['artifact_root']!=out:
        raise ValueError('Prepare the same B8 and frozen reader binding first')
    for name,h in spec['source_sha256'].items():
        path=out/'source_snapshot'/name
        path.parent.mkdir(parents=True,exist_ok=True)
        if not path.exists():
            with path.open('xb') as dest:
                dest.write((ROOT/name).read_bytes())
        if sha(path)!=h:
            raise ValueError('Changed implementation after preparation')
    ledger=EvolutionLedger(LEDGER,run_id='revision6-M1-links-'+out.name[:14],
        sources={'train':list(views['train']),'dev':list(views['dev']),'test':[]},binding=spec)
    executor=FrozenExecutor(ledger,out,spec['executor'])
    executor.exact_replay_roots=[history]
    actor=LinkedReader(executor,out,spec['source_sha256'])
    ordered=[s['key'] for batch in batches for s in batch]
    learner=RelationalInterfaceLibrary(out,actor=actor,train_sources=ordered,
                                       initial_common_library_sha256=terminal['terminal_sha256'])
    grade_path=ROOT/spec['TRAIN_grading_file']
    if sha(grade_path)!=spec['TRAIN_grade_sha256'] or 'train' not in grade_path.parts:
        raise ValueError('The archived TRAIN and scorer binding must match')
    grades=read(grade_path)
    previous=read(history/'paired_reads.json')
    review_by_key={c['source']['key']:(pos,c,o) for (pos,c),o in zip(cases.items(),previous,strict=True)}
    old_roles=dict(zip(ROLES,('fixed_coordinates','synthesized_binding'),strict=True))
    prefix=[]
    train_counts={r:{'correct':0,'grounded':0,'physically_reused':0} for r in ROLES}
    for batch,mothers in enumerate(batches,1):
        prefix.extend(s['key'] for s in mothers)
        for source in mothers:
            key=source['key']
            if key not in review_by_key:
                continue
            pos,c,archived=review_by_key[key]
            view=views['train'][key]
            reads=[actor.measure(source,view,p,'skill_actor') for p in view['plans']]
            for plan,row in zip(view['plans'],reads,strict=True):
                role=plan['name']
                if row['physical_call_id']!=archived[old_roles[role]]['physical_call_id']:
                    raise ValueError('The historical matched archive should satisfy the exact TRAIN wire')
                source_check=fidelity(row['native'],linked.REVIEWS[pos])
                score=first.native_score(source,native(row['native']),grades)['grade']
                learner.observe(source,view,plan,row,native_utility=score,source_fidelity=source_check,
                                visible_prefix=prefix)
                train_counts[role]['correct']+=score
                train_counts[role]['grounded']+=source_check['all_local_relations_source_faithful']
                train_counts[role]['physically_reused']+=row['reused_paid_response']
        snapshot=learner.snapshot(batch=batch,visible_prefix=prefix)
        immutable_json(out/'TRAIN_batch_libraries'/f'B{batch}.json',snapshot)
    learner=RelationalInterfaceLibrary.restore(out,actor=actor,train_sources=ordered,
                                                snapshot=read(out/'TRAIN_batch_libraries/B8.json'))
    original=first.release.ReleaseActor(parent,first.release.parent_cells(parent,terminal),{})
    bank={k:{} for k in ('common_program','direct_source','fixed','synthesized','learned')}
    all_native={}
    decisions=[]
    for source in dev:
        key=source['key']
        prior=original.original(first.release.formal.common.ORDINARY,key)['result']['native']
        all_native[key]=prior
        base=prior[linked.TASK]
        target=next(v for v in source['views'] if v['id']==linked.TASK)
        proof=direct_source(target)
        for role in bank:
            bank[role][key]=base if role=='common_program' or not proof else proof
        if key not in views['dev']:
            continue
        view=views['dev'][key]
        plan,choice=learner.choose(source,view)
        selected={'source':key,'TRAIN_library_sha256':snapshot['snapshot_sha256'],'selection':choice}
        immutable_json(out/'pre_read_selections'/(digest(key)+'.json'),selected)
        results={p['name']:actor.measure(source,view,p,'skill_dev') for p in view['plans']}
        for role,row in results.items():
            bank[role][key]=proof or native(row['native'])
        bank['learned'][key]=bank[plan['name']][key]
        decisions.append({**selected,'picked_synthesized':plan['name']=='synthesized',
                          'literal_rule_used':proof is not None,
                          'calls':{role:row['physical_call_id'] for role,row in results.items()}})
        write_status(out,{'status':'running','completed_mothers':len(decisions)},POINTER)
    prediction_sha=immutable_json(out/'sealed_predictions.json',{
        role:{key:{**all_native[key],linked.TASK:value} for key,value in rows.items()} for role,rows in bank.items()})
    grade_rel=study['grading_paths'][linked.DATASET]
    if sha(ROOT/grade_rel)!=study['grading_file_sha256'][grade_rel] or 'dev' not in Path(grade_rel).parts:
        raise ValueError('Use the original DEV annotation binding')
    labels=read(ROOT/grade_rel)
    with ledger.transaction() as db:
        physical=dict(db.execute('select status,count(*) from calls where id like ? group by status',(ledger.run_id+':%',)))
    if physical.get('reserved'):
        raise ValueError('Reconcile pending response before grading')
    result=sealed({'status':'settled_revision6_contract_M1_linked_scope','binding_sha256':out.name,
                   'TEST_opened':False,'TRAIN':train_counts,'DEV_eligible':spec['DEV_eligible'],
                   'DEV_participating_scores':first.compare([s for s in dev if s['key'] in views['dev']],bank,labels),
                   'DEV_all_scores':first.compare(dev,bank,labels),'pre_read_selected_pairs':decisions,
                   'predictions_sha256':prediction_sha,'new_physical':physical},'terminal_sha256')
    immutable_json(out/'terminal.json',result)
    write_status(out,{'status':result['status'],'terminal_sha256':result['terminal_sha256']},POINTER)
    print(out,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=('prepare','run'))
    run(parser.parse_args().phase=='run')
