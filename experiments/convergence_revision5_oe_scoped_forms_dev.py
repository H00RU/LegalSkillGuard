"""Forward comparison with a title-factored fixed-field control on the original PA DEV rows."""

import argparse
import base64
from collections import Counter
import fcntl
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
from statistics import mean

import jsonschema

from experiments.convergence_formal_curves import pointer
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision5_oe_scoped_forms import (
    FIXED, RELATION, PORTS, REGIME, POINTER as TRAIN_POINTER, answers, contract as training_contract,
)
from experiments.convergence_revision5_oe_scoped_forms_controls import literal_ports
from legal_skill_guard.paired_interfaces.asset_interfaces import context_from_public
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.convergence_oe_title_scope import rules, title_inventory
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view, record_schema
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE / 'revision5_OE_scoped_forms_DEV_20261119'
POINTER = HANDOFF / 'revision5_OE_scoped_forms_DEV_current.json'
ARMS = (FIXED, RELATION)
MODES = ('raw', 'audited')
CONTROLS = ('train_literal', 'source_review')
METRICS = (*(f'{arm}_{mode}' for arm in ARMS for mode in MODES), *CONTROLS)
# Source-review audit for the existing PA DEV views. Kept out of prompts and
# candidate fitting. These cues identify the main item in each literal name.
REVIEW_APPAREL = re.compile(r'\b(?:hoodie|dress shirt|utility jacket)\b', re.I)
REVIEW_OTHER = re.compile(r'\b(?:insulin pump|brooch|Jeep Wrangler|Volkswagen Jetta|Chevrolet Suburban|'
                          r'drum kit|laptop|pendant necklace|revolver|Lexus RX)\b', re.I)


def review_port_tuple(asset):
    text = asset['description']
    apparel, other = (bool(p.search(text)) for p in (REVIEW_APPAREL, REVIEW_OTHER))
    if apparel == other:
        raise ValueError('The DEV review requires an unambiguous principal item')
    return (asset['filing_interest_established'], True, apparel)


def contract(case, arm):
    messages, schema = training_contract(case, arm)
    if arm == RELATION:
        return messages, schema
    bits = {p: {'type': ['boolean', 'null']} for p in PORTS[1:]}
    schema = record_schema(dict.fromkeys(case['public']['inventory'], record_schema(bits)))
    common = messages[0]['content'].rsplit('\n', 1)[0]
    directions = ('Return independent movable and apparel truth values for each asset. Use null for '
                  'unestablished predicates. The decoder derives personal-nonbusiness from the same supplied '
                  'title scope and these observations.')
    return ([{**messages[0], 'content': common + '\n' + directions}, messages[1]], schema)


def decode(case, arm, raw, residual):
    if arm == RELATION or raw['finish_reason'] != 'stop':
        return answers(case, arm, raw, residual)
    try:
        value = json.loads(raw['content'])
        jsonschema.validate(value, contract(case, FIXED)[1])
    except (ValueError, jsonschema.ValidationError) as error:
        return {'raw': {}, 'audited': {}, 'invalid': type(error).__name__, 'supported': 0, 'unsafe': 0}
    expanded = {key: {PORTS[0]: None, **cells} for key, cells in value.items()}
    return answers(case, FIXED, {**raw, 'content': json.dumps(expanded)}, residual)


