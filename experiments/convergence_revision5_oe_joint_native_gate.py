"""Recheck the B7 OpenExempt update with shared eligibility across its native queries."""

import argparse
from itertools import product
import json
from pathlib import Path
import sqlite3
from statistics import mean

from experiments.convergence_formal_b1_observe import load_roster
from experiments.convergence_formal_train_fit import M2, OE, ORDINARY, _group, _group_digest, _validate_relation, pointer
from experiments.convergence_oe_scoped_proposal import OWNERSHIP_FIELD, scoped_program
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.openexempt import UPSTREAM
from legal_skill_guard.paired_interfaces.convergence_ev_inventory import public_inventory
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.paired_interfaces.convergence_oe_public_scope import supplied_jurisdiction_scope
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE/'revision5_OE_joint_native_gate_20261119'
POINTER = HANDOFF/'revision5_OE_joint_native_gate_current.json'
DONE = 'completed_revision5_OE_joint_native_gate_TRAIN'
MODES = ('shared','independent','direct_implication')
# EC reports the latent admissibility of a citation. A positive EV allocation
# additionally requires a positive allocatable amount. Either observed port can be absent.
SHARED = frozenset((eligible,eligible and value) for eligible,value in product((False,True),repeat=2))
INDEPENDENT = frozenset(product((False,True),repeat=2))


def support(ec,ev,mode):
    if mode=='direct_implication':
        return not (ec is False and ev is True)
    table = SHARED if mode=='shared' else INDEPENDENT
    return any((ec is None or ec==p) and (ev is None or ev==v) for p,v in table)


def slot_records(source, incumbent, candidate):
    public = {v['id']:v['public']['original_input'] for v in source['views']}
    inventory = {v:{p['description']:p['amount_quote'] for p in public_inventory(text).values()}
                 for v,text in public.items()}
    scopes={v:supplied_jurisdiction_scope(text) for v,text in public.items()}
    if (inventory['EC']!=inventory['EV'] or not scopes['EC'] or scopes['EC']!=scopes['EV']
            or source['project_split']!='train'):
        raise ValueError('Both native tasks must bind the same case, asset values and public citations')
    lawful = set(scopes['EC']['citations'])
    native={role:r['native'] for role,r in (('incumbent',incumbent),('candidate',candidate))}
    if any(not data[v]['handled'] for data in native.values() for v in ('EC','EV')):
        return []
    named=set(inventory['EC'])
    for data in native.values():
        for v in ('EC','EV'):
            named &= data[v]['answer'].keys()
    ec_map={role:data['EC']['answer'] for role,data in native.items()}
    positives={role:{(a,c['citation']) for a in named for c in data['EV']['answer'][a]
                     if c['claim_value']>0 and c['citation'] in lawful} for role,data in native.items()}
    union=positives['incumbent']|positives['candidate']
    return [{'asset':asset,'citation':citation,
             'ports':{role:[citation in ec_map[role][asset],True if (asset,citation) in observed else None]
                      for role,observed in positives.items()}} for asset,citation in sorted(union)]


def physical_native(db,source,row):
    ids=[]
    for readout in row['reads']:
        native, = readout['native'].values()
        assert native['handled'] and not native['fallback_executed']
        trace, = (t for t in readout['execution']['traces'] if 'physical_call_id' in t)
        identity = trace['physical_call_id']
        role,status,root,purpose,body=db.execute(
            'select role,status,source,purpose,result from calls where id=?',(identity,)).fetchone()
        if (role,status,root,purpose)!=('executor','completed',source,'skill_actor'):
            raise ValueError('The native comparison needs a settled exact executor response')
        raw=json.loads(body)
        assert raw['content']==trace['raw_content'] and raw['finish_reason']=='stop'
        ids.append(identity)
    if len(ids)!=2:
        raise ValueError('The complete original EC and EV outputs must remain')
    return ids


def compare_slots(rows):
    stats={role:{'positive':0,'shared_conflicts':0,'independent_conflicts':0,'direct_implication_conflicts':0}
           for role in ('incumbent','candidate')}
    for row in rows:
        for role,(ec,ev) in row['ports'].items():
            stat=stats[role]
            stat['positive']+=ev is True
            for mode in MODES:
                stat[mode+'_conflicts']+=not support(ec,ev,mode)
    return stats


