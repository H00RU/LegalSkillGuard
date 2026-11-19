"""Replay an explicit subsection attachment check on original MAUD views."""

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sqlite3

from experiments.convergence_formal_b1_observe import POINTER as FIRST, load_roster
from experiments.convergence_formal_bootstrap import POINTER as BOOTSTRAP
from experiments.convergence_formal_curves import pointer as dev_pointer
from experiments.convergence_formal_train_fit import EXTERNAL_ARM, ORDINARY
from experiments.convergence_formal_train_observe import pointer as observe_pointer
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha
from experiments.convergence_revision5_cni_nonsolicitation import bound_stage
from experiments.convergence_revision5_cni_oral_dev import verify_wire
from experiments.convergence_revision5_maud_parent_definition_coverage import NEGATIVE, ORDINARY_ONLY, unpage
from experiments.convergence_revision5_maud_sibling_cue import CUES, response, verify_prediction
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.paired_interfaces.formal_evaluation import verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


MAUD = 'MAUD'
ARMS = (ORDINARY, EXTERNAL_ARM)
MODES = ('original','deeming_only','separate_headers','attached_exceptions')
HOME = BASE / 'revision5_MAUD_section_scope_20261119'
AFFIRMATIVE = re.compile(r'\b(?:conducts?|operate[sd]?)\b[^.;]{0,185}\bin\s+(?:the\s+)?ordinary course', re.I)
NEW_NEGATIVE = re.compile(
    r'\(b\)\s+(?:in addition,\s*without limiting the generality of the foregoing,\s*)?except\b|'
    r'\bwithout limiting the foregoing,\s*and as an extension thereof,\s*except\b|'
    r'\bwithout limiting the generality of and in furtherance of the foregoing sentence,'
    r'\s*during the interim period,\s*except\b', re.I)
NEGATIVE_GOVERNOR = re.compile(r'\b(?:company|parent)\s+(?:shall|will)\s+not\b',re.I)
AFFIRMATIVE_HEADER = re.compile(r'\(a\)\s+except\b',re.I)
IMPORT = re.compile(
    r'\b(?:subject to|pursuant to|as permitted by|in accordance with)\b[^.;]{0,70}'
    r'(?:foregoing exceptions|(?:Section\s+)?\d+\.\d+\s*\(a\))',re.I)
PANDEMIC_EXCEPTION = re.compile(
    r'\brequired by applicable law\s*\(including (?:any )?covid-19 measures\)|'
    r'\bfor commercially reasonable actions in deviation of the prohibitions\b'
    r'[^:]{1,450}\bto (?:comply with or implement|implement) COVID-19 Measures\b',re.I)


def attachment_proof(public):
    """Certify the narrow case of a visible cue under a separate affirmative duty."""
    text=unpage(public['source_text'])
    cues=list(CUES.finditer(text))
    if not cues:
        return {'separate_headers':False,'deeming_only':False,'cue_count':0,
                'attached_negative_exception':False}
    deeming = ORDINARY_ONLY.search(text)
    direct = bool(deeming and all(deeming.start()<=m.start()<deeming.end() for m in cues))
    row={'separate_headers':False,'deeming_only':direct,'cue_count':len(cues),
         'attached_negative_exception':False}
    for border in NEW_NEGATIVE.finditer(text):
        after=text[border.end():]
        governor=NEGATIVE_GOVERNOR.search(after)
        if not governor:
            continue
        prefix=after[:governor.start()]
        if len(prefix)<=1400:
            exact=PANDEMIC_EXCEPTION.search(prefix)
            intervening=AFFIRMATIVE.search(prefix) or NEW_NEGATIVE.search(prefix)
            if exact and not intervening:
                row.update(attached_negative_exception=True,
                           negative_exception_range=[border.end()+exact.start(),border.end()+exact.end()],
                           governing_negative_prefix=[border.start(),border.end()+governor.end()],
                           source_text_sha256=digest(text))
        if any(m.start()>=border.start() for m in cues) or IMPORT.search(prefix):
            continue
        affirmative=list(AFFIRMATIVE.finditer(text,0,border.start()))
        if not affirmative:
            continue
        duty=affirmative[-1]
        headers=list(AFFIRMATIVE_HEADER.finditer(text,0,duty.start()))
        before_duty=bool(headers and all(headers[-1].start()<=m.start()<duty.start() for m in cues)
                         and NEGATIVE_GOVERNOR.search(text,headers[-1].end(),duty.start()) is None)
        if direct or before_duty:
            return {**row,'separate_headers':True,
                    'governing_negative_prefix':[border.start(),border.end()+governor.end()],
                    'ordinary_duty_range':[duty.start(),duty.end()],
                    'source_text_sha256':digest(text)}
    return row


