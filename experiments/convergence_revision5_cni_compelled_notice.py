"""Replay compelled-disclosure notice witnesses and archived CNI update decisions."""

import argparse
import json
import re
from pathlib import Path
import sqlite3
from statistics import mean

from experiments.convergence_formal_b1_observe import POINTER as FIRST, load_roster
from experiments.convergence_formal_bootstrap import POINTER as BOOTSTRAP
from experiments.convergence_formal_curves import pointer as dev_pointer
from experiments.convergence_formal_train_fit import EXTERNAL_ARM, ORDINARY, pointer as fit_pointer
from experiments.convergence_formal_train_observe import pointer as observe_pointer
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision5_cni_linked_evidence import span_inventory
from experiments.convergence_revision5_cni_nonsolicitation import bound_stage
from experiments.convergence_revision5_cni_oral_dev import verify_wire as verify_dev_wire
from experiments.convergence_revision5_cni_scoped_update import verify_public_wire
from experiments.convergence_revision5_m2_cni_disposition_retention import verify_prediction
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.paired_interfaces.formal_evaluation import verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


DATASET, TASK = 'ContractNLI', 'nda-8'
HOME = BASE/'revision5_CNI_compelled_notice_20261119'
TRAIN = HANDOFF/'revision5_CNI_compelled_notice_TRAIN_current.json'
ARMS = (ORDINARY, EXTERNAL_ARM)
LAW = re.compile(r'\b(?:subpoena|court|applicable law|legal(?:ly)?\s+(?:compelled|process|requirement)|'
                 r'government(?:al)?\s+(?:authority|body|entit\w*)|regulatory\s+(?:authority|body)|'
                 r'lawful process|judicial|securities laws|(?:freedom of information act|public records)\s+(?:or|disclosure|request)|'
                 r'required by law|mandated under the law|law or regulation)\b',re.I)
COMPEL = re.compile(r'\b(?:requir(?:ed|ing)|compelled|pursuant to|in response to|mandated|requested|'
                    r'(?:receiv\w*|receipt of).{0,95}(?:subpoena|legal process|public records disclosure request))\b',re.I)
DISCLOSE = re.compile(r'\b(?:disclos(?:e[ds]?|ing|ure)|share|public records)\b',re.I)
NOTICE = re.compile(r'\b(?:notif(?:y|ied|ication)|inform|advise|notice|prior written information|consult(?:ation)?)\b',re.I)
PARTY = re.compile(r'\b(?:disclos(?:ing party|er)|originating party|other part(?:y|ies)|each other|'
                   r'(?:other |affected |each )participating entit\w*|auditee|NYNEX|UNHCR|'
                   r'(?:notice|notify)\b.{0,34}\b(?:provider|you|general counsel))\b',re.I)
MANDATORY = re.compile(r'\b(?:shall|must|will|only make|provided|so long as|with prior|shall first)\b',re.I)
REFERENCE = re.compile(r'\b(?:under|pursuant to|in accordance with)\s+(?:clause|section|paragraph)\s+(\d+(?:\.\d+)+)\b',re.I)
NUMBER = re.compile(r'^\s*(\d+(?:\.\d+)+)\s+')
INITIAL = re.compile(r'^\s*\([a-zivx]+\)',re.I)
ANAPHOR = re.compile(r'\b(?:of (?:the|any|such) required disclosure|notice of such disclosure|of such receipt|'
                     r'any such request|notice thereof|of the request)\b',re.I)
OUTSIDE_ACTOR = re.compile(r'\b(?:inform|advise|notify)\s+(?:the |any )?(?:requesting authority|court|'
                           r'governmental authority|regulatory authority)\b',re.I)


def trigger(text):
    return bool(LAW.search(text) and COMPEL.search(text) and (DISCLOSE.search(text) or NUMBER.match(text)))


def notice(text):
    return bool(NOTICE.search(text) and PARTY.search(text) and MANDATORY.search(text) and not OUTSIDE_ACTOR.search(text))