def materials():
    if any(support(a,b,'shared')!=support(a,b,'direct_implication')
           for a,b in product((True,False,None),repeat=2)):
        raise ValueError('Preserve the matched public implication control including missing fields')
    fit=ROOT/read(pointer(7))['artifact_root']
    bound=read(fit/'binding.json')
    terminal=read(fit/'terminal.json')
    frozen_comparisons=read(fit/'matched_decisions.json')
    if (fit.name!=digest(bound) or terminal['TEST_opened'] or terminal['batch']!=7
            or digest(frozen_comparisons)!=terminal['matched_decisions_sha256']):
        raise ValueError('Use the unchanged B7 TRAIN proposals')
    archive=read(fit/'source_snapshot_receipt.json')
    assert archive['files']==bound['source_sha256']
    assert all(sha(fit/'source_snapshot'/p)==v for p,v in archive['files'].items())
    sealed=frozen_comparisons['relation'][OE]
    previous=read(HANDOFF/'B7_OE_shared_selection_audit_20261119.json')
    observed=previous['literal']['explanation_state']['observations']
    original_literal,=observed
    assert previous['binding']==fit.name and previous['reproduced_update_status']=='insufficient_positive_supervision'
    assert len(original_literal['actual_signature'])==2
    assert all(p=={'ownership':None,'stated_value':None} for p in original_literal['actual_signature'])
    root=ROOT/bound['checkpoint_root']
    study=read(root/'binding.json')
    batches=load_roster(study)
    journal=TrainingJournal(root,study,batches)
    visible=[s for b in batches[:7] for s in b]
    keys=[s['key'] for s in visible]
    cohort=[s for s in batches[6] if s['dataset']==OE]
    assert len(cohort)==4
    patch_dir=fit/'candidates'/ORDINARY/OE
    proposal=read(patch_dir/'measurements.json')
    decision=read(patch_dir/'decision.json')
    candidate=proposal['candidate']
    incumbent=journal.library(M2,6)['programs'][OE]
    assert digest(proposal['predictions'])==decision['predictions_sha256']
    assert digest(candidate)==previous['candidate_sha256']==sealed['matched_proposal_sha256']
    assert digest(incumbent)==previous['incumbent_sha256']
    native_receipt=journal._observations(M2,7)
    witness=[]
    physical=[]
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        status,role,doc=db.execute('select status,role,result from calls where id=?',(decision['teacher_call'],)).fetchone()
        assert (status,role)==('completed','teacher')
        literal_program=scoped_program(json.loads(doc)['value'],keys,literal_wire=True)
        native_program={k:v for k,v in literal_program.items() if k!=OWNERSHIP_FIELD}
        assert native_program==candidate and OWNERSHIP_FIELD not in candidate
        for source in cohort:
            key=source['key']
            saved=read(journal.directory(M2,7)/'predictions'/(digest(key)+'.json'))
            assert digest(saved)==native_receipt['predictions'][key]
            first= saved['result']
            second=proposal['predictions'][key]
            physical.extend(physical_native(db,key,first))
            physical.extend(physical_native(db,key,second))
            witness.extend({**row,'source':key} for row in slot_records(source,first,second))
        for identity in original_literal['physical_call_ids']:
            status,role,doc=db.execute('select status,role,result from calls where id=?',(identity,)).fetchone()
            assert (status,role)==('completed','executor')
            assert json.loads(json.loads(doc)['content'])=={'ownership':None,'stated_value':None}
    assert len(physical)==16
    stats=compare_slots(witness)
    assert stats['incumbent']['positive']==stats['candidate']['positive']==10
    assert stats['incumbent']['shared_conflicts']==0 and stats['candidate']['shared_conflicts']==2
    assert all(r['shared_conflicts']==r['direct_implication_conflicts'] and not r['independent_conflicts']
               for r in stats.values())
    group,_=_group(visible)
    assert _group_digest(group)==bound['natural_group_public_sha256']
    assert [c.source_id for c in group['cases']]==original_literal['source_ids']
    pos=sealed['native_comparisons']
    assert pos==previous['native_pairs'] and mean(r['patch_utility']-r['baseline_utility'] for r in pos)>0
    files={*bound['source_sha256'],'legal_skill_guard/openexempt.py',
           str(Path(__file__).resolve().relative_to(ROOT)),
           str((UPSTREAM/'source/solver.py').relative_to(ROOT)),
           str((UPSTREAM/'source/task_generator.py').relative_to(ROOT))}
    spec={'study':'revision5_OE_B7_two_native_queries_shared_eligibility',
          'TRAIN_batch':7,'prior_fit_terminal_sha256':sha(fit/'terminal.json'),
          'literal_group_sha256':bound['natural_group_public_sha256'],
          'literal_program_sha256':digest(literal_program),'literal_policy_semantically_same_as_verified_teacher':True,
          'candidate_sha256':digest(candidate),'incumbent_sha256':digest(incumbent),
          'physical_native_evidence_sha256':digest(physical),'paired_slots_sha256':digest(witness),
          'native_pair_sha256':digest(pos),'native_utility_delta':mean(r['patch_utility']-r['baseline_utility'] for r in pos),
          'relational_summary':stats,'executor':bound['executor'],'planned_literal_requests':2,
          'source_sha256':{p:sha(ROOT/p) for p in sorted(files)},'TEST_and_DEV_opened':False}
    return spec,group,keys,literal_program,pos,witness


