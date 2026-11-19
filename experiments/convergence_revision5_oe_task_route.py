"""Replay the B6 OpenExempt proposal by task on the archived B7 forward cohort."""

from itertools import product
import json
from pathlib import Path
import sqlite3
from statistics import mean

from experiments.convergence_formal_b1_observe import load_roster
from experiments.convergence_formal_train_fit import M2, OE, ORDINARY, pointer as fit_pointer
from experiments.convergence_formal_train_observe import pointer as observe_pointer
from experiments.convergence_pilot_b0 import BASE, LEDGER, ROOT, read, sha
from experiments.convergence_revision5_cni_nonsolicitation import bound_stage
from experiments.convergence_revision5_oe_m2_source_placement import direct_title_scope, title_conditional_support
from experiments.convergence_revision5_oe_native_amount_bound import amount_guard, clip_claims
from experiments.convergence_revision5_oe_scoped_policy_replay import verify_native
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.paired_interfaces.convergence_oe_public_scope import supplied_jurisdiction_scope
from legal_skill_guard.paired_interfaces.convergence_oe_title_scope import title_inventory
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE/'revision5_OE_B6_task_route_20261119'
FAMILIES = ('EC','EV')
INCUMBENT, PROPOSAL = 'incumbent', 'proposal'
OPTIONS = dict(zip(('incumbent','EV_only','EC_only','whole_proposal'),
                   product((INCUMBENT,PROPOSAL),repeat=2),strict=True))


def route(native, choice):
    return {task:native[role][task] for task,role in zip(FAMILIES,OPTIONS[choice],strict=True)}


def public_controls(view, output):
    scope = supplied_jurisdiction_scope(view['public']['original_input'])
    if scope is None:
        raise ValueError('The archived native view must state its allowed public jurisdictions')
    law = set(scope['citations'])
    if view['id']=='EC':
        return {asset:[c for c in citations if c in law] for asset,citations in output.items()}
    lawful = {asset:[c for c in claims if c['citation'] in law] for asset,claims in output.items()}
    guard = amount_guard(view['public'])
    if guard is None:
        raise ValueError('The public asset-value control must bind to the same native input')
    return clip_claims(lawful,guard)[0]


def aligned_titles(views):
    public = {f:views[f]['public']['original_input'] for f in FAMILIES}
    scope = {f:supplied_jurisdiction_scope(t) for f,t in public.items()}
    if scope['EC']!=scope['EV'] or scope['EC'] is None:
        raise ValueError('The shared eligibility check requires the same public legal regime')
    assets = {f:{a['description']:a for a in title_inventory(t)[1].values()} for f,t in public.items()}
    return {name:tuple(assets[f][name]['filing_interest_established'] for f in FAMILIES)
            for name in assets['EC'].keys() & assets['EV'].keys()
            if assets['EC'][name]['amount_quote']==assets['EV'][name]['amount_quote']}


def conflicts(predictions, titles):
    """Only compare jointly named assets, keeping title evidence local to each read."""
    ec,ev = (predictions[f] for f in FAMILIES)
    for name in ec.keys() & ev.keys() & titles.keys():
        for claim in ev[name]:
            if claim['claim_value']<=0:
                continue
            citation = claim['citation']
            options = (citation in ec[name],True,*titles[name])
            shared = title_conditional_support(*options)
            assert direct_title_scope(*options)==shared
            if not shared:
                yield (name,citation)


def select(calibration, policy_conflicts=None):
    incumbent_conflicts = frozenset() if policy_conflicts is None else policy_conflicts['incumbent']
    choices = [m for m in OPTIONS if policy_conflicts is None or policy_conflicts[m]<=incumbent_conflicts]
    return max(choices,key=lambda m:(calibration[m]['native_mean_F1'],-OPTIONS[m].count(PROPOSAL)))