def proof(view):
    spans = {i:' '.join(s.split()) for i,s in enumerate(span_inventory(view)) if s.strip()}
    positions = list(spans)
    triggers = {i for i,t in spans.items() if trigger(t)}
    numbers = {}
    for i,t in spans.items():
        match = NUMBER.match(t)
        if match:
            numbers.setdefault(match[1],[]).append(i)
    local, linked, unresolved = [], [], []
    for rank,(i,text) in enumerate(spans.items()):
        if not notice(text):
            continue
        refs = {n for n in REFERENCE.findall(text)}
        if i in triggers and not refs:
            local.append([i])
            continue
        exact = [j for n in refs if len(numbers.get(n,()))==1 for j in numbers[n] if j in triggers and j!=i]
        previous = positions[rank-1] if rank else None
        if len(exact)==1:
            j=exact[0]
            earlier_governing = [h for h,t in spans.items() if 0<j-h<=4 and t.endswith(':')
                                 and re.search(r'(?:disclose|disclosure of)\s+Confidential Information',t,re.I)]
            linked.append(sorted({i,j,*earlier_governing[-1:]}))
        elif not refs and previous in triggers and (
                ANAPHOR.search(text) or (INITIAL.search(text) and spans[previous].endswith('provided that'))):
            linked.append([previous,i])
        elif i in triggers or ANAPHOR.search(text) or refs:
            unresolved.append(i)
    return {'same_clause':local,'linked':linked,'unresolved_notice':unresolved,'trigger_count':len(triggers)}


def answer(output, source_proof, *, use_links):
    groups = source_proof['same_clause'] + (source_proof['linked'] if use_links else [])
    if groups:
        return {'answer':'Entailment','evidence_sentence_ids':sorted({x for g in groups for x in g})}
    if source_proof['linked'] or source_proof['unresolved_notice'] or source_proof['trigger_count']:
        return output
    return {'answer':'NotMentioned','evidence_sentence_ids':[]}


def alternatives(output,p):
    return {'original':output,'same_clause':answer(output,p,use_links=False),'linked':answer(output,p,use_links=True)}


def estimate(views,bank,grades):
    values={m:{'grade':[],'evidence_f1':[],'joint':[]} for m in next(iter(bank.values()))}
    for key,models in bank.items():
        for mode,output in models.items():
            g=grade_view(DATASET,views[key],grades[key][TASK],output['answer'],output['evidence_sentence_ids'])
            for item,value in {'grade':g['grade'],'evidence_f1':g['evidence_f1'],'joint':g['grade']*g['evidence_f1']}.items():
                values[mode][item].append({'source':key,'view':TASK,'grade':value})
    return {'metrics':{m:{'mothers':len(rows['grade']),'correct':int(sum(r['grade'] for r in rows['grade'])),
                          **{i:mean(r['grade'] for r in rows[i]) for i in ('evidence_f1','joint')}} for m,rows in values.items()},
            'paired':{m:{k:paired_source_effect(values['original'][k],values[m][k]) for k in ('grade','joint')}
                      for m in values if m!='original'}}


def view_for(source):
    return next(v for v in source['views'] if v['id']==TASK)


