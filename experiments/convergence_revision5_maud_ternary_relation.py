"""Compare an equivalent nullable MAUD inquiry relation with the two settled readers."""

import argparse
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path
import sqlite3

from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision5_maud_definition_scope import DONE as PARENT_DONE, POINTER as PARENT
from legal_skill_guard.paired_interfaces import indexed_relational_read as indexed
from legal_skill_guard.paired_interfaces import maud_knowledge_relational as knowledge
from legal_skill_guard.paired_interfaces import relational_program, residual
from legal_skill_guard.paired_interfaces.formal_actors import InterfaceActor
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE/'revision5_MAUD_ternary_relation_20261119'
POINTER = HANDOFF/'revision5_MAUD_ternary_relation_current.json'
DONE = 'completed_revision5_MAUD_ternary_relation_TRAIN'
LOCAL = 'operative_knowledge_definition'


def equality(left,right):
    return {'op':'eq','args':[left,right]}


@lru_cache(maxsize=1)
def equivalent_asset():
    model = knowledge.module()
    fixed, compiled = knowledge.assets()
    dependencies = {'qualification_target','inquiry_effect'}
    conjunction, = (feature for feature in compiled['features']
                    if feature.get('expression',{}).get('op')=='and'
                    and set(feature['consumer_dependencies'])==dependencies)
    actual, = (f for f in compiled['features'] if f['operation']=='field')
    if actual['field']!='explicit_actual_restriction':
        raise ValueError('Preserve the original actual-knowledge coordinate')
    # Ordinary three-valued AND can return false when either dependency is unknown.
    # Equality with this tri-valued test preserves that unknown dependency.
    fields = [{'op':'field','field':v} for v in sorted(dependencies)]
    both_known = equality(*(equality(field,field) for field in fields))
    strict = equality(conjunction['expression'],both_known)
    inquiry = {'name':'operative_inquiry','operation':'relation','expression':strict,
               'consumer_dependencies':sorted(dependencies)}
    if residual.witness(model,[conjunction,actual]) is None:
        raise ValueError('Verify the failed simpler projection before changing the representation')
    asset = residual.compile_pair(model,[inquiry,actual],operation='nullable_same_definition_inquiry',
                                  layout=compiled['layout'])
    for state in model.states:
        left = state['qualification_target']
        right = state['inquiry_effect']
        truth = None if None in (left,right) else left=='target_definition' and right=='required'
        values = residual.encode(asset['features'],state)
        if values['operative_inquiry'] is not truth:
            raise ValueError('The wording must match every compiled inquiry state')
        for ctx in model.contexts:
            readout = residual.decode(asset,values,ctx,module_binding=model.binding)
            for original in (fixed,compiled):
                baseline = residual.decode(original,residual.encode(original['features'],state),ctx,
                                           module_binding=model.binding)
                if readout!=baseline:
                    raise ValueError('The compiled reader must preserve every original finite consumer output')
    return asset


def plan_for(view,prior):
    planned = {k:deepcopy(v) for k,v in prior.items() if k!='version'}
    asset = equivalent_asset()
    program = planned['relational_program']
    unit = program['units'][LOCAL]
    unit.update(asset=asset,asset_sha256=digest(asset),template_key='knowledge_scope:'+asset['version'])
    program = relational_program.sealed({k:v for k,v in program.items() if k!='program_sha256'})
    binding = indexed.bind(program,view['relational_public_source'])
    old_instructions = prior['system']
    focus = '\nThe indexed evidence contains the complete observed sentence or fragment'
    if focus not in old_instructions or binding!=prior['indexed_evidence_binding']:
        raise ValueError('Keep the original exact public definition scope')
    _,suffix = old_instructions.split(focus,1)
    common = '\n'.join(old_instructions.splitlines()[:6])
    actual = asset['source_scope']['field_meanings']['explicit_actual_restriction']
    system = (common + '\nLocal unit: ' + asset['source_scope']['local_unit'] + '\n'
              + LOCAL + ' value order:\n'
              'operative_inquiry: true, false, ?\nexplicit_actual_restriction: true, false, ?\n'
              'For operative_inquiry, return true if a required inquiry attaches to the target '
              'definition. Return false if the attachment and force of any inquiry can both be '
              'determined and the target definition has no required inquiry. A closed definition '
              'with no inquiry wording can be read as false. Return ? if the attachment or force '
              'cannot be determined. For explicit_actual_restriction, read ' + actual + '.'
              + focus + suffix)
    planned.update(name='knowledge_scope_nullable_indexed',relational_program=program,
                   indexed_evidence_binding=binding,schema=indexed.reader_schema(program,binding,factorized=True),
                   system=system,choices={'knowledge_scope':2})
    planned['reader_template_sha256'] = relational_program.template_version(
        program,system=system,public_rules='same-definition anchor',
        protocol='maud_same_definition_nullable_inquiry_v1')
    planned['version'] = digest(planned)
    return planned


