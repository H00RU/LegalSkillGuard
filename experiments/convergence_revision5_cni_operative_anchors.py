"""Test shared operative-event anchors with fixed and synthesized CNI readers."""

import argparse
from collections import defaultdict
from copy import deepcopy
import json
from pathlib import Path
import re
import sqlite3

from experiments.convergence_cni_bundle_probe import POINTER as PRIOR
from experiments.convergence_cni_disclosure_probe import SOURCE_REVIEWS
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import cni_disclosure_relational as disclosure
from legal_skill_guard.paired_interfaces import indexed_relational_read as indexed
from legal_skill_guard.paired_interfaces import residual
from legal_skill_guard.paired_interfaces.cni_disclosure_mentions import MENTION_INSTRUCTIONS, mention_windows
from legal_skill_guard.paired_interfaces.formal_actors import InterfaceActor
from legal_skill_guard.paired_interfaces.production_decode import decode_response
from legal_skill_guard.paired_interfaces.relational_program import template_version
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


POINTER = HANDOFF / 'revision5_CNI_operative_anchors_current.json'
HOME = BASE / 'revision5_CNI_operative_anchors_20261119'
DONE = 'completed_revision5_CNI_operative_anchors_TRAIN'
MODAL_DISTRIBUTION = re.compile(
    r'\b(?:may|shall|must|will|can)\s+(?:not\s+)?(?:be\s+)?'
    r'(?:disclos\w*|shar\w*|divulg\w*|restrict\s+access)\b', re.I,
)
ELLIPTICAL_DISTRIBUTION = re.compile(
    r'\b(?:shall|must)\s+be\s+to\s+hold\s+and\s+maintain\s+the\s+Confidential\s+Information\b'
    r'.*?\band\s+to\s+their\b.*?\bneed\s+to\s+know\b', re.I | re.S,
)


def operative_anchors(public):
    """Declare literal event sites without assigning an actor, audience or legal outcome."""
    text = public['source_text']
    native_spans = public['sentence_spans']
    anchors = {}
    for anchor, (start, end) in disclosure.clause_ranges(public).items():
        first, last = map(int, anchor[1:].split('_'))
        same_span = first == last
        modal_scope = text[start:native_spans[first][1]]
        tail_start = start if same_span else native_spans[last][0]
        recipient_scope = text[tail_start:end]
        if not same_span and not modal_scope.rstrip().endswith(':'):
            continue
        match = MODAL_DISTRIBUTION.search(modal_scope)
        if match is None and same_span:
            match = ELLIPTICAL_DISTRIBUTION.search(modal_scope)
        if match is None or not disclosure.RECIPIENT.search(recipient_scope):
            continue
        a, b = match.span()
        anchors[anchor] = {'range': [start, end], 'event_cue': {'start': start+a, 'end': start+b,
                                                                'text': text[start+a:start+b]}}
    return anchors


def limited_view(source, measured):
    target, = (v for v in source['views'] if v['id'] == disclosure.TASK)
    selected = {**source, 'views': [target]}
    public = target['public']
    full = measured['bundle']['local_view']
    sites = operative_anchors(public)
    if not sites:
        raise ValueError('The narrow pilot requires at least one licensed event site in every source')
    ranges = {name: slot['range'] for name, slot in sites.items()}
    source_text = public['source_text']
    bounded = deepcopy(full)
    bounded['relational_public_source']['indexed_ranges'] = ranges
    bounded['read_input']['source_text'] = source_text
    bounded['read_input']['participant_mentions'] = mention_windows(source_text, ranges)
    bounded['read_input']['operative_event_cues'] = [
        {'id': name, **slot['event_cue']} for name, slot in sites.items()]
    bounded['read_input']['indexed_evidence'] = [
        {'id': name, 'text': source_text[start:end]} for name, (start,end) in ranges.items()]
    for plan in bounded['plans']:
        program = plan['relational_program']
        evidence = indexed.bind(program, bounded['relational_public_source'])
        plan['indexed_evidence_binding'] = evidence
        plan['schema'] = indexed.reader_schema(program, evidence, factorized=True)
        plan['system'] = (indexed.instructions(program) + '\n' + MENTION_INSTRUCTIONS
                          + '\nThe indexed spans point to candidate distribution events and do not show by themselves '
                            'who is permitted to receive the information. Resolve the actor, audience and force within '
                            'one listed event. Use the complete source for context. Use unread where the listed event '
                            'does not suffice.')
        plan['reader_template_sha256'] = template_version(
            program, system=plan['system'], public_rules='same-event source anchor',
            protocol='cni_operative_event_site_factorized_v1')
        plan['version'] = digest({k:v for k,v in plan.items() if k!='version'})
    return selected, bounded


