"""Localize cross-view pandemic false positives in two archived MAUD updates."""

import argparse
from copy import deepcopy
import fcntl
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
from zipfile import ZipFile

import jsonschema

from experiments.convergence_revision5_maud_zero_evidence import (
    BOOTSTRAP, EXTERNAL_ARM, MAUD, ORDINARY, TrainingJournal, bound_stage,
    fit_pointer, load_roster, observe_pointer, response, verify_prediction,
)
from experiments.convergence_revision5_maud_parent_definition_coverage import (
    ARCHIVE, NEGATIVE, ORDINARY as ORDINARY_COVENANT, unpage,
)
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces.control_answers import decode_native, source_bundle, wire_schema
from legal_skill_guard.paired_interfaces.convergence_schema_control import ReversibleWire
from legal_skill_guard.paired_interfaces.scope_learning import strict_json
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view, record_schema, restore_enum_transport
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE / 'revision5_MAUD_sibling_cue_20261119'
POINTER = HANDOFF / 'revision5_MAUD_sibling_cue_current.json'
SETTLED = 'settled_MAUD_B6_B8_sibling_cue_TRAIN_diagnostic'
KNOWLEDGE = 'Knowledge Definition-Answer'
MODES = ('pandemic_mask', 'length_matched_mask')
CUES = re.compile(r'\b(?:covid(?:-\s*19)?|coronavirus|pandemic|epidemic|outbreak)\b', re.I)
PLACEBO = re.compile(r'\b(?:agreement|section|schedule|subsidiaries|respect|parties|information|'
                     r'company|business|documents|calendar|pending|delivery|statement|relevant|provided|'
                     r'party|title|named|basis|dated)\b', re.I)
SCOPES = {
    6: (1, 'modifications of such loans consistent with regulatory COVID-relief guidelines'),
    8: (1, 'except for such temporary closures'),
}


def span_edits(text):
    """Pick a nearby neutral reference of identical width for each cue."""
    covid = [(m.start(),m.end()) for m in CUES.finditer(text)]
    controls = [(m.start(),m.end()) for m in PLACEBO.finditer(text)]
    assert covid
    neutral = []
    for start,end in covid:
        match = min((p for p in controls if p[1]-p[0]==end-start),
                    key=lambda p:(abs(p[0]-start),p[0]))
        controls.remove(match)
        neutral.append(match)
    return dict(zip(MODES,(sorted(covid),sorted(neutral)),strict=True))


def mask(text, spans):
    start, pieces = 0, []
    for left,right in spans:
        assert start<=left<right<=len(text) and right-left>=3
        pieces.extend((text[start:left], '[x]' + ' '*(right-left-3)))
        start = right
    result = ''.join((*pieces,text[start:]))
    assert len(result)==len(text)
    return result


def messages_with_edit(payload, source, selected, mode):
    messages = deepcopy(payload['messages'])
    user, = (m for m in messages if m['role']=='user')
    obj = json.loads(user['content'])
    assert json.dumps(obj,ensure_ascii=False,sort_keys=True)==user['content']
    bundle = source_bundle(source)
    assert obj == {'public':bundle['public'],'answer_schema':bundle['answer_schema']}
    targets = obj['public']['native_views']
    view, = (view for view in targets if view['id']==NEGATIVE)
    text = view['public']['source_text']
    view['public']['source_text'] = mask(text,selected[mode])
    assert all(a==b for a,b in zip(targets,bundle['public']['native_views'],strict=True) if a['id']!=NEGATIVE)
    if mode=='pandemic_mask':
        assert not CUES.search(view['public']['source_text'])
    else:
        assert CUES.findall(text)==CUES.findall(view['public']['source_text'])
    user['content'] = json.dumps(obj,ensure_ascii=False,sort_keys=True)
    return messages


def archived_case(db, journal, fit, end, batch, arm, source):
    key = source['key']
    table = read(fit/'matched_decisions.json')
    assert digest(table)==end['matched_decisions_sha256']
    directory = fit/'candidates'/arm/MAUD
    changed = read(directory/'measurements.json')
    decision = table['teacher'][arm][MAUD]
    assert decision['selected']=='candidate' and digest(changed['predictions'])==decision['predictions_sha256']
    orig = read(journal.directory(arm,batch)/'predictions'/(digest(key)+'.json'))
    assert digest(orig)==journal._observations(arm,batch)['predictions'][key]
    case = {'source':source}
    for name,v in (('incumbent',orig['result']),('candidate',changed['predictions'][key])):
        physical = verify_prediction(db,key,v)
        raw,payload = response(db,key,physical)
        assert raw['finish_reason']=='stop'
        case[name]={'id':physical,'payload':payload,'native':v['native']}
    return case


