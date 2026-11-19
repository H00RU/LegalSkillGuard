"""Compare fixed and consumer-derived designation reads on source-bound routes."""

import inspect
from itertools import product
import json
from pathlib import Path
import re
import sqlite3

from experiments.convergence_revision5_cni_designation import (
    ARM, C, DATASET, E, LEDGER, ROOT, TASK, TrainingJournal,
    DONE as OLD_DONE, POINTER as OLD_POINTER, layouts as old_layouts,
    load_roster, physical_prediction, pointer, read, sha, spans_for,
)
from experiments.convergence_revision5_cni_designation_control import direct as definition_control, verified_read
from experiments.convergence_pilot_b0 import BASE, HANDOFF, write_status
from legal_skill_guard.paired_interfaces import residual
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE/'revision5_CNI_designation_routes_20261119'
POINTER = HANDOFF/'revision5_CNI_designation_routes_current.json'
ROLES = ('fixed', 'synthesized')
DONE = 'settled_CNI_matched_designation_routes_TRAIN_replay'
APPLIES = 'governs_original_qualification'
REQUIRES = 'express_designation_necessary_on_route'
MEANINGS = {
    APPLIES: 'the original span group gives an operative way for original information to qualify or expressly governs its qualification',
    REQUIRES: 'original information on this one route must be expressly marked or identified by its discloser. '
              'Use false if the cited wording permits an alternative path or otherwise protects a stated class without marking. '
              'An or between two independently marked modalities leaves the requirement intact within each modality. '
              'Leave resolution null where another condition is needed to determine whether the route requires a mark',
}
# A source-only review of the original documents binds local clauses to their
# lead-ins. Complete route inventories are needed only for universal claims.
# B6 contributes two documents outside the earlier paired study. The later
# TRAIN positions serve as a retrospective chronological comparison.
ANCHORS = {
    (3, 1): ('calibration', False, ((2, 5), (7,)), (C, C)),
    (5, 1): ('calibration', True, ((10, 11), (10, 12)), (E, E)),
    (6, 0): ('forward', True, ((14,),), (E,)),
    (6, 1): ('forward', False, ((18, 19), (18, 20), (18, 21)), (C, C, C)),
    (8, 0): ('forward', False, ((12,),), (C,)),
    (8, 2): ('forward', False, ((7, 8), (7, 9)), (C, C)),
}
def local_consumer(v, _):
    return {
        'open_route': (v['governs_original_qualification'] == True and v['express_designation_necessary_on_route'] == False),
        'gated_route': (v['governs_original_qualification'] == True and v['express_designation_necessary_on_route'] == True),
    }


def consume_world(v, context):
    domains = [(v[field],) if v[field] is not None else (False, True) for field in MEANINGS]
    completed = [local_consumer(dict(zip(MEANINGS, pair, strict=True)), context)
                 for pair in product(*domains)]
    return {port: completed[0][port] if all(row[port] == completed[0][port] for row in completed) else None
            for port in completed[0]}


def compile_layouts():
    procedure = inspect.getsource(local_consumer)
    domains = {key: [True, False, None] for key in MEANINGS}
    scope = {'source_fields': ['source_text'], 'local_unit': 'one anchored qualification route', 'field_meanings': MEANINGS}
    scaffold = residual.FiniteModule.build('route_dependencies', domains, [{}], local_consumer,
                                           consumer_sha256=digest(procedure), source_scope=scope, program_source=procedure)
    selected = []
    for feature in residual.consumer_relations(scaffold):
        expr = feature['expression']
        if expr['op'] != 'and' or set(feature['consumer_dependencies']) != set(domains):
            continue
        comparison, = (r for r in expr['args'] if residual.expression_fields(r) == {REQUIRES})
        requires, = (r['value'] for r in comparison['args'] if r['op'] == 'constant')
        selected.append({**feature, 'name': 'gated_route' if requires else 'open_route'})
    assert {r['name'] for r in selected} == {'open_route', 'gated_route'} and len(selected) == 2
    context = {}
    consumer = residual.FiniteModule.build('CNI_anchored_qualification_route', domains, [context], consume_world,
                                          consumer_sha256=digest([procedure, inspect.getsource(consume_world)]), source_scope=scope)
    fixed = [{'name': f, 'field': f, 'operation': 'field'} for f in domains]
    assets = [residual.compile_pair(consumer, fields, operation=operation, layout='anchored')
              for fields, operation in ((fixed, 'fixed_coordinates'), (selected, 'consumer_relational_projection'))]
    for state in consumer.states:
        for asset in assets:
            actual = residual.decode(asset, residual.encode(asset['features'], state), context, module_binding=consumer.binding)
            assert actual['valid'] and actual['outputs'] == consume_world(state, context)
    return consumer, context, dict(zip(ROLES, assets, strict=True))


