"""Test a common source-amount correction on archived OpenExempt EV outputs."""

from collections import Counter
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import sqlite3

from experiments.convergence_formal_b1_observe import POINTER as FIRST, load_roster
from experiments.convergence_formal_bootstrap import POINTER as BOOTSTRAP
from experiments.convergence_formal_curves import pointer as dev_pointer
from experiments.convergence_formal_train_fit import EXTERNAL_ARM, ORDINARY
from experiments.convergence_formal_train_observe import pointer as observe_pointer
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha
from experiments.convergence_revision5_cni_nonsolicitation import bound_stage
from experiments.convergence_revision5_cni_oral_dev import verify_wire
from experiments.convergence_revision5_m2_cumulative_audit import physical_wire
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.convergence_ev_inventory import public_inventory
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.paired_interfaces.convergence_oe_public_scope import supplied_jurisdiction_scope
from legal_skill_guard.paired_interfaces.formal_evaluation import verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


OE = 'OpenExempt'
ARMS = (ORDINARY,EXTERNAL_ARM)
HOME = BASE / 'revision5_OE_native_amount_bound_20261119'


def amount_guard(public):
    text = public['original_input']
    inventory = public_inventory(text)
    scope = supplied_jurisdiction_scope(text)
    if inventory is None or scope is None:
        return None
    amounts = {item['description']:Decimal(item['amount_quote'][1:].replace(',','')) for item in inventory.values()}
    if len(amounts)!=len(inventory):
        return None
    return amounts,set(scope['citations'])


def clip_claims(answer, guard):
    """Leave eligibility and in-bound amounts with the measured reader."""
    if guard is None or not isinstance(answer,dict):
        return answer,0
    amounts,laws = guard
    new = deepcopy(answer)
    changed=0
    for asset,claims in new.items():
        if asset not in amounts:
            continue
        counts = Counter(c['citation'] for c in claims)
        for claim in claims:
            citation = claim['citation']
            if citation not in laws or counts[citation]!=1:
                continue
            value = Decimal(str(claim['claim_value']))
            bound = amounts[asset]
            if value.is_finite() and value>bound:
                claim['claim_value'] = float(bound)
                changed += 1
    return new,changed


def ev_view(source):
    view, = (v for v in source['views'] if v['id']=='EV')
    return view


def split_view(saved):
    result = saved['result']
    field='schema_reads' if 'schema_reads' in result else 'reads'
    row, = (r for r in result[field] if set(r['native'])=={'EV'})
    assert row['native']['EV']==result['native']['EV']
    return {field:[row],'native':row['native']}


def read_ev(db, source, data, paid, partition):
    result=split_view(data)
    key=source['key']
    if 'schema_reads' in result:
        trace,=result['schema_reads']
    else:
        call,=result['reads']
        trace,=(r for r in call['execution']['traces'] if 'physical_call_id' in r)
    identity=trace['physical_call_id']
    if partition=='dev':
        wire = verify_wire(db,key,result,paid)
        assert wire==result['native']
    else:
        physical_wire(db,{key},identity,key)
        paid.add(identity)
    actual=json.loads(db.execute('select result from calls where id=?',(identity,)).fetchone()[0])
    if 'schema_reads' in result:
        assert digest(actual['content'])==trace['response_sha256']
    else:
        assert actual['content']==trace['raw_content']
    payload=read(Path(actual['artifact_directory'])/'request.json')['payload']
    user,=(r['content'] for r in payload['messages'] if r['role']=='user')
    text=ev_view(source)['public']['original_input']
    assert any(json.dumps(text,ensure_ascii=flag) in user for flag in (True,False))
    return result['native']['EV']


def all_scores(bank,sources,annotations):
    out={}
    for arm,rows in bank.items():
        values={mode:[] for mode in ('original','asset_bound')}
        counted=Counter()
        for key,row in rows.items():
            if not row['handled']:
                continue
            view=ev_view(sources[key])
            direct={mode:grade_view(OE,view,annotations[key]['EV'],row[mode])['grade'] for mode in values}
            if any(value is None for value in direct.values()):
                counted['unscored_mothers']+=1
                continue
            for mode,value in direct.items():
                values[mode].append({'source':key,'view':'EV','grade':value})
            a,b=direct.values()
            counted['higher' if b>a else 'lower' if b<a else 'same']+=1
        out[arm]={'mothers':len(rows),'common_scorable':len(values['original']),
                  'handled':sum(row['handled'] for row in rows.values()),
                  'projected_claims':sum(row['claims_changed'] for row in rows.values()),
                  'counts':dict(counted),'paired_effect':paired_source_effect(values['original'],values['asset_bound']),
                  'F1':{mode:sum(r['grade'] for r in entries)/len(entries) for mode,entries in values.items()}}
    return out


