"""Formal ContractNLI M1 learning and forward matched evaluation over fixed TRAIN/DEV."""

import argparse
from copy import deepcopy
import inspect
from pathlib import Path

from experiments import convergence_revision5_cni_operative_anchors as prior
from experiments import convergence_revision5_release_dev as release
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import cni_disclosure_relational as relation
from legal_skill_guard.paired_interfaces import convergence_cni_bundle, convergence_training, residual
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.formal_actors import InterfaceActor
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.paired_interfaces.formal_training import RelationalInterfaceLibrary
from legal_skill_guard.paired_interfaces.production_decode import decode_response
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest

HOME = BASE / 'revision6_formal_contract_M1'
POINTER = HANDOFF / 'revision6_formal_contract_M1_current.json'
DATASET, TASK = 'ContractNLI', relation.TASK


class ContractProvider:
    """The same clause/participant wire for calibration, fixed control, and DEV."""

    def __init__(self, historical_template):
        self.historical_template = historical_template

    def build(self, source):
        native = next(v for v in source['views'] if v['id'] == TASK)
        if source['dataset'] != DATASET or source['project_split'] not in ('train', 'dev'):
            raise ValueError('The new contract reader uses only TRAIN or DEV')
        if not prior.operative_anchors(native['public']):
            return None
        template = deepcopy(self.historical_template)
        existing = template['bundle']['local_view']
        existing['source'] = source['key']
        existing['relational_public_source']['source_text'] = native['public']['source_text']
        existing['read_input']['hypothesis'] = native['public']['question']
        selected, view = prior.limited_view(source, template)
        for plan in view['plans']:
            plan['source_public_sha256'] = digest(selected)
            plan['version'] = digest({k: v for k, v in plan.items() if k != 'version'})
        return selected, view

    def verify_plan(self, source, view, plan):
        if (digest(source) != plan['source_public_sha256'] or view['source'] != source['key']
                or digest({k: v for k, v in plan.items() if k != 'version'}) != plan['version']):
            raise ValueError('The selected contract interface lost its source or template binding')


def sources():
    _, study, batches = release.cni.base.archive.archive_context()
    dev, _, checked, _ = release.formal.common.archive()
    if checked != study:
        raise ValueError('Bind the same original TRAIN and DEV study')
    history = ROOT / read(prior.POINTER)['artifact_root']
    binding = read(history / 'binding.json')
    cases = read(history / 'cases.json')
    end = read(history / 'terminal.json')
    if (digest(binding) != history.name or digest(cases) != binding['case_pairs_sha256']
            or end['status'] != prior.DONE or end['TEST_and_DEV_opened'] is not False
            or any(sha(history / 'source_snapshot' / p) != h for p, h in binding['source_sha256'].items())):
        raise ValueError('Use the verified original independent TRAIN source reviews')
    reviewed = {c['source']['key']: c for c in cases}
    return study, batches, [s for s in dev if s['dataset'] == DATASET], history, binding, reviewed


def audit(case):
    key = case['source']['key']
    anchor, recipient = prior.SOURCE_REVIEWS[key[-8:]]
    if anchor != case['anchor_review']:
        raise ValueError('The retained independent participant review changed')
    first, last = map(int, anchor[1:].split('_'))
    evidence = {TASK: list(range(first, last + 1))}
    return {relation.UNIT: {
        'module': relation.module(),
        'admissible_states': [{'disclosure_actor': 'receiver', 'recipient_group': recipient,
                               'permission_force': 'allow'}],
        'provenance': [{'kind': 'independent_source_audit', 'evidence_sha256': digest({
            'source': digest(case['source']), 'anchor': anchor, 'recipient': recipient,
        })}],
        'native_evidence_ids': evidence if recipient == 'own_employees' else {},
    }}