def source_checked_outputs(bank, findings, keys, route_choice):
    outputs, kept = {}, []
    added_at = {position for position, *_ in findings[route_choice]-findings['incumbent']}
    for position,key in enumerate(keys):
        selected = 'incumbent' if position in added_at else route_choice
        outputs[key] = bank[selected][key]
        if selected!='incumbent':
            kept.append(position)
    return outputs,kept


def metric_rows(views, predictions, labels):
    return [{'source':key,'view':family,'grade':grade_view(OE,views[key][family],labels[key][family],output[family])['grade']}
            for key,output in predictions.items() for family in FAMILIES]


def score(views, bank, labels):
    reference = metric_rows(views,bank['incumbent'],labels)
    scores={}
    for mode,prediction in bank.items():
        values=metric_rows(views,prediction,labels)
        assert all(row['grade'] is not None for row in values)
        scores[mode]={'native_mean_F1':mean(r['grade'] for r in values),
                      'F1':{f:mean(r['grade'] for r in values if r['view']==f) for f in FAMILIES},
                      'paired_vs_incumbent':paired_source_effect(reference,values)}
    return scores


def original_bank():
    fit,frozen,fit_end=bound_stage(fit_pointer(6))
    assert fit_end['batch']==6
    decisions=read(fit/'matched_decisions.json')
    assert digest(decisions)==fit_end['matched_decisions_sha256']
    original=decisions['relation'][OE]
    assert original['status']=='retain_incumbent_on_native_train'
    directory=fit/'candidates'/ORDINARY/OE
    proposal=read(directory/'measurements.json')
    assert digest(proposal['candidate'])==original['matched_proposal_sha256']
    assert digest(proposal['predictions'])==decisions['teacher'][ORDINARY][OE]['predictions_sha256']
    checkpoint=ROOT/frozen['checkpoint_root']
    study=read(checkpoint/'binding.json')
    assert digest(study)==frozen['study_binding_sha256']
    roster=load_roster(study)
    journal=TrainingJournal(checkpoint,study,roster)
    keep=digest(journal.library(M2,5)['programs'][OE]); adopted=digest(proposal['candidate'])
    assert digest(journal.library(M2,6)['programs'][OE])==keep
    assert digest(journal.library(ORDINARY,6)['programs'][OE])==adopted
    refs = {'B6_fit':sha(fit/'terminal.json')}
    built, grade_paths, wires = {},{},set()
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        counts=dict(db.execute('select status,count(*) from calls group by status'))
        assert not counts.get('reserved')
        for batch in (6,7):
            observed,binding,terminal=bound_stage(observe_pointer(batch))
            refs[f'B{batch}_observe']=sha(observed/'terminal.json')
            grades=binding['native_grade_paths'][OE]
            assert 'train' in Path(grades).parts
            grade_paths[grades]=binding['native_grade_sha256'][grades]
            cohort=[s for s in roster[batch-1] if s['dataset']==OE]
            assert len(cohort)==4 and all(s['project_split']=='train' for s in cohort)
            views, raw_bank, public_bank = {},{m:{} for m in OPTIONS},{m:{} for m in OPTIONS}
            discrepancy = {m:set() for m in OPTIONS}
            for pos,source in enumerate(cohort):
                key=source['key']
                views[key]={v['id']:v for v in source['views']}
                native={}
                for role,arm,h in ((INCUMBENT,M2,keep),(PROPOSAL,ORDINARY,adopted)):
                    if batch==6 and role==PROPOSAL:
                        result=proposal['predictions'][key]
                    else:
                        receipt=journal._observations(arm,batch)
                        assert receipt['train_observation_sha256']==terminal['observation_receipts'][arm]
                        row=read(journal.directory(arm,batch)/'predictions'/(digest(key)+'.json'))
                        assert digest(row)==receipt['predictions'][key]
                        result=row['result']
                    verify_native(db,source,result,h,wires)
                    native[role]={f:result['native'][f]['answer'] for f in FAMILIES}
                titles=aligned_titles(views[key])
                assert titles
                for m in OPTIONS:
                    outputs=route(native,m)
                    checked={f:public_controls(views[key][f],outputs[f]) for f in FAMILIES}
                    raw_bank[m][key]=outputs
                    public_bank[m][key]=checked
                    discrepancy[m].update((pos,*w) for w in conflicts(checked,titles))
            built[batch]={'views':views,'raw':raw_bank,'common_controls':public_bank,'conflicts':discrepancy}
    assert len(grade_paths)==1
    (grade,h),=grade_paths.items()
    assert sha(ROOT/grade)==h
    return built,ROOT/grade,refs,{'physical_responses':len(wires),'ledger':counts},(keep,adopted)