def score_partition(partition):
    root=ROOT/read(BOOTSTRAP)['artifact_root']; study=read(root/'binding.json')
    assert root.name==digest(study)
    roster=load_roster(study)
    journal=TrainingJournal(root,study,roster)
    data={arm:{} for arm in ARMS}
    receipts=[]; grade_refs=set()
    if partition=='train':
        sources={src['key']:src for batch in roster for src in batch if src['dataset']==OE}
        for n,batch in enumerate(roster,1):
            stage,obs,end=bound_stage(FIRST if n==1 else observe_pointer(n))
            grade=obs['native_grade_paths'][OE]
            grade_refs.add((grade,obs['native_grade_sha256'][grade]))
            receipts.append(sha(stage/'terminal.json'))
            for arm in ARMS:
                locked=journal._observations(arm,n)
                assert locked['train_observation_sha256']==end['observation_receipts'][arm]
                for source in (s for s in batch if s['dataset']==OE):
                    key=source['key']
                    saved=read(journal.directory(arm,n)/'predictions'/(digest(key)+'.json'))
                    assert digest(saved)==locked['predictions'][key]
                    data[arm][key]=saved
    else:
        stage,obs,end=bound_stage(dev_pointer(8))
        assert obs['checkpoint_binding_sha256']==digest(study)
        boot=ROOT/obs['b0_dev_data_root']
        all_sources=read(boot/'public_DEV_sources.json')
        assert digest(all_sources)==read(boot/'binding.json')['DEV_public_sha256']
        sources={s['key']:s for s in all_sources if s['dataset']==OE}
        grade=study['grading_paths'][OE]
        grade_refs.add((grade,study['grading_file_sha256'][grade]))
        receipts.append(sha(stage/'terminal.json'))
        for arm in ARMS:
            directory=root/'dev'/'B8'/arm
            seal=verify(read(directory/'prediction_seal.json'),'prediction_seal_sha256')
            score=verify(read(directory/'scores.json'),'cell_sha256')
            assert seal['task_sha256']==digest(read(directory/'task.json'))
            assert score['partition']==partition and score['cell_sha256']==end['cell_sha256'][arm]
            assert seal['prediction_seal_sha256']==score['prediction_seal_sha256']
            for key in sources:
                saved=read(directory/'predictions'/(digest(key)+'.json'))
                assert digest(saved)==seal['predictions_sha256'][key] and saved['library_sha256']==score['libraries'][OE]
                data[arm][key]=saved
    assert len(sources)==(32 if partition=='train' else 16)
    assert all(s['project_split']==partition for s in sources.values())
    ((grade,grade_sha256),)=grade_refs
    assert partition in Path(grade).parts
    guards={key:amount_guard(ev_view(s)['public']) for key,s in sources.items()}
    bank={arm:{} for arm in ARMS}; paid=set()
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        assert not db.execute("select 1 from calls where status='reserved'").fetchone()
        for arm,rows in data.items():
            for key,saved in rows.items():
                row=read_ev(db,sources[key],saved,paid,partition)
                before=row['answer']
                after,n=clip_claims(before,guards[key])
                bank[arm][key]={'original':before,'asset_bound':after,'claims_changed':n,'handled':row['handled']}
    lock={'study':'EV_direct_public_amount_bound','partition':partition,
          'source_cluster_sha256':digest(sources),'original_stage_terminals':receipts,
          'grader_sha256':grade_sha256,'runner_sha256':sha(Path(__file__)),
          'rule':'Clip a unique in-scope claim exceeding the original valuation, with no change to eligibility.'}
    out=HOME/partition/digest(lock)
    immutable_json(out/'binding.json',lock)
    immutable_json(out/'predictions.json',bank)
    assert sha(ROOT/grade)==grade_sha256
    terminal={'partition':partition,'source_guard_coverage':sum(g is not None for g in guards.values()),
              'physical_responses_verified':len(paid),'new_calls':0,'scores':all_scores(bank,sources,read(ROOT/grade)),
              'predictions_sha256':sha(out/'predictions.json')}
    immutable_json(out/'terminal.json',terminal)
    return {'artifact_root':str(out.relative_to(ROOT)),**terminal}


if __name__=='__main__':
    import argparse

    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('partition',choices=('train','dev'))
    args=parser.parse_args()
    print(json.dumps(score_partition(args.partition),sort_keys=True))