def prepare():
    study, batches, dev, history, audit_binding, reviewed = sources()
    original_stage = ROOT / read(prior.PRIOR)['artifact_root']
    original_cases = read(original_stage/'cases.json')
    if (sha(original_stage/'terminal.json') != audit_binding['previous_terminal_sha256']
            or digest(original_cases) != read(original_stage/'binding.json')['cases_sha256']):
        raise ValueError('Use the reader template underlying the verified historical wire')
    provider = ContractProvider(original_cases[0])
    cohort = [s for batch in batches for s in batch if s['key'] in reviewed]
    if set(reviewed) != {s['key'] for s in cohort}:
        raise ValueError('Reviewed contracts left the official TRAIN population')
    views = {'train': {}, 'dev': {}}
    for part, rows in (('train', cohort), ('dev', dev)):
        for s in rows:
            if part == 'train':
                matching = reviewed[s['key']]
                if next(v for v in s['views'] if v['id'] == TASK) != matching['source']['views'][0]:
                    raise ValueError('The official TRAIN document differs from the reviewed native view')
                s = matching['source']
            if (built := provider.build(s)) is not None:
                selected, view = built
                if part == 'train' and (selected != reviewed[s['key']]['source'] or view != reviewed[s['key']]['view']):
                    raise ValueError('TRAIN calibration must reproduce the exact archived request')
                views[part][s['key']] = {'source': selected, 'view': view}
    if len(views['train']) != len(reviewed):
        raise ValueError('A reviewed source lost its eligible contract event')
    conditions = {tuple(p['reader_template_sha256'] for p in c['view']['plans'])
                  for cases in views.values() for c in cases.values()}
    if len(conditions) != 1:
        raise ValueError('Reuse the same reader template on subsequent mothers')
    modules = (prior, relation, convergence_cni_bundle, convergence_training, residual)
    paths = [Path(__file__).resolve(), *(Path(m.__file__) for m in modules),
             Path(inspect.getfile(decode_response)), Path(inspect.getfile(InterfaceActor)),
             Path(inspect.getfile(RelationalInterfaceLibrary)), Path(inspect.getfile(FrozenExecutor))]
    code = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    parent, terminal, _ = release.stage(release.POINTER)
    spec = {'stage': 'revision6_formal_contract_interface', 'executor': study['executor'],
            'revision6_authority': read(HANDOFF/'continuation_revision6_authority_20261119.json')['commit'],
            'parent_B8_DEV': terminal['terminal_sha256'], 'review_terminal_sha256': sha(history/'terminal.json'),
            'original_cni_TRAIN_grade_sha256': audit_binding['grading_sha256'],
            'views_sha256': digest(views), 'source_sha256': code,
            'TRAIN_mothers': len(views['train']), 'DEV_mothers': len(dev),
            'DEV_eligible': len(views['dev']), 'TEST_opened': False}
    out = HOME / digest(spec)
    return out, spec, views, provider, study, batches, dev, history, reviewed, parent, terminal


def native_score(source, prediction, labels):
    native = next(v for v in source['views'] if v['id'] == TASK)
    return grade_view(DATASET, native, labels[source['key']][TASK], prediction.get('answer'),
                      prediction.get('evidence_sentence_ids', []))


def compare(cohort, bank, labels):
    rows = {}
    for arm, outputs in bank.items():
        rows[arm] = [{'source': s['key'], 'view': TASK, **native_score(s, outputs[s['key']], labels)}
                     for s in cohort]
    return {name: {'correct': sum(t['grade'] for t in cells), 'evidence_f1': sum(t['evidence_f1'] for t in cells)/len(cells),
                   'paired_vs_fixed': paired_source_effect(rows['fixed'], cells)}
            for name, cells in rows.items()}