def compose(routes, anchors, complete):
    open_anchors = [group for route, group in zip(routes, anchors, strict=True) if route['open_route'] is True]
    if open_anchors:
        return {'answer': C, 'evidence': list(min(open_anchors, key=lambda group: (len(group), group)))}
    if complete and all(route['open_route'] is False and route['gated_route'] is not None for route in routes):
        evidence = {i for route, group in zip(routes, anchors, strict=True) if route['gated_route'] is True for i in group}
        if evidence:
            return {'answer': E, 'evidence': sorted(evidence)}
    return {'answer': None, 'evidence': []}


MARK = re.compile(r'\bis (?:marked|identified as confidential|designated as confidential)\b.*', re.I)
EXPLICIT_OPEN = re.compile(r'or from all the relevant circumstances|or should be deemed by its nature|'
                           r'or otherwise disclosed in a manner consistent|whether or not it is designated as', re.I)
DIRECT_DEFINITION = re.compile(
    r'Confidential Information["”\']?(?:,\s*whenever used in this Agreement,)?\s+(?:(?:shall|will)\s+)?(?:means?|includes?)\b', re.I)


def direct(case):
    """Apply the same attached source groups to an explicit clause-pattern control."""
    values = []
    for group in case['anchor_spans']:
        texts = [' '.join(r['text'].split()) for r in group]
        first, tail = texts[0], texts[-1]
        has_gate = bool(MARK.search(tail))
        if EXPLICIT_OPEN.search(tail):
            values.append({'open_route': True, 'gated_route': False})
        elif has_gate and DIRECT_DEFINITION.search(first):
            values.append({'open_route': False, 'gated_route': True})
        elif (not has_gate and DIRECT_DEFINITION.search(first)
              and re.search(r'\b(?:all|any)\b', first, re.I)
              and not re.search(r'\b(?:except where|only if|which$|subject to)\b', first, re.I)):
            values.append({'open_route': True, 'gated_route': False})
        else:
            values.append({'open_route': None, 'gated_route': None})
    return compose(values, case['anchors'], case['complete_routes'])


def materials(contract):
    stage = ROOT/read(pointer(3))['artifact_root']
    prior_binding = read(stage/'binding.json')
    checkpoint = ROOT/prior_binding['checkpoint_root']
    study = read(checkpoint/'binding.json')
    roster = load_roster(study)
    train_keys = {s['key'] for batch in roster for s in batch if s['dataset'] == DATASET}
    journal = TrainingJournal(checkpoint, study, roster)
    cases, verified, snapshots = [], set(), {}
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro', uri=True) as db:
        for (batch, idx), (role, complete, anchors, expected) in ANCHORS.items():
            source = [s for s in roster[batch-1] if s['dataset'] == DATASET][idx]
            assert source['project_split'] == 'train'
            key = source['key']
            view, = (v for v in source['views'] if v['id'] == TASK)
            spans = spans_for(view)
            history = journal._observations(ARM, batch)
            snapshot = ROOT/read(pointer(batch))['artifact_root']
            snapshot_binding = read(snapshot/'binding.json')
            terminal = read(snapshot/'terminal.json')
            assert snapshot.name == digest(snapshot_binding)
            assert not terminal['TEST_opened'] and terminal['observation_receipts'][ARM] == history['train_observation_sha256']
            if str(batch) not in snapshots:
                assert all(sha(snapshot/'source_snapshot'/p)==h for p,h in snapshot_binding['source_sha256'].items())
                snapshots[str(batch)] = sha(snapshot/'terminal.json')
            old = read(journal.directory(ARM, batch)/'predictions'/(digest(key)+'.json'))
            assert history['predictions'][key] == digest(old)
            start = physical_prediction(db, train_keys, key, old, view, verified)
            anchor_spans = [[{'span_id': i, 'text': spans[i]} for i in group] for group in anchors]
            cases.append({'source': key, 'view': view, 'position': [batch, idx], 'role': role,
                          'anchors': [list(a) for a in anchors], 'anchor_spans': anchor_spans, 'complete_routes': complete,
                          'reviewed_route_labels': list(expected), 'original': start})
    assert len(verified) == len(cases)
    grade = prior_binding['native_grade_paths'][DATASET]
    assert '/train/' in grade
    old = ROOT/read(OLD_POINTER)['artifact_root']
    files = (str(Path(__file__).relative_to(ROOT)), 'legal_skill_guard/paired_interfaces/residual.py',
             'experiments/convergence_revision5_cni_designation.py', 'experiments/convergence_revision5_m2_cumulative_audit.py',
             'experiments/convergence_revision5_cni_designation_control.py', 'legal_skill_guard/skill_evolution/native.py')
    binding = {'study': 'CNI_same_definition_designation_routes', 'split': 'TRAIN', 'cases_sha256': digest(cases),
               'executor': study['executor'], 'grade_path': grade, 'grade_sha256': prior_binding['native_grade_sha256'][grade],
               'original_observation_terminals': snapshots, 'prior_paired_terminal_sha256': sha(old/'terminal.json'),
               'source_hashes': {f: sha(ROOT/f) for f in files}, 'proof_states': len(contract[0].states),
               'candidate_ids': {role: a['version'] for role, a in contract[2].items()}}
    return binding, cases


