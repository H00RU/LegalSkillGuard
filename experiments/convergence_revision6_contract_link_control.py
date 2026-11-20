"""Compare the locked linked interface with direct reading on the identical contract view."""

import argparse
import json
from pathlib import Path

import jsonschema

from experiments import convergence_revision6_contract_links as linked
from experiments.convergence_pilot_b0 import BASE,HANDOFF,LEDGER,ROOT,read,sha,write_status
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.formal_actors import verify_physical_response
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed,verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest

HOME=BASE/'revision6_contract_same_input_direct'
POINTER=HANDOFF/'revision6_contract_same_input_direct_current.json'
CONTROL=(
    'Decide whether the receiving party may share this confidential information with at least some of '
    'its own employees. Use Entailment if there is such permission, including permission restricted to '
    'need-to-know disclosure. Use Contradiction for an explicit prohibition of all such sharing. When the '
    'document establishes neither conclusion, use NotMentioned. Use null when you cannot read a '
    'source-grounded result. Use the same permission and definition span slots for your own native decision.'
)


def request(view):
    plan=view['plans'][0]
    schema={**plan['schema'],'properties':{**plan['schema']['properties']}}
    schema['properties']['classification']={'enum':['Entailment','Contradiction','NotMentioned',None]}
    del schema['properties']['relations']
    schema['required']=['classification' if f=='relations' else f for f in schema['required']]
    return [{'role':'system','content':linked.linked.COMMON+'\n'+CONTROL},
            {'role':'user','content':json.dumps(view['read_input'],ensure_ascii=False)}],schema


def decode(view, schema, response):
    try:
        if response['finish_reason']!='stop':
            raise ValueError('A partial prediction cannot enter the native comparison')
        value=json.loads(response['content'])
        jsonschema.validate(value,schema)
        row=linked.citations.canonical_citations(value)
        state=row['classification']
        permission=row['permission_spans']
        evidence=permission+([row['definition_span']] if row['definition_span'] is not None else [])
        if state in ('Entailment','Contradiction') and (
                not permission or any(not view['spans'][i].strip() for i in evidence)):
            raise ValueError('An operative answer requires original native evidence')
        return {'answer':state,'evidence_sentence_ids':sorted(evidence) if state in (
            'Entailment','Contradiction') else []}
    except (ValueError,jsonschema.ValidationError):
        return {'answer':None,'evidence_sentence_ids':[]}


def materials():
    parent=ROOT/read(linked.POINTER)['artifact_root']
    spec=read(parent/'binding.json')
    terminal=verify(read(parent/'terminal.json'),'terminal_sha256')
    if (parent.name!=digest(spec) or parent.name!=terminal['binding_sha256'] or terminal['TEST_opened']
            or sha(parent/'sealed_predictions.json')!=terminal['predictions_sha256']):
        raise ValueError('Use the settled relation path before fixing the direct control')
    views=read(parent/'views.json')
    if digest(views)!=spec['views_sha256']:
        raise ValueError('Use the identical source and span inventory')
    dev=views['dev']
    wires={k:request(v) for k,v in dev.items()}
    latest,old,study,_=linked.first.release.formal.common.archive()
    cohort=[s for s in latest if s['key'] in dev]
    if len(dev)!=len(cohort) or len(dev)!=terminal['DEV_eligible']:
        raise ValueError('Direct control must cover every predeclared in-scope mother')
    binding={'stage':'revision6_contract_same_input_direct','M1_terminal_sha256':terminal['terminal_sha256'],
             'public_cohort_sha256':digest(cohort),'exact_direct_wire_sha256':digest(wires),
             'executor':spec['executor'],'eligible_DEV':len(dev),'TEST_opened':False,
             'source_sha256':{str(p.relative_to(ROOT)):sha(p) for p in (
                 Path(__file__).resolve(),Path(linked.__file__),Path(linked.linked.__file__))}}
    return binding,cohort,dev,wires,study,parent,terminal