def materials():
    previous = ROOT/read(PARENT)['artifact_root']
    base = read(previous/'binding.json')
    prior_state = read(previous/'terminal.json')
    prior_cases = read(previous/'cases.json')
    if (base['TEST_and_DEV_opened'] or prior_state['status']!=PARENT_DONE
            or previous.name!=digest(base) or digest(prior_cases)!=base['cases_sha256']):
        raise ValueError('Use the prior exact matched TRAIN scope')
    if any(sha(previous/'source_snapshot'/p)!=v for p,v in base['source_sha256'].items()):
        raise ValueError('The original physical comparison source snapshot changed')
    cases=[]
    for case in prior_cases:
        if case['source']['project_split']!='train':
            raise ValueError('Use original TRAIN only')
        original = case['view']
        plan = plan_for(original,original['plans'][1])
        cases.append({**case,'view':{**original,'plans':[plan]}})
    path = str(Path(__file__).resolve().relative_to(ROOT))
    source_paths = {*base['source_sha256'],path}
    proof = equivalent_asset()['certificate']
    spec = {'study':'revision5_MAUD_certified_nullable_same_definition_inquiry',
            'previous_binding':previous.name,'previous_terminal_sha256':sha(previous/'terminal.json'),
            'previous_raw_results_sha256':sha(previous/'native_reads.json'),
            'cases_sha256':digest(cases),'executor':base['executor'],
            'TRAIN_grade_path':base['TRAIN_grade_path'],'TRAIN_grade_sha256':base['TRAIN_grade_sha256'],
            'proof_states':proof['states'],'same_public_input_as_both_original_readers':True,
            'previous_measured_read_fields':4,'candidate_read_fields':2,'TRAIN_mothers':len(cases),
            'source_sha256':{name:sha(ROOT/name) for name in sorted(source_paths)},'TEST_and_DEV_opened':False}
    return spec,cases


def run(execute):
    if POINTER.exists() and read(POINTER)['status']==DONE:
        print(read(POINTER)['artifact_root'],flush=True)
        return
    spec,cases = materials()
    stage = HOME/digest(spec)
    if execute and (not POINTER.exists() or ROOT/read(POINTER)['artifact_root']!=stage):
        raise ValueError('Execute only the prepared comparison')
    immutable_json(stage/'binding.json',spec)
    immutable_json(stage/'cases.json',cases)
    if not execute:
        if POINTER.exists() and read(POINTER)['status']=='running':
            raise ValueError('Preserve the active run')
        write_status(stage,{'status':'prepared','planned_executor_calls':len(cases)},POINTER)
        print(json.dumps({'stage':str(stage.relative_to(ROOT)),'proof_states':spec['proof_states'],
                          'TRAIN_mothers':len(cases)}),flush=True)
        return
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        if db.execute("select 1 from calls where status='reserved'").fetchone():
            raise ValueError('Reconcile the previous physical task')
    for name,expected in spec['source_sha256'].items():
        target = stage/'source_snapshot'/name
        target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists():
            with target.open('xb') as f:
                f.write((ROOT/name).read_bytes())
        if sha(target)!=expected:
            raise ValueError('Preserve the exact new and reused bindings')
    run_id = 'convergence-revision5-MAUD-ternary-'+stage.name[:16]
    ledger = EvolutionLedger(LEDGER,run_id=run_id,sources={'train':[c['source']['key'] for c in cases],
                             'dev':[],'test':[]},binding=spec)
    executor = FrozenExecutor(ledger,stage,spec['executor'])
    executor.readiness()
    actor = InterfaceActor(executor,stage,plan_assets={},source_inputs=None,pipeline_binding=spec['source_sha256'])
    write_status(stage,{'status':'running','finished_mothers':0},POINTER)
    rows=[]
    for i,case in enumerate(cases,1):
        plan, = case['view']['plans']
        rows.append(actor.measure(case['source'],case['view'],plan,'skill_actor'))
        write_status(stage,{'status':'running','finished_mothers':i},POINTER)
    immutable_json(stage/'native_reads.json',rows)
    path = ROOT/spec['TRAIN_grade_path']
    if sha(path)!=spec['TRAIN_grade_sha256']:
        raise ValueError('Use the exact previously declared TRAIN grader')
    grades=read(path)
    outcomes=[]
    for case,row in zip(cases,rows,strict=True):
        task, = case['source']['views']
        answer=row['native'][task['id']]['answer']
        outcomes.append({'family':case['family'],'original_pilot':case['original_pilot'],
                         'correct':bool(grade_view('MAUD',task,grades[case['source']['key']][task['id']],answer)['grade']),
                         'agrees_with_source_review':answer==case['reference'],'unresolved':answer is None})
    with ledger.transaction() as db:
        calls=db.execute('select status,result from calls where id like ?', (run_id+':%',)).fetchall()
    if len(calls)!=len(cases) or any(s!='completed' for s,_ in calls):
        raise ValueError('Need one actual paired candidate response per TRAIN mother')
    t={'status':DONE,'outcomes':outcomes,'executor_calls':len(calls),
       'executor_tokens':sum(json.loads(raw)['usage']['total_tokens'] for _,raw in calls),
       'teacher_calls':0,'TRAIN_only':True}
    immutable_json(stage/'terminal.json',t)
    write_status(stage,{'status':DONE,'executor_calls':len(calls)},POINTER)
    print(json.dumps(t,sort_keys=True),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=('prepare','run'))
    run(parser.parse_args().phase=='run')