def materials():
    root=ROOT/read(BOOTSTRAP)['artifact_root']
    study=read(root/'binding.json')
    assert digest(study)==root.name
    roster=load_roster(study)
    journal=TrainingJournal(root,study,roster)
    a=read(BASE/'postfreeze_M2_MAUD_source_scope_20261119'/'terminal.json')['parent_reference_audit']
    assert sha(ARCHIVE)==a['official_archive_sha256']
    cases,fit_hashes,observation_hashes,paths = [],{},{},set()
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db, ZipFile(ARCHIVE) as parents:
        assert not db.execute("select 1 from calls where status='reserved'").fetchone()
        for number,(ordinal,lead) in SCOPES.items():
            fit,setting,terminal=bound_stage(fit_pointer(number))
            observe,obs_setting,obs_end=bound_stage(observe_pointer(number))
            assert sha(observe/'terminal.json')==setting['observations_terminal_sha256']
            ref=journal._observations(EXTERNAL_ARM,number)
            assert ref['train_observation_sha256']==obs_end['observation_receipts'][EXTERNAL_ARM]
            fit_hashes[str(number)] = sha(fit/'terminal.json')
            observation_hashes[str(number)] = sha(observe/'terminal.json')
            grade=obs_setting['native_grade_paths'][MAUD]
            paths.add((grade,obs_setting['native_grade_sha256'][grade]))
            src=[s for s in roster[number-1] if s['dataset']==MAUD][ordinal]
            assert src['project_split']=='train'
            parent=parents.read('data/contracts/'+src['parent_id']+'.txt')
            assert sha256(parent).hexdigest()==src['fulltext_raw_sha256']
            view={v['id']:v['public']['source_text'] for v in src['views']}
            text=view[NEGATIVE]
            assert lead in unpage(text) and lead in unpage(parent.decode('utf-8-sig'))
            assert not CUES.search(view[ORDINARY_COVENANT])
            case=archived_case(db,journal,fit,terminal,number,EXTERNAL_ARM,src)
            assert [case[arm]['native'][ORDINARY_COVENANT]['answer'] for arm in ('incumbent','candidate')]==['Yes','No']
            if number==8:
                assert 'facts that are known by' in view[KNOWLEDGE]
                assert 'written notice received by such Person' in view[KNOWLEDGE]
                assert [case[a]['native'][KNOWLEDGE]['answer'] for a in ('incumbent','candidate')]==[
                    'Constructive knowledge','Actual knowledge']
            case['batch']=number
            case['schema_proposal']=journal.library(EXTERNAL_ARM,number-1)['schema_proposals'][MAUD]
            tape=case['incumbent']['payload']
            bundle=source_bundle(src)
            local=record_schema({'value':ReversibleWire(wire_schema(MAUD,bundle),case['schema_proposal']).schema})
            assert tape['response_format']['json_schema']['schema']==local
            case['edits']=span_edits(text)
            for mode in MODES:
                messages_with_edit(tape,src,case['edits'],mode)
            cases.append(case)
        # Verify the distinct B6 true-positive path from the ordinary teacher logs.
        b6,_,end=bound_stage(fit_pointer(6))
        positive=[s for s in roster[5] if s['dataset']==MAUD][0]
        known=archived_case(db,journal,b6,end,6,ORDINARY,positive)
        occ=next(v['public']['source_text'] for v in positive['views'] if v['id']==ORDINARY_COVENANT)
        assert 'as required by applicable Law (including any COVID-19 Measures)' in unpage(occ)
        assert [known[a]['native'][ORDINARY_COVENANT]['answer'] for a in ('incumbent','candidate')]==['No','Yes']
    ((grade,grade_hash),) = paths
    assert 'train' in Path(grade).parts
    paths=('experiments/convergence_revision5_maud_sibling_cue.py',
           'experiments/convergence_revision5_maud_zero_evidence.py',
           'experiments/convergence_revision5_m2_cumulative_audit.py',
           'legal_skill_guard/paired_interfaces/convergence_schema_control.py',
           'legal_skill_guard/paired_interfaces/control_answers.py')
    lock={'study':'MAUD_non_target_sibling_mask_train_diagnostic',
          'binding_scope':'paired visibility perturbation, no changes to native source identities',
          'native_target':[ORDINARY_COVENANT,KNOWLEDGE],
          'masked_view':NEGATIVE,'masked_view_excluded_from_scoring':True,
          'expected_effect':'The entrant switches the unchanged ordinary-covenant label to No after '
                            'masking the sibling pandemic cues, with no switch after a width-matched control mask.',
          'bound_fits':fit_hashes,'bound_observations':observation_hashes,
          'input_bindings':digest(cases),'unperturbed_positive_pair_sha256':digest(known),
          'grade_sha256':grade_hash,'source_sha256':{p:sha(ROOT/p) for p in paths},
          'executor':study['executor'],'planned_calls':2*len(cases)}
    return lock,cases,grade


def decode(case, raw):
    if raw['finish_reason']!='stop':
        return None
    source=case['source']
    bundle=source_bundle(source)
    codec=ReversibleWire(wire_schema(MAUD,bundle),case['schema_proposal'])
    schema=record_schema({'value':codec.schema})
    native,_=restore_enum_transport(strict_json(raw['content']),schema)
    answers,evidence=decode_native(MAUD,bundle,codec.restore(native['value']))
    return {k:{'answer':answers[k],'evidence_sentence_ids':evidence[k]} for k in (ORDINARY_COVENANT,KNOWLEDGE)}