def materials():
    training = ROOT / read(TRAIN_POINTER)['artifact_root']
    fit = read(training / 'binding.json')
    train_terminal = read(training / 'terminal.json')
    assert training.name == digest(fit) and fit['partition'] == 'TRAIN'
    assert train_terminal['status'] == 'settled_OE_scoped_form_relation_TRAIN'
    assert sha(training / 'predictions.json') == train_terminal['predictions_sha256']
    assert all(sha(ROOT / p) == h for p, h in fit['source_sha256'].items())
    train = read(training / 'cases.json')
    assert fit['cases_sha256'] == digest(train) and len(train) == 8
    for r in train:
        debtors, inventory, _ = title_inventory(r['public']['source_text'])
        assert debtors == r['debtor'] and inventory == r['public']['inventory']

    original = ROOT / read(pointer(8))['artifact_root']
    original_binding = read(original / 'binding.json')
    original_terminal = read(original / 'terminal.json')
    assert original.name == digest(original_binding) and original_terminal['batch'] == 8 and not original_terminal['TEST_opened']
    assert all(sha(original / 'source_snapshot' / p) == h for p, h in original_binding['source_sha256'].items())
    checkpoint = ROOT / original_binding['checkpoint_root']
    prior = read(checkpoint / 'binding.json')
    assert digest(prior) == original_binding['checkpoint_binding_sha256']
    grade = prior['grading_paths']['OpenExempt']
    assert 'dev' in Path(grade).parts
    b0 = ROOT / original_binding['b0_dev_data_root']
    public = read(b0 / 'public_DEV_sources.json')
    assert len(public) == 80 and digest(public) == read(b0 / 'binding.json')['DEV_public_sha256']
    cases, coverage = [], Counter()
    for source in public:
        if source['dataset'] != 'OpenExempt':
            continue
        assert source['project_split'] == 'dev'
        for view in source['views']:
            family = view['id']
            context = context_from_public(view['public'])
            if family not in ('EC', 'EV') or context['governing_regime'] != REGIME:
                continue
            assert context['public_task_assumptions'] and context['supported_by_frozen_legal_program']
            text = view['public']['original_input']
            debtors, inventory, receipts = title_inventory(text)
            trial = {'source': source['key'], 'family': family, 'native': view, 'debtor': debtors,
                     'public': {'source_text': text, 'public_scope': REGIME, 'inventory': inventory},
                     'truth': {slot: review_port_tuple(a) for slot, a in inventory.items()},
                     'local_anchor_receipts': receipts}
            for a in inventory.values():
                if all(v is None for v in literal_ports(a['description'], a['filing_interest_established']).values()):
                    coverage['outside_train_noun_control_'+family] += 1
            coverage['assets_'+family] += len(inventory)
            coverage['unresolved_title_groups_'+family] += sum(r['status'] is None for r in receipts.values())
            cases.append(trial)
    assert Counter(x['family'] for x in cases) == {'EC': 5, 'EV': 5}
    assert len({x['source'] for x in cases}) == 5
    files = {*fit['source_sha256'], str(Path(__file__).relative_to(ROOT)),
             'experiments/convergence_revision5_oe_scoped_forms_controls.py',
             'legal_skill_guard/paired_interfaces/convergence_oe_title_scope.py',
             'legal_skill_guard/paired_interfaces/convergence_effects.py'}
    binding = {'study': 'PA_scoped_form_original_B8_DEV', 'partition': 'DEV',
               'cohort_selection': 'All PA EC and EV views from the existing B8 development split',
               'original_B8_DEV_binding': original.name, 'public_DEV_sha256': digest(public),
               'train_binding': training.name, 'train_terminal_sha256': sha(training / 'terminal.json'),
               'source_sha256': {f: sha(ROOT / f) for f in sorted(files)}, 'case_sha256': digest(cases),
               'proof': fit['proof'], 'executor': fit['executor'], 'grading_path': grade,
               'grading_sha256': prior['grading_file_sha256'][grade],
               'comparison': 'Frozen TRAIN relation versus independent fixed movable/apparel fields with title factored out',
               'primary': 'Raw EV native F1; EC and source-reviewed outputs reported separately',
               'heldout_access': False, 'native_labels_used_for_source_review_or_method': False,
               'train_title_bindings_unchanged': len(train), 'renderer_templates': len(rules()), 'coverage': dict(coverage)}
    return binding, cases


def verified_raw(db, executor, call, case, arm):
    row = db.execute('select status,role,source,purpose,request_hash,result from calls where id=?', (call,)).fetchone()
    assert row[:4] == ('completed', 'executor', case['source'], 'skill_dev')
    raw = json.loads(row[5])
    folder = Path(raw['artifact_directory'])
    request, wire = (read(folder / name) for name in ('request.json', 'wire_request.json'))
    data = base64.b64decode(wire['body_b64'], validate=True)
    messages, schema = contract(case, arm)
    expect = executor.payload(messages=messages, thinking=False, schema=schema)
    assert sha256(data).hexdigest() == wire['body_sha256'] and json.loads(data) == request['payload'] == expect
    assert request['request_hash'] == row[4] == raw['request_hash'] and read(folder / 'result.json') == raw
    return raw


def control_answers(case, residual):
    direct, review = {}, {}
    for key, a in case['public']['inventory'].items():
        direct[key] = literal_ports(a['description'], a['filing_interest_established'])
        review[key] = dict(zip(PORTS, case['truth'][key], strict=True))
    return {arm: answers(case, FIXED, {'finish_reason': 'stop', 'content': json.dumps(value)}, residual)['raw']
            for arm, value in zip(CONTROLS, (direct, review), strict=True)}


