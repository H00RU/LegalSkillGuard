"""Recover ContractNLI personnel-solicitation scope from bound native reads."""

from collections import Counter
from pathlib import Path
import re
import sqlite3
from statistics import mean

from experiments.convergence_formal_b1_observe import POINTER as FIRST, load_roster
from experiments.convergence_formal_bootstrap import POINTER as BOOTSTRAP
from experiments.convergence_formal_curves import pointer as dev_pointer
from experiments.convergence_formal_train_fit import EXTERNAL_ARM, ORDINARY, pointer as fit_pointer
from experiments.convergence_formal_train_observe import pointer as observe_pointer
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha
from experiments.convergence_revision5_cni_linked_evidence import DATASET, span_inventory
from experiments.convergence_revision5_cni_oral_dev import verify_wire as verify_dev_wire
from experiments.convergence_revision5_cni_scoped_update import (
    POINTER as SCOPE_POINTER, verify_public_wire,
)
from experiments.convergence_revision5_m2_cni_disposition_retention import verify_prediction
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.paired_interfaces.formal_evaluation import verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


TASK = 'nda-18'
HERE = BASE / 'revision5_CNI_nonsolicitation_20261119'
ACTION = re.compile(r'\b(?:solicit\w*|recruit\w*|poach\w*|entic\w*)\b', re.I)
VERB = re.compile(r'\b(?:solicit|recruit|poach|entice)\b', re.I)
SECONDARY = re.compile(r'\b(?:hire|employ|engage|induce|persuade)\b', re.I)
PERSON = re.compile(r'\b(?:director|officer|employee|consultant|contractor|representative)s?\b|'
                    r'\bperson(?:s)?\b.{0,35}\bemployed\b', re.I)
VOTE = re.compile(r'\b(?:votes?|voting|prox(?:y|ies)|tender offer|stockholder|shareholder)\b', re.I)
TERM = re.compile(r'\brestricted persons?\b', re.I)
OWNER = re.compile(r'\b(?:other party|originating party|disclosing party|auditee|of you|by you)\b', re.I)
BAR = re.compile(r'\b(?:(?:shall|will|may|must) not|agrees? not to|is prohibited from|'
                 r'neither party shall)\b', re.I)
NUMBER = re.compile(r'^\s*(\d+(?:\.\d+)+)\.?\s+')
MODES = ('original','direct','linked')


def provision(view):
    """Bind a prohibition to the same operative action and personnel class."""
    spans = [' '.join(s.split()) for s in span_inventory(view)]
    definitions = [i for i,s in enumerate(spans) if TERM.search(s)
                   and re.search(r'\b(?:means|includes)\b',s,re.I) and PERSON.search(s)]
    direct, linked, unclear, votes = [], [], set(), set()
    for i, clause in enumerate(spans):
        if not ACTION.search(clause):
            if BAR.search(clause) and SECONDARY.search(clause) and PERSON.search(clause):
                unclear.add(i)
            continue
        verbs = list(VERB.finditer(clause))
        if not verbs and VOTE.search(clause):
            votes.add(i)
            continue
        if not verbs:
            unclear.add(i)
        for verb in verbs:
            before, after = clause[:verb.start()], clause[verb.end():]
            scoped_after = re.split(r'[;.]', after, maxsplit=1)[0]
            if VOTE.search(scoped_after[:85]) and not (PERSON.search(scoped_after[:85]) or TERM.search(scoped_after[:85])):
                votes.add(i)
                continue
            if BAR.search(before) and PERSON.search(scoped_after) and OWNER.search(scoped_after):
                direct.append([i])
            else:
                num = NUMBER.match(clause)
                child = num[1].rsplit('.',1)[0] if num else None
                headers = [j for j in range(max(0,i-5),i)
                           if (parent:=NUMBER.match(spans[j])) and parent[1]==child
                           and spans[j].endswith(':') and BAR.search(spans[j])]
                if len(headers)==len(definitions)==1 and TERM.search(scoped_after) and OWNER.search(scoped_after):
                    linked.append(sorted([definitions[0],headers[0],i]))
                else:
                    unclear.add(i)
    # An unindexed lexical occurrence blocks an absence update as well.
    full = view['public']['source_text']
    if sum(1 for _ in ACTION.finditer(full)) > sum(len(ACTION.findall(s)) for s in spans):
        unclear.add(-1)
    return {'direct':direct,'linked':linked,'unresolved':sorted(unclear),'votes':sorted(votes)}