def materials():
    parent = ROOT / read(PRIOR)['artifact_root']
    prior = read(parent/'binding.json')
    historical = read(parent/'terminal.json')
    original = read(parent/'cases.json')
    if (parent.name != digest(prior) or digest(original) != prior['cases_sha256']
            or historical['status'] != 'completed' or len(original) != 4):
        raise ValueError('Use the original locked four-source native TRAIN comparison')
    archive_count = 0
    for name, version in prior['source_sha256'].items():
        if sha(parent/'source_snapshot'/name) != version:
            raise ValueError('The measured prior candidate source snapshot changed')
        archive_count += 1
    if sha(ROOT/prior['grading_path']) != prior['grading_sha256']:
        raise ValueError('Use the original TRAIN grading file')
    cases = []
    comparison = defaultdict(list)
    original_predictions = []
    for entry in original:
        source = entry['source']
        key = source['key']
        if source['project_split'] != 'train':
            raise ValueError('Use only TRAIN')
        selected, view = limited_view(source, entry)
        anchors = view['relational_public_source']['indexed_ranges']
        anchor, recipient = SOURCE_REVIEWS[key[-8:]]
        if anchor not in anchors:
            raise ValueError('The shared anchor grammar must preserve the original independent source review')
        expected = 'Entailment' if recipient == 'own_employees' else None
        for role, new, old in zip(('fixed','synthesized'),view['plans'],entry['bundle']['plans'],strict=True):
            program = new['relational_program']
            if program != old['local_plan']['relational_program']:
                raise ValueError('Only the anchor representation changes')
            _, unit = indexed.indexed_unit(program)
            values = residual.encode(unit['asset']['features'], {
                'disclosure_actor': 'receiver', 'recipient_group': recipient, 'permission_force': 'allow'})
            encoded = '|'.join([anchor, *(indexed.symbol(value) for value in values.values())])
            review = decode_response(selected, view, new,
                                     {'content':json.dumps(encoded),'finish_reason':'stop'})
            if review['production_errors'] or review['native'][disclosure.TASK]['answer'] != expected:
                raise ValueError('The indexed relation must retain reviewed meaning and unknown')
            sealed = read(parent/'predictions'/(digest([key,role])+'.json'))
            original_predictions.append(sealed)
            pred = sealed['result']['native'][disclosure.TASK]
            comparison[role].append(pred)
        cases.append({'source':selected, 'view':view, 'anchor_review':anchor,
                      'known_local_support':recipient == 'own_employees',
                      'native_span_sizes':[len(entry['bundle']['local_view']['relational_public_source']['indexed_ranges']),
                                           len(anchors)]})
    if read(parent/'prediction_seal.json')['predictions_sha256']!=digest(original_predictions):
        raise ValueError('The original physical prediction seal changed')
    current = str(Path(__file__).resolve().relative_to(ROOT))
    paths = {*prior['source_sha256'],current}
    binding = {'study':'revision5_CNI_operative_event_anchors_same_information',
               'previous_complete_TRAIN_binding':parent.name, 'previous_terminal_sha256':sha(parent/'terminal.json'),
               'previous_source_snapshot_files_verified':archive_count,
               'case_pairs_sha256':digest(cases), 'executor':prior['executor'],
               'grading_path':prior['grading_path'], 'grading_sha256':prior['grading_sha256'],
               'source_sha256':{f:sha(ROOT/f) for f in sorted(paths)},
               'planned_executor_calls':8,'TRAIN_mothers':len(cases),
               'target_native_hypothesis':disclosure.TASK,
               'native_and_evidence_unconditional_on_answer_coverage':True, 'TEST_opened':False}
    return binding, cases, comparison


def scored(case, gold, prediction):
    task, = case['source']['views']
    ids = prediction['evidence_sentence_ids']
    s = grade_view('ContractNLI',task,gold,prediction['answer'], ids)
    start, end = map(int, case['anchor_review'][1:].split('_'))
    supported = (case['known_local_support'] and prediction['answer']=='Entailment'
                 and set(range(start,end+1))<=set(ids))
    return {'native_correct':int(s['grade']), 'evidence_f1':s['evidence_f1'],
            'supported_entailment':supported, 'resolved':prediction['answer'] is not None}