def view_for(source):
    view,=(v for v in source['views'] if v['id']==NEGATIVE)
    return view


def policies(native, proof):
    answer=native['answer']
    separate = 'No' if proof['separate_headers'] else answer
    return {'original':answer,'deeming_only':'No' if proof['deeming_only'] else answer,
            'separate_headers':separate,
            'attached_exceptions':'Yes' if proof['attached_negative_exception'] else separate}


def summarize(bank, sources, grades, proof):
    result={}
    for arm,rows in bank.items():
        grade_rows={mode:[] for mode in MODES}
        switched={m:Counter() for m in MODES[1:]}
        for key,answers in rows.items():
            target=grades[key][NEGATIVE]['answer']
            for mode,value in answers.items():
                grade=grade_view(MAUD,view_for(sources[key]),grades[key][NEGATIVE],value)['grade']
                grade_rows[mode].append({'source':key,'view':NEGATIVE,'grade':grade})
                if mode!='original' and value!=answers['original']:
                    switched[mode]['corrected' if value==target else 'regressed' if answers['original']==target else 'other']+=1
        result[arm]={'correct':{mode:int(sum(r['grade'] for r in g)) for mode,g in grade_rows.items()},
                     'mothers':len(rows),'switches':switched,
                     'scope_vs_original':paired_source_effect(grade_rows['original'],grade_rows['separate_headers']),
                     'scope_vs_deeming_only':paired_source_effect(grade_rows['deeming_only'],grade_rows['separate_headers']),
                     'attached_exceptions_vs_original':paired_source_effect(
                         grade_rows['original'],grade_rows['attached_exceptions']),
                     'source_scope_positives':sum(proof[k]['separate_headers'] and grades[k][NEGATIVE]['answer']=='Yes'
                                                 for k in rows)}
    return result


def source_counts(proof):
    return {'separate_headers':sum(r['separate_headers'] for r in proof.values()),
            'deeming_only':sum(r['deeming_only'] for r in proof.values()),
            'attached_negative_exceptions':sum(r['attached_negative_exception'] for r in proof.values()),
            'cue_bearing':sum(bool(r['cue_count']) for r in proof.values())}


def train():
    root=ROOT/read(BOOTSTRAP)['artifact_root']; study=read(root/'binding.json')
    assert digest(study)==root.name
    batches=load_roster(study)
    sources={s['key']:s for b in batches for s in b if s['dataset']==MAUD}
    assert len(sources)==24 and all(s['project_split']=='train' for s in sources.values())
    proof={key:attachment_proof(view_for(s)['public']) for key,s in sources.items()}
    assert any(r['separate_headers'] for r in proof.values())
    journal=TrainingJournal(root,study,batches)
    bank={a:{} for a in ARMS}
    receipts=[]; retained=set(); paid=set()
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro', uri=True) as db:
        assert not db.execute("select 1 from calls where status='reserved'").fetchone()
        for batch,rows in enumerate(batches,1):
            stage,obs,end=bound_stage(FIRST if batch==1 else observe_pointer(batch))
            receipts.append(sha(stage/'terminal.json'))
            grade=obs['native_grade_paths'][MAUD]
            retained.add((grade,obs['native_grade_sha256'][grade]))
            for arm in ARMS:
                archive=journal._observations(arm,batch)
                assert archive['train_observation_sha256']==end['observation_receipts'][arm]
                for s in (s for s in rows if s['dataset']==MAUD):
                    key=s['key']
                    saved=read(journal.directory(arm,batch)/'predictions'/(digest(key)+'.json'))
                    assert digest(saved)==archive['predictions'][key]
                    row=saved['result']
                    call=verify_prediction(db,key,row)
                    if call not in paid:
                        raw,payload=response(db,key,call)
                        user=next(m['content'] for m in payload['messages'] if m['role']=='user')
                        doc=json.loads(user)
                        assert view_for(s)['public'] in [v['public'] for v in doc.get('public',doc)['native_views']]
                        paid.add(call)
                    bank[arm][key]=policies(row['native'][NEGATIVE],proof[key])
    ((grade,expected),)=retained
    assert 'train' in Path(grade).parts
    lock={'partition':'TRAIN','runner_sha256':sha(Path(__file__)),'source_cluster_sha256':digest(sources),
          'stage_terminal_sha256':receipts,'proof_sha256':digest(proof),'grade_sha256':expected,
          'hypothesis':'View-local exception attachment excludes earlier ordinary cues and recovers explicit '
                       'exceptions in the preamble of the target negative covenant.'}
    out=HOME/'TRAIN'/digest(lock)
    immutable_json(out/'binding.json',lock)
    immutable_json(out/'predictions.json',bank)
    assert sha(ROOT/grade)==expected
    terminal={'partition':'TRAIN','source_counts':source_counts(proof),'physical_reads_verified':len(paid),
              'by_arm':summarize(bank,sources,read(ROOT/grade),proof),'predictions_sha256':sha(out/'predictions.json')}
    immutable_json(out/'terminal.json',terminal)
    return out,terminal