def project(proof, native, *, use_links):
    supported = proof['direct'] + (proof['linked'] if use_links else [])
    if supported:
        return {'answer':'Entailment','evidence_sentence_ids':sorted({p for group in supported for p in group})}
    if proof['unresolved'] or proof['linked']:
        return native
    return {'answer':'NotMentioned','evidence_sentence_ids':[]}


def choices(proof, native):
    return {'original':native,'direct':project(proof,native,use_links=False),'linked':project(proof,native,use_links=True)}


def view_for(source):
    return next(v for v in source['views'] if v['id']==TASK)


def estimate(views, predictions, labels):
    modes = tuple(next(iter(predictions.values())))
    scores = {mode:{metric:[] for metric in ('grade','evidence_f1','grounded')} for mode in modes}
    recall = Counter()
    positives = sum(labels[key][TASK]['answer']=='Entailment' for key in predictions)
    for key, alternatives in predictions.items():
        view, gold = views[key], labels[key][TASK]
        for mode, value in alternatives.items():
            quality = grade_view(DATASET,view,gold,value['answer'],value['evidence_sentence_ids'])
            if gold['answer']=='Entailment':
                recall[mode] += int(quality['grade'])
            values = {**quality,'grounded':quality['grade']*quality['evidence_f1']}
            for metric in scores[mode]:
                scores[mode][metric].append({'source':key,'view':TASK,'grade':values[metric]})
    metrics = {mode:{'correct':int(sum(r['grade'] for r in rows['grade'])),
                     'total':len(rows['grade']), 'positive_correct':recall[mode],'positives':positives,
                     **{m:mean(r['grade'] for r in rows[m]) for m in ('evidence_f1','grounded')}}
               for mode,rows in scores.items()}
    comparisons = {}
    if modes == MODES:
        for a,b in (('original','linked'),('direct','linked')):
            comparisons[f'{b}_vs_{a}'] = {metric:paired_source_effect(scores[a][metric],scores[b][metric])
                                        for metric in scores[a]}
    return {'metrics':metrics,'paired':comparisons}


def bound_stage(pointer):
    root = ROOT/read(pointer)['artifact_root']
    binding, terminal = (read(root / n) for n in ('binding.json','terminal.json'))
    assert root.name==digest(binding) and not terminal['TEST_opened']
    assert all(sha(root/'source_snapshot'/k)==v for k,v in binding['source_sha256'].items())
    return root,binding,terminal