def run():
    for status in product((None,False,True),repeat=4):
        assert title_conditional_support(*status)==direct_title_scope(*status)
    book,grade,refs,metadata,programs=original_bank()
    lock={'scope':'chronological_replay_B6_calibration_B7_original_forward_TRAIN',
          'runner_sha256':sha(Path(__file__)),'sealed_terminals':refs,'original_program_sha256':list(programs),
          'native_grade_sha256':sha(grade),'joint_formula_equivalent_to_direct_control':True,
          'training_selection':'Select the maximal mean of two official task F1 scores on B6, retain prior conflicts at most.'}
    out=HOME/digest(lock)
    immutable_json(out/'binding.json',lock)
    labels=read(grade)
    before=book[6]
    train_scores={m:score(before['views'],before[m],labels) for m in ('raw','common_controls')}
    chosen={m:select(s) for m,s in train_scores.items()}
    chosen['shared_checked_with_common_controls']=select(train_scores['common_controls'],before['conflicts'])
    immutable_json(out/'calibrated_routes.json',chosen)
    later=book[7]
    red_route, kept = source_checked_outputs(later['common_controls'],later['conflicts'],list(later['views']),
                                             chosen['shared_checked_with_common_controls'])
    immutable_json(out/'B7_source_checked_route.json',red_route)
    for batch,cohort in book.items():
        immutable_json(out/f'B{batch}_predictions.json',{
            'raw':cohort['raw'],'common_controls':cohort['common_controls'],
            'source_conflicts':{m:sorted(d) for m,d in cohort['conflicts'].items()}})
    forward={m:score(later['views'],later[m],labels) for m in ('raw','common_controls')}
    forward['common_controls'].update({k:v for k,v in score(later['views'],{
        'incumbent':later['common_controls']['incumbent'],'B7_source_checked_route':red_route},labels).items()
        if k!='incumbent'})
    counts={f'B{b}':{m:{'conflicts':len(v),'new_vs_incumbent':len(v-c['conflicts']['incumbent'])}
                    for m,v in c['conflicts'].items()} for b,c in book.items()}
    result={'status':'settled_B6_OpenExempt_task_route_B7_forward_replay',
            'TRAIN_calibration_B6':train_scores,'frozen_B6_choices':chosen,'TRAIN_forward_B7':forward,
            'conflict_counts':counts,'matched_direct_guard_applies_same_title_test':True,
            'B7_source_route_replay':{'proposal_routed_positions':kept,'retrospective':True,
                                      'needs_incumbent_predictions_and_proposal_EC_per_source':True,
                                      'predictions_sha256':sha(out/'B7_source_checked_route.json')},
            'physical_responses_verified':metadata['physical_responses'],'new_requests':0,'ledger':metadata['ledger'],
            'native_training_or_library_changed':False,'TEST_opened':False,
            'prediction_sha256':{f'B{b}':sha(out/f'B{b}_predictions.json') for b in book}}
    immutable_json(out/'terminal.json',result)
    print(json.dumps({'artifact_root':str(out.relative_to(ROOT)),**result},sort_keys=True),flush=True)


if __name__=='__main__':
    run()