def run(execute):
    if POINTER.exists() and read(POINTER)['status']==DONE:
        print(read(POINTER)['artifact_root'],flush=True)
        return
    spec,group,keys,program,pos,witness=materials()
    stage=HOME/digest(spec)
    if execute and (not POINTER.exists() or ROOT/read(POINTER)['artifact_root']!=stage):
        raise ValueError('Use the prepared comparison')
    immutable_json(stage/'binding.json',spec)
    immutable_json(stage/'matched_native_slots.json',witness)
    if not execute:
        if POINTER.exists() and read(POINTER)['status']=='running':
            raise ValueError('Preserve the active comparison')
        write_status(stage,{'status':'prepared','planned_literal_calls':2},POINTER)
        print(json.dumps({'stage':str(stage.relative_to(ROOT)),'relation':spec['relational_summary']}),flush=True)
        return
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        if db.execute("select 1 from calls where status='reserved'").fetchone():
            raise ValueError('Reconcile the in-flight request before dispatching')
    for name,expected in spec['source_sha256'].items():
        target=stage/'source_snapshot'/name
        target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists():
            with target.open('xb') as f:
                f.write((ROOT/name).read_bytes())
        assert sha(target)==expected
    key,={c.root_id for c in group['cases']}
    ledger=EvolutionLedger(LEDGER,run_id='convergence-revision5-OE-B7-cross-view-'+stage.name[:16],
                            sources={'train':[key],'dev':[],'test':[]},binding=spec)
    executor=FrozenExecutor(ledger,stage,spec['executor'])
    executor.readiness()
    write_status(stage,{'status':'running','step':'candidate_literal'},POINTER)
    literal=_validate_relation(executor,stage,program,group,keys,pos)
    literal_ok=literal['status']=='eligible_train_update'
    stats=spec['relational_summary']
    choices={'native_only':'candidate','literal_only':'candidate' if literal_ok else 'incumbent'}
    for mode in MODES:
        n=mode+'_conflicts'
        compatible_incumbent=stats['incumbent'][n]==0
        reject=stats['candidate'][n]>0 and compatible_incumbent
        choices[mode]='candidate' if literal_ok and not reject else 'incumbent'
    with ledger.transaction() as db:
        calls=db.execute('select status,result from calls where id like ?',(ledger.run_id+':%',)).fetchall()
    assert len(calls)==2 and all(s=='completed' for s,_ in calls)
    t={'status':DONE,'literal_recheck':literal,'choices':choices,
       'relational_summary':stats,'physical_executor_calls':len(calls),
       'executor_tokens':sum(json.loads(v)['usage']['total_tokens'] for _,v in calls),
       'native_executor_calls':0,'teacher_calls':0,'TRAIN_only':True}
    immutable_json(stage/'terminal.json',t)
    write_status(stage,{'status':DONE,'executor_calls':len(calls)},POINTER)
    print(json.dumps({'choices':choices,'literal_status':literal['status'],'tokens':t['executor_tokens']}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=('prepare','run'))
    run(parser.parse_args().phase=='run')