def train():
    root = ROOT/read(BOOTSTRAP)['artifact_root']
    binding = read(root/'binding.json')
    assert digest(binding)==root.name
    roster = load_roster(binding)
    journal = TrainingJournal(root,binding,roster)
    by_batch = [[s for s in rows if s['dataset']==DATASET and s['project_split']=='train'] for rows in roster]
    sources = {s['key']:s for rows in by_batch for s in rows}
    assert len(sources)==24
    views = {k:view_for(s) for k,s in sources.items()}
    proof = {k:provision(v) for k,v in views.items()}
    bank, verified, observation_refs = {a:{} for a in (ORDINARY,EXTERNAL_ARM)},set(),[]
    hist = {}
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        assert not db.execute("select 1 from calls where status='reserved'").fetchone()
        for b,rows in enumerate(by_batch,1):
            stage, spec, terminal = bound_stage(FIRST if b==1 else observe_pointer(b))
            observation_refs.append(sha(stage/'terminal.json'))
            for arm in bank:
                obs=journal._observations(arm,b)
                assert terminal['observation_receipts'][arm]==obs['train_observation_sha256']
                for source in rows:
                    key=source['key']
                    row=read(journal.directory(arm,b)/'predictions'/(digest(key)+'.json'))
                    assert digest(row)==obs['predictions'][key]
                    identity=verify_prediction(db,key,row['result'])
                    if identity not in verified:
                        verify_public_wire(db,source,identity)
                        verified.add(identity)
                    bank[arm][key]=choices(proof[key],row['result']['native'][TASK])
        fit, _, fit_end = bound_stage(fit_pointer(4))
        decisions=read(fit/'matched_decisions.json')
        assert digest(decisions)==fit_end['matched_decisions_sha256']
        folder=fit/'candidates'/EXTERNAL_ARM/DATASET
        data, earlier = (read(folder/n) for n in ('measurements.json','prior_TRAIN_regression.json'))
        decision=decisions['teacher'][EXTERNAL_ARM][DATASET]
        assert digest(earlier)==decision['earlier_TRAIN_regression']['evidence_sha256']
        assert digest(data['predictions'])==decision['predictions_sha256'] and decision['selected']=='incumbent'
        for key,result in earlier['candidate'].items():
            identity=verify_prediction(db,key,result)
            verify_public_wire(db,sources[key],identity)
            verified.add(identity)
            hist[key]={'incumbent':earlier['before'][key]['native'][TASK],'candidate':result['native'][TASK]}
            identity=verify_prediction(db,key,earlier['before'][key])
            verify_public_wire(db,sources[key],identity)
            verified.add(identity)
        for key,result in data['predictions'].items():
            identity=verify_prediction(db,key,result)
            verify_public_wire(db,sources[key],identity)
            verified.add(identity)
            hist[key]={'incumbent':bank[EXTERNAL_ARM][key]['original'],'candidate':result['native'][TASK]}
        correct=ROOT/read(SCOPE_POINTER)['artifact_root']
        predecessor,corrected=(read(correct/n) for n in ('binding.json','terminal.json'))
        assert digest(predecessor)==correct.name and predecessor['public_wire']=='original_explicit_zero_based_spans_for_both_readers'
        assert corrected['predictions_sha256']==sha(correct/'predictions.json')
        forward=read(correct/'predictions.json')
        for i, source in enumerate(by_batch[4]):
            key=source['key']
            row=read(correct/'reads'/f'{i}.json')
            verify_public_wire(db,source,row['physical_call_id'])
            verified.add(row['physical_call_id'])
            assert row['native'][TASK]==forward[key]['whole_candidate'][TASK]
            hist[key]={'incumbent':forward[key]['incumbent'][TASK],'candidate':row['native'][TASK]}
    grade = spec['native_grade_paths'][DATASET]
    assert 'train' in Path(grade).parts
    files = (Path(__file__).resolve().relative_to(ROOT),
             'experiments/convergence_revision5_cni_scoped_update.py',
             'experiments/convergence_revision5_cni_oral_dev.py',
             'legal_skill_guard/skill_evolution/native.py')
    lock={'scope':'original_24_CNI_TRAIN','runner_sha256':sha(Path(__file__)),'proof_sha256':digest(proof),
          'original_observation_sha256':observation_refs,'fit_terminal_sha256':sha(fit/'terminal.json'),
          'B5_wire_corrected_terminal_sha256':sha(correct/'terminal.json'),
          'grade_file_sha256':spec['native_grade_sha256'][grade],
          'sources_sha256':{str(f):sha(ROOT/f) for f in files}}
    out=HERE/'TRAIN'/digest(lock)
    immutable_json(out/'binding.json',lock)
    immutable_json(out/'predictions.json',{'bank':bank,'archived_candidate':hist})
    assert sha(ROOT/grade)==lock['grade_file_sha256']
    labels=read(ROOT/grade)
    report={'scope':'TRAIN','all_sources_sha256':digest(sources),
            'physical_reads_verified':len(verified),'archived_candidate_through_B5':estimate(views,hist,labels),
            'direct_witnesses':sum(bool(x['direct']) for x in proof.values()),
            'separate_definition_witnesses':sum(bool(x['linked']) for x in proof.values()),
            'unresolved_or_unhandled':sum(not(x['direct'] or x['linked']) and bool(x['unresolved']) for x in proof.values()),
            'explicit_vote_decoys':sum(bool(x['votes']) for x in proof.values()),
            'by_arm':{a:estimate(views,v,labels) for a,v in bank.items()},
            'predictions_sha256':sha(out/'predictions.json')}
    immutable_json(out/'terminal.json',report)
    return out,lock,report