def train():
    root = ROOT/read(BOOTSTRAP)['artifact_root']
    study = read(root/'binding.json')
    assert root.name==digest(study)
    roster = load_roster(study)
    journal = TrainingJournal(root,study,roster)
    incoming,cohort,positions,wires,archive = {a:{} for a in ARMS},{},{},set(),{}
    candidate_bank = []
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        assert not db.execute("select 1 from calls where status='reserved'").fetchone()
        for n,batch in enumerate(roster,1):
            stage,binding,terminal=bound_stage(FIRST if n==1 else observe_pointer(n))
            archive[f'observe_{n}']=sha(stage/'terminal.json')
            for i,source in enumerate(s for s in batch if s['dataset']==DATASET):
                assert source['project_split']=='train'
                key=source['key']
                cohort[key]=source
                positions[key]=(n,i)
                for arm in ARMS:
                    observed=journal._observations(arm,n)
                    assert terminal['observation_receipts'][arm]==observed['train_observation_sha256']
                    pred=read(journal.directory(arm,n)/'predictions'/(digest(key)+'.json'))
                    assert digest(pred)==observed['predictions'][key]
                    pid=verify_prediction(db,key,pred['result'])
                    if pid not in wires:
                        verify_public_wire(db,source,pid)
                        wires.add(pid)
                    incoming[arm][key]=pred['result']['native'][TASK]
        for n in (3,4,5):
            stage,binding,terminal=bound_stage(fit_pointer(n))
            archive[f'fit_{n}']=sha(stage/'terminal.json')
            table=read(stage/'matched_decisions.json')
            assert digest(table)==terminal['matched_decisions_sha256']
            for arm in ARMS:
                decision=table['teacher'][arm][DATASET]
                if decision['native_utility_delta'] <= 0:
                    continue
                path=stage/'candidates'/arm/DATASET
                assert read(path/'decision.json')==decision
                changes=read(path/'measurements.json')['predictions']
                seen=read(path/'prior_TRAIN_regression.json')
                assert digest(changes)==decision['predictions_sha256']
                assert digest(seen)==decision['earlier_TRAIN_regression']['evidence_sha256']
                maps={}
                for key,after in (seen['candidate']|changes).items():
                    assert positions[key][0]<=n
                    before=seen['before'].get(key)
                    for record in (before,after):
                        if record is None:
                            continue
                        pid=verify_prediction(db,key,record)
                        if pid not in wires:
                            verify_public_wire(db,cohort[key],pid)
                            wires.add(pid)
                    maps[key]={'original':before['native'][TASK] if before else incoming[arm][key],
                               'candidate':after['native'][TASK]}
                candidate_bank.append({'fit_batch':n,'arm':arm,'original_decision':decision['selected'],'comparisons':maps})
    assert len(cohort)==24
    views = {key:view_for(s) for key,s in cohort.items()}
    evidence={k:proof(v) for k,v in views.items()}
    initialized={arm:{k:alternatives(out,evidence[k]) for k,out in rows.items()} for arm,rows in incoming.items()}
    for entry in candidate_bank:
        for key,rows in entry['comparisons'].items():
            rows['candidate_source_checked']=answer(rows['candidate'],evidence[key],use_links=True)
            rows['incumbent_source_checked']=answer(rows['original'],evidence[key],use_links=True)
    stage,observed,_=bound_stage(observe_pointer(8))
    grade=observed['native_grade_paths'][DATASET]
    assert 'train' in Path(grade).parts
    lock={'scope':'CNI_notice_and_trigger_TRAIN','runner_sha256':sha(Path(__file__)),'source_scope_sha256':digest(cohort),
          'source_evidence_sha256':digest(evidence),'native_grade_sha256':observed['native_grade_sha256'][grade],
          'observation_terminal_sha256':archive,'native_arms':list(ARMS),'reused_candidate_count':len(candidate_bank)}
    out=HOME/'TRAIN'/digest(lock)
    immutable_json(out/'binding.json',lock)
    immutable_json(out/'predictions.json',{'scope':evidence,'incoming':initialized,'candidates':candidate_bank})
    assert sha(ROOT/grade)==lock['native_grade_sha256']
    grades=read(ROOT/grade)
    reports=[]
    for entry in candidate_bank:
        maps=entry['comparisons']
        score=estimate(views,maps,grades)
        labels={'corrected':0,'regressed':0,'changed_decisions':0,'source_check_changes':0}
        for key,row in maps.items():
            expected=grades[key][TASK]['answer']
            before=row['original']['answer']
            candidate=row['candidate']['answer']
            labels['changed_decisions']+=candidate!=before
            labels['corrected']+=candidate!=before and candidate==expected
            labels['regressed']+=candidate!=before and before==expected
            labels['source_check_changes']+=row['candidate_source_checked']['answer']!=candidate
        reports.append({k:v for k,v in entry.items() if k!='comparisons'}|{'results':score,'label_changes':labels})
    result={'partition':'TRAIN','new_calls':0,'physical_responses_verified':len(wires),'candidate_results':reports,
            'direct_scope':{'same_clause':sum(bool(r['same_clause']) for r in evidence.values()),
                            'linked_only':sum(bool(r['linked']) and not r['same_clause'] for r in evidence.values())},
            'by_arm':{arm:estimate(views,rows,grades) for arm,rows in initialized.items()},
            'predictions_sha256':sha(out/'predictions.json')}
    immutable_json(out/'terminal.json',result)
    write_status(out,{'terminal_sha256':sha(out/'terminal.json')},TRAIN)
    return out,result