def summary(rows):
    n = len(rows)
    return {'mothers':n,'native_correct':sum(x['native_correct'] for x in rows),
            'evidence_f1':sum(x['evidence_f1'] for x in rows)/n,
            'source_bound_entailments':sum(x['supported_entailment'] for x in rows),
            'resolved':sum(x['resolved'] for x in rows)}


def run(execute):
    if POINTER.exists() and read(POINTER)['status']==DONE:
        print(read(POINTER)['artifact_root'],flush=True)
        return
    b,cases,prior = materials()
    stage = HOME/digest(b)
    if execute and (not POINTER.exists() or ROOT/read(POINTER)['artifact_root']!=stage):
        raise ValueError('Use the prepared comparison binding')
    immutable_json(stage/'binding.json',b)
    immutable_json(stage/'cases.json',cases)
    if not execute:
        if POINTER.exists() and read(POINTER)['status']=='running':
            raise ValueError('Preserve the active run')
        write_status(stage,{'status':'prepared','planned_executor_calls':8},POINTER)
        print(json.dumps({'stage':str(stage.relative_to(ROOT)),'anchor_sizes':[x['native_span_sizes'] for x in cases]}),
              flush=True)
        return
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        if db.execute("select 1 from calls where status='reserved'").fetchone():
            raise ValueError('Reconcile the previous physical call before dispatch')
    for name, version in b['source_sha256'].items():
        destination = stage/'source_snapshot'/name
        destination.parent.mkdir(parents=True,exist_ok=True)
        if not destination.exists():
            with destination.open('xb') as file:
                file.write((ROOT/name).read_bytes())
        if sha(destination)!=version:
            raise ValueError('Archive each exact bound implementation before dispatch')
    keys = [c['source']['key'] for c in cases]
    run_id = 'convergence-revision5-CNI-event-'+stage.name[:16]
    ledger = EvolutionLedger(LEDGER,run_id=run_id,sources={'train':keys,'dev':[],'test':[]},binding=b)
    executor = FrozenExecutor(ledger,stage,b['executor'])
    executor.readiness()
    actor = InterfaceActor(executor,stage,plan_assets={},source_inputs=None,pipeline_binding=b['source_sha256'])
    results = defaultdict(list)
    write_status(stage,{'status':'running','completed_pairs':0},POINTER)
    for i,c in enumerate(cases):
        for role,plan in zip(('fixed','synthesized'),c['view']['plans'],strict=True):
            out = actor.measure(c['source'],c['view'],plan,'skill_actor')
            results[role].append(out)
        write_status(stage,{'status':'running','completed_pairs':i+1},POINTER)
    immutable_json(stage/'native_reads.json',dict(results))
    labels = read(ROOT/b['grading_path'])
    metrics = {}
    for role,rows in results.items():
        scores = []
        old_scores = []
        for case,result,already in zip(cases,rows,prior[role],strict=True):
            grade = labels[case['source']['key']][disclosure.TASK]
            scores.append(scored(case,grade,result['native'][disclosure.TASK]))
            old_scores.append(scored(case,grade,already))
        metrics[role] = {'restricted_anchors':summary(scores),'original_complete_bundle':summary(old_scores),
                         'paired_native_rows':scores,
                         'production_errors':sum(bool(row['production_errors']) for row in rows)}
    with ledger.transaction() as db:
        physical = db.execute('select status,result from calls where id like ?', (run_id+':%',)).fetchall()
    if len(physical)!=b['planned_executor_calls'] or any(status!='completed' for status,_ in physical):
        raise ValueError('Seal only the eight actual reads of the matched comparison')
    done = {'status':DONE,'same_complete_public_TRAIN_documents_in_both_arms':True,
            'native_hypothesis':disclosure.TASK,'metrics':metrics,'executor_calls':len(physical),
            'executor_tokens':sum(json.loads(v)['usage']['total_tokens'] for _,v in physical),
            'new_teacher_calls':0,'TEST_and_DEV_opened':False}
    immutable_json(stage/'terminal.json',done)
    write_status(stage,{'status':DONE,'physical_reads':len(physical)},POINTER)
    print(json.dumps(done,sort_keys=True),flush=True)


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=('prepare','run'))
    run(parser.parse_args().phase=='run')