def score(out, binding, cases, records, ledger):
    path = ROOT / binding['grading_path']
    assert sha(path) == binding['grading_sha256']
    grade = read(path)
    measurements = []
    for case, pair in zip(cases, records, strict=True):
        key, family = case['source'], case['family']
        comparisons = {f'{arm}_{mode}': pair[arm][mode] for arm in ARMS for mode in MODES}
        comparisons.update({name: pair[name] for name in CONTROLS})
        values = {k: grade_view('OpenExempt', case['native'], grade[key][family], v)['grade']
                  for k, v in comparisons.items()}
        assert all(v is not None for v in values.values())
        measurements.append({'source': key, 'family': family, **values})
    immutable_json(out / 'scores.json', measurements)
    means, effects = {}, {}
    for family in ('EC', 'EV'):
        group = [r for r in measurements if r['family'] == family]
        means[family] = {k: mean(r[k] for r in group) for k in METRICS}
        def cells(k):
            return [{'source': r['source'], 'view': family, 'grade': r[k]} for r in group]
        effects[family] = {m: paired_source_effect(cells(FIXED+'_'+m), cells(RELATION+'_'+m)) for m in MODES}
    return {'status': 'settled_OE_scoped_forms_original_DEV', 'new_Qwen_calls': len(cases) * len(ARMS),
            'new_teacher_calls': 0, 'tokens': {arm: sum(row[arm]['tokens'] for row in records) for arm in ARMS},
            'native_mean_f1': means, 'paired_effects': effects, 'ledger': ledger, 'views': len(cases), 'mothers': 5,
            'unsupported_form_assertions': {arm: sum(row[arm]['unsafe'] for row in records) for arm in ARMS},
            'invalid_responses': {arm: sum(bool(row[arm]['invalid']) for row in records) for arm in ARMS},
            'predictions_sha256': sha(out / 'predictions.json'), 'scores_sha256': sha(out / 'scores.json'),
            'runner_sha256': sha(Path(__file__)), 'TEST_opened': False}


def run(phase):
    binding, cases = materials()
    out = HOME / digest(binding)
    immutable_json(out / 'binding.json', binding)
    immutable_json(out / 'cases.json', cases)
    if (out / 'terminal.json').exists():
        print(json.dumps(read(out / 'terminal.json')), flush=True)
        return
    if phase == 'prepare':
        write_status(out, {'status': 'prepared', 'planned_calls': len(cases)*len(ARMS)}, POINTER)
        print(json.dumps({'path': str(out.relative_to(ROOT)), 'coverage': binding['coverage']}), flush=True)
        return
    assert ROOT / read(POINTER)['artifact_root'] == out
    driver = (out / 'driver.lock').open('a')
    fcntl.flock(driver, fcntl.LOCK_EX | fcntl.LOCK_NB)
    for name, expected in binding['source_sha256'].items():
        saved = out / 'source_snapshot' / name
        saved.parent.mkdir(parents=True, exist_ok=True)
        if not saved.exists():
            with saved.open('xb') as stream:
                stream.write((ROOT / name).read_bytes())
        assert sha(saved) == expected
    identity = 'convergence-revision5-OE-scoped-forms-DEV-' + out.name[:16]
    ledger = EvolutionLedger(LEDGER, run_id=identity, sources={
        'train': [], 'dev': sorted({c['source'] for c in cases}), 'test': []}, binding=binding)
    executor = FrozenExecutor(ledger, out, binding['executor'])
    executor.readiness()
    results = []
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        assert not db.execute("select 1 from calls where status='reserved'").fetchone()
        for index, case in enumerate(cases):
            residual = binding['proof']['residuals'][case['family']]
            record = {}
            for arm in (ARMS if index % 2 == 0 else ARMS[::-1]):
                call = f'{identity}:{index}:{arm}'
                write_status(out, {'status': 'running', 'verified_pairs': index, 'current_call_id': call}, POINTER)
                messages, schema = contract(case, arm)
                executor.generate(call, source=case['source'], purpose='skill_dev',
                                  messages=messages, thinking=False, schema=schema)
                raw = verified_raw(db, executor, call, case, arm)
                record[arm] = {'physical_call_id': call, 'tokens': raw['usage']['total_tokens'],
                               **decode(case, arm, raw, residual)}
                print(json.dumps({'verified_call': call}), flush=True)
            record.update(control_answers(case, residual))
            immutable_json(out / 'paired_reads' / f'{index}.json', record)
            results.append(record)
        ledger_counts = dict(db.execute('select status,count(*) from calls group by status'))
        assert not ledger_counts.get('reserved')
    immutable_json(out / 'predictions.json', results)
    terminal = score(out, binding, cases, results, ledger_counts)
    immutable_json(out / 'terminal.json', terminal)
    write_status(out, {'status': terminal['status'], 'verified_pairs': len(cases)}, POINTER)
    print(json.dumps(terminal), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('prepare', 'run'))
    run(parser.parse_args().phase)