def run(execute=False):
    binding,cohort,views,wires,study,parent,terminal=materials()
    out=HOME/digest(binding)
    immutable_json(out/'binding.json',binding)
    if (out/'terminal.json').exists():
        print(out,flush=True)
        return
    if not execute:
        write_status(out,{'status':'prepared','planned_DEV_calls':len(cohort)},POINTER)
        print(out,flush=True)
        return
    if ROOT/read(POINTER)['artifact_root']!=out:
        raise ValueError('Prepare exact direct comparison before dispatch')
    for name,expected in binding['source_sha256'].items():
        snapshot=out/'source_snapshot'/name
        snapshot.parent.mkdir(parents=True,exist_ok=True)
        if not snapshot.exists():
            with snapshot.open('xb') as f:
                f.write((ROOT/name).read_bytes())
        if sha(snapshot)!=expected:
            raise ValueError('The bounded implementation changed')
    ledger=EvolutionLedger(LEDGER,run_id='revision6-M1-direct-'+out.name[:12],
        sources={'train':[],'dev':list(views),'test':[]},binding=binding)
    reader=FrozenExecutor(ledger,out,binding['executor'])
    outputs={}
    for source in cohort:
        key=source['key']
        messages,schema=wires[key]
        logical=f'{ledger.run_id}:{digest(key)}'
        response=reader.generate(logical,source=key,purpose='skill_dev',messages=messages,
                                 schema=schema,thinking=False)
        physical=response.get('reused_physical_call_id',logical)
        verify_physical_response(reader,identity=physical,source=key,purpose='skill_dev',
          content_sha256=digest(response['content']),usage=response['usage'],finish_reason=response['finish_reason'])
        target=next(v for v in source['views'] if v['id']==linked.linked.TASK)
        outputs[key]=linked.direct_source(target) or decode(views[key],schema,response)
        immutable_json(out/'physical_reads'/f'{digest(key)}.json',{'call_id':physical,'output':outputs[key]})
        write_status(out,{'status':'running','completed_DEV':len(outputs)},POINTER)
    pred_hash=immutable_json(out/'direct_predictions.json',outputs)
    source_bank=read(parent/'sealed_predictions.json')
    task=linked.linked.TASK
    bank={role:{k:values[k][task] for k in views} for role,values in source_bank.items()}
    bank['direct_same_input']=outputs
    grade=study['grading_paths'][linked.linked.DATASET]
    if sha(ROOT/grade)!=study['grading_file_sha256'][grade] or 'dev' not in Path(grade).parts:
        raise ValueError('Use the declared native DEV grading file')
    labels=read(ROOT/grade)
    scores=linked.first.compare(cohort,bank,labels)
    differences={}
    for arm in ('common_program','direct_same_input'):
        a,b=({s['key']:linked.first.native_score(s,bank[role][s['key']],labels) for s in cohort}
             for role in (arm,'learned'))
        for metric in ('grade','evidence_f1'):
            rows=tuple([{'source':k,'view':task,'grade':x[metric]} for k,x in values.items()] for values in (a,b))
            differences[f'{arm}_{metric}']=paired_source_effect(*rows)
    with ledger.transaction() as db:
        counts=dict(db.execute('select status,count(*) from calls where id like ? group by status',(ledger.run_id+':%',)))
    if counts!={'completed':len(cohort)}:
        raise ValueError('This control requires actual paired development responses')
    result=sealed({'status':'settled_revision6_contract_same_input_direct','binding_sha256':out.name,
        'prediction_sha256':pred_hash,'scores':scores,'learned_differences':differences,
        'physical_requests':counts['completed'],'TEST_opened':False},'terminal_sha256')
    immutable_json(out/'terminal.json',result)
    write_status(out,{'status':result['status'],'terminal_sha256':result['terminal_sha256']},POINTER)
    print(out,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=('prepare','run'))
    run(parser.parse_args().phase=='run')