def dev(train_root, train_binding, train_summary):
    stage,binding,terminal = bound_stage(dev_pointer(8))
    root = ROOT/binding['checkpoint_root']
    study = read(root/'binding.json')
    assert digest(study)==binding['checkpoint_binding_sha256']
    b0=ROOT/binding['b0_dev_data_root']
    original=read(b0/'public_DEV_sources.json')
    assert digest(original)==read(b0/'binding.json')['DEV_public_sha256']
    sources={s['key']:s for s in original if s['dataset']==DATASET and s['project_split']=='dev'}
    assert len(sources)==16 and len(original)==80
    views={k:view_for(s) for k,s in sources.items()}
    proof={k:provision(v) for k,v in views.items()}
    grade=study['grading_paths'][DATASET]
    assert 'dev' in Path(grade).parts
    lock={'scope':'fixed_B8_DEV_only','TRAIN_binding_sha256':sha(train_root/'binding.json'),
          'TRAIN_terminal_sha256':sha(train_root/'terminal.json'),'runner_sha256':sha(Path(__file__)),
          'train_sources_sha256':train_binding['sources_sha256'],'archived_B8_DEV_terminal_sha256':sha(stage/'terminal.json'),
          'dev_sources_sha256':digest(sources),'dev_proof_sha256':digest(proof),'grader_sha256':study['grading_file_sha256'][grade]}
    out=HERE/'DEV'/digest(lock)
    immutable_json(out/'binding.json',lock)
    bank={}; known=set()
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        for arm in (ORDINARY,EXTERNAL_ARM):
            directory=root/'dev'/'B8'/arm
            task=read(directory/'task.json')
            seal=verify(read(directory/'prediction_seal.json'),'prediction_seal_sha256')
            cell=verify(read(directory/'scores.json'),'cell_sha256')
            assert cell['partition']=='dev' and cell['cell_sha256']==terminal['cell_sha256'][arm]
            assert seal['task_sha256']==digest(task) and cell['prediction_seal_sha256']==seal['prediction_seal_sha256']
            assert seal['predictions_sha256'].keys()=={r['key'] for r in original}
            bank[arm]={}
            for key in views:
                saved=read(directory/'predictions'/(digest(key)+'.json'))
                assert digest(saved)==seal['predictions_sha256'][key]
                assert saved['source']==key and saved['library_sha256']==cell['libraries'][DATASET]
                native=verify_dev_wire(db,key,saved['result'],known)
                bank[arm][key]=choices(proof[key],native[TASK])
    immutable_json(out/'predictions.json',bank)
    assert sha(ROOT/grade)==lock['grader_sha256']
    labels=read(ROOT/grade)
    terminal={'scope':'DEV','new_calls':0,'physical_reads_verified':len(known),
              'frozen_TRAIN_replay':train_summary['physical_reads_verified'],
              'direct_witnesses':sum(bool(p['direct']) for p in proof.values()),
              'separate_definition_witnesses':sum(bool(p['linked']) for p in proof.values()),
              'unresolved_or_unhandled':sum(not(p['direct'] or p['linked']) and bool(p['unresolved']) for p in proof.values()),
              'explicit_vote_decoys':sum(bool(p['votes']) for p in proof.values()),
              'by_arm':{a:estimate(views,p,labels) for a,p in bank.items()},
              'predictions_sha256':sha(out/'predictions.json')}
    immutable_json(out/'terminal.json',terminal)
    return out,terminal


if __name__=='__main__':
    import argparse
    import json
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('partition',choices=('train','dev'))
    mode=parser.parse_args().partition
    train_root, train_binding, train_summary=train()
    output=(train_root,train_summary) if mode=='train' else dev(train_root,train_binding,train_summary)
    print(json.dumps({'artifact_root':str(output[0].relative_to(ROOT)),**output[1]},sort_keys=True))