def measurements(cases, pairs, grades):
    readout = []
    for case,pair in zip(cases,pairs,strict=True):
        src=case['source']
        views={v['id']:v for v in src['views']}
        row={'batch':case['batch'],'verified_control_char_widths':
             [b-a for a,b in case['edits']['pandemic_mask']], 'target_labels':{},
             'target_correct':{},'finish_reasons':{},'tokens_by_condition':{}}
        for name, answer in {**pair,**{k:case[k] for k in ('incumbent','candidate')}}.items():
            row['target_labels'][name]={t:answer['native'][t]['answer'] if answer['native'] else None
                                       for t in (ORDINARY_COVENANT,KNOWLEDGE)}
            row['target_correct'][name]=[bool(grade_view(MAUD,views[t],grades[src['key']][t],value)['grade'])
                                         for t,value in row['target_labels'][name].items()]
            if name in pair:
                row['finish_reasons'][name]=answer['finish_reason']
                row['tokens_by_condition'][name]=answer['usage']
        assert grades[src['key']][ORDINARY_COVENANT]['answer']=='No'
        readout.append(row)
    return readout


def run(execute):
    lock,cases,grade=materials()
    out=HOME/digest(lock)
    immutable_json(out/'binding.json',lock)
    if (out/'terminal.json').exists():
        print(json.dumps(read(out/'terminal.json'),sort_keys=True),flush=True)
        return
    if not execute:
        write_status(out,{'status':'prepared','planned_calls':lock['planned_calls']},POINTER)
        print(str(out.relative_to(ROOT)),flush=True)
        return
    assert ROOT/read(POINTER)['artifact_root']==out
    flag=(out/'driver.lock').open('a')
    fcntl.flock(flag,fcntl.LOCK_EX|fcntl.LOCK_NB)
    for name,h in lock['source_sha256'].items():
        path=out/'source_snapshot'/name
        path.parent.mkdir(parents=True,exist_ok=True)
        if not path.exists():
            with path.open('xb') as f:
                f.write((ROOT/name).read_bytes())
        assert sha(path)==h
    run_id='convergence-revision5-MAUD-sibling-cue-'+out.name[:16]
    ledger=EvolutionLedger(LEDGER,run_id=run_id,sources={'train':[c['source']['key'] for c in cases],'dev':[],'test':[]},binding=lock)
    reader=FrozenExecutor(ledger,out,lock['executor'])
    reader.readiness()
    pairs=[]
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        for index,case in enumerate(cases):
            pair={}; src=case['source']; key=src['key']; original=case['incumbent']['payload']
            schema=original['response_format']['json_schema']['schema']
            for mode in MODES if index==0 else MODES[::-1]:
                identity=f'{run_id}:{index}:{mode}'
                messages=messages_with_edit(original,src,case['edits'],mode)
                expected={**original,'messages':messages}
                assert reader.payload(messages=messages,thinking=False,schema=schema)==expected
                write_status(out,{'status':'running','completed_pairs':index,'current_call':identity},POINTER)
                result=reader.generate(identity,source=key,purpose='skill_actor',messages=messages,thinking=False,schema=schema)
                raw,payload=response(db,key,identity)
                assert payload==expected and raw['content']==result['content']
                try:
                    native = decode(case, raw)
                    error = None
                except (ValueError, KeyError, jsonschema.ValidationError) as failure:
                    native = None
                    error = type(failure).__name__
                pair[mode]={'id':identity,'native':native,'usage':raw['usage'],
                            'finish_reason':raw['finish_reason'],'error':error}
                immutable_json(out/'reads'/f'{index}_{mode}.json',pair[mode])
                print(json.dumps({'batch':case['batch'],'condition':mode,'finish_reason':raw['finish_reason']}),flush=True)
            pairs.append(pair)
        counts=dict(db.execute('select status,count(*) from calls group by status'))
        assert not counts.get('reserved')
    immutable_json(out/'predictions.json',pairs)
    assert sha(ROOT/grade)==lock['grade_sha256']
    terminal={'status':SETTLED,'TRAIN_only':True,'original_stage_decisions_preserved':True,
              'new_calls':lock['planned_calls'],'archived_reads':6,
              'tokens':sum(row['usage']['total_tokens'] for pair in pairs for row in pair.values()),
              'ledger':counts,'observations':measurements(cases,pairs,read(ROOT/grade)),
              'runner_sha256':sha(Path(__file__)),'predictions_sha256':sha(out/'predictions.json')}
    immutable_json(out/'terminal.json',terminal)
    write_status(out,{'status':SETTLED,'completed_pairs':len(pairs)},POINTER)
    print(json.dumps(terminal,sort_keys=True),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=('prepare','run'))
    run(parser.parse_args().phase=='run')