def dev():
    ready=read(TRAIN)
    training=ROOT/ready['artifact_root']
    training_lock=read(training/'binding.json')
    assert training.name==digest(training_lock) and sha(training/'terminal.json')==ready['terminal_sha256']
    assert sha(Path(__file__))==training_lock['runner_sha256']
    stage,binding,terminal=bound_stage(dev_pointer(8))
    root=ROOT/binding['checkpoint_root']; study=read(root/'binding.json')
    assert digest(study)==binding['checkpoint_binding_sha256']
    b0=ROOT/binding['b0_dev_data_root']
    sources=read(b0/'public_DEV_sources.json')
    assert digest(sources)==read(b0/'binding.json')['DEV_public_sha256']
    views={s['key']:view_for(s) for s in sources if s['dataset']==DATASET and s['project_split']=='dev'}
    assert len(views)==16 and len(sources)==80
    grade=study['grading_paths'][DATASET]
    assert 'dev' in Path(grade).parts
    evidence={k:proof(v) for k,v in views.items()}
    lock={'scope':'original_fixed_CNI_B8_DEV','TRAIN_terminal_sha256':ready['terminal_sha256'],
          'runner_sha256':sha(Path(__file__)),'original_DEV_terminal_sha256':sha(stage/'terminal.json'),
          'source_evidence_sha256':digest(evidence),'native_grade_sha256':study['grading_file_sha256'][grade]}
    out=HOME/'DEV'/digest(lock)
    bank,wire_ids={},set()
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        assert not db.execute("select 1 from calls where status='reserved'").fetchone()
        for arm in ARMS:
            directory=root/'dev'/'B8'/arm
            task=read(directory/'task.json')
            seal=verify(read(directory/'prediction_seal.json'),'prediction_seal_sha256')
            cell=verify(read(directory/'scores.json'),'cell_sha256')
            assert cell['partition']=='dev' and cell['cell_sha256']==terminal['cell_sha256'][arm]
            assert seal['task_sha256']==digest(task) and cell['prediction_seal_sha256']==seal['prediction_seal_sha256']
            assert seal['predictions_sha256'].keys()=={s['key'] for s in sources}
            bank[arm]={}
            for key in views:
                pred=read(directory/'predictions'/(digest(key)+'.json'))
                assert digest(pred)==seal['predictions_sha256'][key]
                assert pred['source']==key and pred['library_sha256']==cell['libraries'][DATASET]
                actual=verify_dev_wire(db,key,pred['result'],wire_ids)[TASK]
                bank[arm][key]=alternatives(actual,evidence[key])
    immutable_json(out/'binding.json',lock)
    immutable_json(out/'predictions.json',{'scope':evidence,'predictions':bank})
    assert sha(ROOT/grade)==lock['native_grade_sha256']
    grades=read(ROOT/grade)
    result={'partition':'fixed_B8_DEV','new_calls':0,'physical_responses_verified':len(wire_ids),
            'direct_scope':{'same_clause':sum(bool(r['same_clause']) for r in evidence.values()),
                            'linked_only':sum(bool(r['linked']) and not r['same_clause'] for r in evidence.values())},
            'by_arm':{arm:estimate(views,rows,grades) for arm,rows in bank.items()},
            'predictions_sha256':sha(out/'predictions.json')}
    immutable_json(out/'terminal.json',result)
    return out,result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('partition',choices=('train','dev'))
    out,report=(train if parser.parse_args().partition=='train' else dev)()
    print(json.dumps({'artifact_root':str(out.relative_to(ROOT)),**report},sort_keys=True),flush=True)