def score(cases, bank, binding):
    grade_path = ROOT/binding['grade_path']
    assert sha(grade_path) == binding['grade_sha256']
    labels = read(grade_path)
    scores = []
    for case, record in zip(cases, bank, strict=True):
        roles = {}
        for role, row in record.items():
            info = grade_view(DATASET, case['view'], labels[case['source']][TASK], row['answer'], row['evidence'])
            roles[role] = {'answer': row['answer'], 'exact': info['grade'], 'evidence_F1': info['evidence_f1'],
                           'source_matches': row['answer']==case['reviewed_route_labels'][0]}
        scores.append({'position': case['position'], 'selection_role': case['role'], 'roles': roles,
                       'benchmark_answer': labels[case['source']][TASK]['answer'], 'route_count': len(case['anchors'])})
    return scores


def run():
    contract = compile_layouts()
    binding, cases = materials(contract)
    stage = HOME/digest(binding)
    immutable_json(stage/'binding.json', binding)
    immutable_json(stage/'cases.json', cases)
    if (stage/'terminal.json').exists():
        print(json.dumps({'artifact_root':str(stage.relative_to(ROOT)),**read(stage/'terminal.json')}, sort_keys=True), flush=True)
        return
    older = ROOT/read(OLD_POINTER)['artifact_root']
    old_binding = read(older/'binding.json')
    assert older.name == digest(old_binding) and read(older/'terminal.json')['status'] == OLD_DONE
    assert all(sha(older/'source_snapshot'/p)==h for p,h in old_binding['source_sha256'].items())
    old_cases = read(older/'cases.json')
    assert digest(old_cases) == old_binding['cases_sha256']
    old_pairs = dict(zip((c['source'] for c in old_cases), read(older/'paired_reads.json'), strict=True))
    old_cases = {c['source']:c for c in old_cases}
    assets = dict(zip(ROLES, old_layouts()[1], strict=True))
    assert [a['version'] for a in assets.values()] == old_binding['candidate_versions']

    bank, settings, ids = [], {}, set()
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro', uri=True) as db:
        for case in cases:
            key = case['source']
            record = {'original': case['original'], 'direct_anchored_control': direct(case),
                      'prior_direct_control': definition_control(case['view'])}
            if key in old_pairs:
                assert old_cases[key]['view'] == case['view']
                for role, asset in assets.items():
                    previous = old_pairs[key][role]
                    identity = previous['physical_call_id']
                    verified_read(db,identity,asset,old_cases[key],previous,settings)
                    record['prior_'+role] = previous
                    ids.add(identity)
            bank.append(record)
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
        assert not ledger.get('reserved')
    immutable_json(stage/'predictions.json', bank)
    comparisons = score(cases, bank, binding)
    disputed = [r['benchmark_answer'] for r in comparisons
                if not r['roles']['direct_anchored_control']['exact'] and r['roles']['direct_anchored_control']['source_matches']]
    terminal = {'status': DONE, 'partition': 'TRAIN', 'new_executor_calls': 0, 'new_teacher_calls': 0,
                'verified_original_actor_responses': len(cases), 'verified_prior_interface_responses': len(ids),
                'comparison': comparisons, 'original_TEST_opened': False, 'ledger': ledger,
                'generated_layout_received_new_reads': False,
                'benchmark_disagreements_with_source_confirmed_direct_control': disputed,
                'predictions_sha256': sha(stage/'predictions.json')}
    immutable_json(stage/'terminal.json', terminal)
    write_status(stage, {'status': DONE, 'new_executor_calls': 0}, POINTER)
    print(json.dumps({'artifact_root':str(stage.relative_to(ROOT)),**terminal}, sort_keys=True), flush=True)


if __name__ == '__main__':
    run()