def run(execute=False):
    out, spec, views, provider, study, batches, dev, history, reviewed, parent, terminal = prepare()
    immutable_json(out/'binding.json', spec)
    immutable_json(out/'candidate_views.json', views)
    if (out/'terminal.json').exists():
        print(out, flush=True)
        return
    if not execute:
        write_status(out, {'status':'prepared', 'DEV_eligible':spec['DEV_eligible']}, POINTER)
        print(out, spec['TRAIN_mothers'], spec['DEV_eligible'], flush=True)
        return
    if ROOT/read(POINTER)['artifact_root'] != out:
        raise ValueError('Prepare the same execution binding first')
    for name, expected in spec['source_sha256'].items():
        if sha(ROOT/name) != expected:
            raise ValueError('Bound implementation changed')
        dest = out/'source_snapshot'/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            with dest.open('xb') as stream:
                stream.write((ROOT/name).read_bytes())
        if sha(dest) != expected:
            raise ValueError('Source snapshot changed')
    ledger = EvolutionLedger(LEDGER, run_id='revision6-M1-'+out.name[:16],
        sources={'train':list(views['train']), 'dev':list(views['dev']), 'test':[]}, binding=spec)
    executor = FrozenExecutor(ledger, out, spec['executor'])
    executor.exact_replay_roots = [history]
    actor = InterfaceActor(executor, out, plan_assets={}, source_inputs=None, relational_provider=provider,
                           pipeline_binding=spec['source_sha256'])
    all_train = [s['key'] for batch in batches for s in batch]
    learner = RelationalInterfaceLibrary(out, actor=actor, train_sources=all_train,
                                         initial_common_library_sha256=terminal['terminal_sha256'])
    labels_path = ROOT / read(history/'binding.json')['grading_path']
    if 'train' not in labels_path.parts or sha(labels_path) != spec['original_cni_TRAIN_grade_sha256']:
        raise ValueError('Use the original TRAIN label binding')
    prefix, train_trace = [], []
    for batch, group in enumerate(batches, 1):
        prefix.extend(s['key'] for s in group)
        for mother in group:
            key = mother['key']
            if key not in views['train']:
                continue
            source, view = (views['train'][key][k] for k in ('source', 'view'))
            decision = learner.choose(source, view)[1]
            entry = {'source':key, 'batch':batch, 'pre_fit_choice':decision}
            immutable_json(out/'TRAIN_forward_choices'/(digest(key)+'.json'), entry)
            rows = convergence_training.calibrate_source(
                learner, source, view, unit_reviews=audit(reviewed[key]),
                grade_provider=lambda mother: read(labels_path)[mother], visible_prefix=prefix)
            entry['calibration_reads_sha256'] = [digest(row) for row in rows]
            train_trace.append(entry)
        snapshot = learner.snapshot(batch=batch, visible_prefix=prefix)
        immutable_json(out/'TRAIN_batch_libraries'/f'B{batch}.json', snapshot)
        write_status(out, {'status':'running', 'stage':'TRAIN_fit', 'batch':batch}, POINTER)
    restored = RelationalInterfaceLibrary.restore(out, actor=actor, train_sources=all_train,
                                                  snapshot=read(out/'TRAIN_batch_libraries/B8.json'))
    before, baseline, predictions, choices = {}, {}, {'fixed':{},'synthesized':{},'learned':{}}, []
    old_actor = release.ReleaseActor(parent, release.parent_cells(parent, terminal), {})
    old_arm = release.formal.common.ORDINARY
    for mother in dev:
        key = mother['key']
        old = old_actor.original(old_arm, key)['result']['native']
        before[key] = old
        baseline[key] = old[TASK]
        if key not in views['dev']:
            for values in predictions.values():
                values[key] = old[TASK]
            continue
        source, view = (views['dev'][key][k] for k in ('source','view'))
        plan, choice = restored.choose(source, view)
        proof = {'source':key, 'library_sha256':snapshot['snapshot_sha256'], 'selection':choice}
        immutable_json(out/'DEV_pre_read_choices'/(digest(key)+'.json'), proof)
        cases = {role:actor.measure(source,view,candidate,'skill_dev')
                 for role, candidate in zip(('fixed','synthesized'),view['plans'],strict=True)}
        for role, row in cases.items():
            predictions[role][key] = row['native'][TASK]
        predictions['learned'][key] = cases['fixed' if plan['is_correct_fixed_raw_control'] else 'synthesized']['native'][TASK]
        choices.append({**proof, 'selected_relational':not plan['is_correct_fixed_raw_control'],
                        'physical_calls':{role:row['physical_call_id'] for role,row in cases.items()}})
        write_status(out, {'status':'running', 'stage':'DEV_reuse', 'completed_mothers':len(choices)}, POINTER)
    bank = {'common_program':baseline, **predictions}
    prediction_sha256 = immutable_json(out/'sealed_native_predictions.json', {
        arm:{k:{**before[k], TASK:row} for k,row in values.items()} for arm,values in bank.items()})
    loc = study['grading_paths'][DATASET]
    if 'dev' not in Path(loc).parts or sha(ROOT/loc) != study['grading_file_sha256'][loc]:
        raise ValueError('Only the already declared DEV grading file is authorized')
    with ledger.transaction() as db:
        physical = dict(db.execute('select status,count(*) from calls where id like ? group by status',
                                   (ledger.run_id+':%',)))
    if physical.get('reserved'):
        raise ValueError('Reconcile active physical requests first')
    result = sealed({
        'status':'settled_revision6_formal_contract_M1', 'binding_sha256':out.name,
        'TRAIN_calibration':train_trace, 'DEV_selection':choices, 'TEST_opened':False,
        'prediction_sha256':prediction_sha256, 'new_physical_requests':physical,
        'DEV_all':compare(dev, bank, read(ROOT/loc)),
        'DEV_eligible':compare([s for s in dev if s['key'] in views['dev']], bank, read(ROOT/loc)),
    },'terminal_sha256')
    immutable_json(out/'terminal.json', result)
    write_status(out, {'status':result['status'],'terminal_sha256':result['terminal_sha256']}, POINTER)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('prepare','run'))
    run(parser.parse_args().phase == 'run')