def dev(train_root):
    stage,config,archived_end=bound_stage(dev_pointer(8))
    root=ROOT/config['checkpoint_root']; study=read(root/'binding.json')
    assert config['checkpoint_binding_sha256']==digest(study)
    b0=ROOT/config['b0_dev_data_root']; roster=read(b0/'public_DEV_sources.json')
    assert digest(roster)==read(b0/'binding.json')['DEV_public_sha256']
    sources={s['key']:s for s in roster if s['dataset']==MAUD and s['project_split']=='dev'}
    assert len(sources)==16
    proof={k:attachment_proof(view_for(s)['public']) for k,s in sources.items()}
    grade=study['grading_paths'][MAUD]
    assert 'dev' in Path(grade).parts
    lock={'partition':'DEV','runner_sha256':sha(Path(__file__)),'source_cluster_sha256':digest(sources),
          'train_binding_sha256':sha(train_root/'binding.json'),'train_terminal_sha256':sha(train_root/'terminal.json'),
          'dev_terminal_sha256':sha(stage/'terminal.json'),'grade_sha256':study['grading_file_sha256'][grade],
          'proof_sha256':digest(proof)}
    out=HOME/'DEV'/digest(lock)
    immutable_json(out/'binding.json',lock)
    bank={a:{} for a in ARMS}; paid=set()
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        for arm in ARMS:
            directory=root/'dev'/'B8'/arm
            receipt=verify(read(directory/'prediction_seal.json'),'prediction_seal_sha256')
            scores=verify(read(directory/'scores.json'),'cell_sha256')
            task=read(directory/'task.json')
            assert receipt['task_sha256']==digest(task) and receipt['prediction_seal_sha256']==scores['prediction_seal_sha256']
            assert scores['partition']=='dev' and scores['cell_sha256']==archived_end['cell_sha256'][arm]
            for key in sources:
                saved=read(directory/'predictions'/(digest(key)+'.json'))
                assert digest(saved)==receipt['predictions_sha256'][key]
                assert saved['source']==key and saved['library_sha256']==scores['libraries'][MAUD]
                output=verify_wire(db,key,saved['result'],paid)
                bank[arm][key]=policies(output[NEGATIVE],proof[key])
    immutable_json(out/'predictions.json',bank)
    assert sha(ROOT/grade)==lock['grade_sha256']
    terminal={'partition':'DEV','source_counts':source_counts(proof),'physical_reads_verified':len(paid),
              'by_arm':summarize(bank,sources,read(ROOT/grade),proof),
              'predictions_sha256':sha(out/'predictions.json'),'new_calls':0}
    immutable_json(out/'terminal.json',terminal)
    return out,terminal


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('partition',choices=('train','dev'))
    mode=parser.parse_args().partition
    root,report=train()
    out,terminal=(root,report) if mode=='train' else dev(root)
    print(json.dumps({'artifact_root':str(out.relative_to(ROOT)),**terminal},sort_keys=True))
