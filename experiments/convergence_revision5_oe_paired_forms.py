"""Measure same-asset form reconciliation with archived EC and EV reads."""

import json
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

import jsonschema

from experiments import convergence_revision5_oe_scoped_forms as tr
from experiments import convergence_revision5_oe_scoped_forms_dev as dv
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha
from legal_skill_guard.paired_interfaces import convergence_oe_pa_monetary as pa
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.convergence_oe_title_scope import title_inventory
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest

HOME = BASE / 'revision5_oe_paired_forms_20261119'
POINTER = HANDOFF / 'revision5_oe_paired_forms_current.json'
TASKS = ('EC', 'EV')
PERSONAL = 'Assume all assets are held for the personal use of the Debtor(s), unless explicitly stated otherwise.'
FILING = re.compile(r'(?P<party>[^.]+ \(hereinafter the Debtors?\)) filed for bankruptcy on (?P<date>.+)\.')
DATE = re.compile(r'(?:\d{1,2}(?:[./]\d{1,2})[./]20\d{2}|[A-Za-z,\d ]+20\d{2})')


def form_context(case):
    text = case['public']['source_text']
    if text != case['native']['public']['original_input'] or case['public']['public_scope'] != tr.REGIME:
        raise ValueError('The reconciled form needs the originally bound PA view')
    instruction, _, after = text.partition('\nStatutes:\n')
    statutes, _, next_section = after.partition('\nSolved Reasoning Steps:\n')
    premise, _, after_facts = next_section.partition('\nFacts:\n')
    facts = after_facts.partition('\nOutput contract:')[0]
    if PERSONAL not in instruction or not statutes:
        raise ValueError('The source must share the same explicit personal-use rule')
    debtors, inventory, receipts = title_inventory(text)
    if debtors != case['debtor'] or inventory != case['public']['inventory']:
        raise ValueError('Reconcile only the original title-visible public inventory')
    for quote in receipts:
        if facts.count(quote) != 1:
            raise ValueError('Each renderer quote must be uniquely bound to the original facts')
        facts = facts.replace(quote, '')
    match = FILING.fullmatch(' '.join(facts.split()).rstrip(' ^').rstrip('. ') + '.')
    if not match or not DATE.fullmatch(match['date']):
        raise ValueError('A separate fact outside the asset and filing date can change the form')
    return {'filing_parties': match['party'], 'statutes': digest(statutes), 'resolved_regime': digest(premise),
            'assets': {a['description']: a['amount_quote'] for a in inventory.values()}}


def read_forms(observation, arm):
    if arm == tr.RELATION:
        if len(set(observation)) != len(observation):
            raise ValueError('A form relation must have unique states')
        return frozenset(observation)
    fixed = [observation[k] for k in tr.PORTS[1:]]
    return frozenset(name for name, values in tr.FORMS.items()
                     if all(value is None or value is actual for value, actual in zip(fixed, values, strict=True)))


def merge_forms(first, second):
    """Keep jointly supported possibilities; preserve uncertainty under disagreement."""
    intersection = first & second
    return intersection if intersection else first | second


def project(case, forms, consumer):
    family = case['family']
    plan = {'public_context': {'governing_regime': tr.REGIME}, 'residual_program': consumer,
            'residual_required_fields': consumer['input_fields'],
            'array_fields': ['asset_descriptions', 'asset_values', *tr.PORTS]}
    answer = {}
    for row in case['public']['inventory'].values():
        name = row['description']
        raw_claims = []
        for world in tr.worlds(row['filing_interest_established'], forms[name]):
            contents = (name, float(row['amount_quote'][1:].replace(',', '')), *world)
            fields = {key: {'value': value, 'status': 'stated'}
                      for key, value in zip(plan['array_fields'], contents, strict=True)}
            packet = {'assets': [{'fields': fields}], 'inventory_complete': True, 'unresolved': [],
                      'globals': {'number_of_debtors': {'value': case['debtor'], 'status': 'stated'}}}
            native = tr.consume(plan, packet, family)
            if not native['handled'] or set(native['answer']) != {name}:
                raise ValueError('Both layouts must use the same fixed asset consumer')
            raw_claims.append(native['answer'][name])
        if raw_claims:
            must_hold = [claim for claim in raw_claims[0] if all(claim in r for r in raw_claims[1:])]
            if must_hold or all(not claims for claims in raw_claims):
                answer[name] = must_hold
    return answer


def collect(module, role, db):
    stage = ROOT / read(module.POINTER)['artifact_root']
    old = read(stage / 'binding.json')
    archive = read(stage / 'terminal.json')
    cases = read(stage / 'cases.json')
    path = ROOT / old['grade' if role == 'train' else 'grading_path']
    if (stage.name != digest(old) or digest(cases) != old['cases_sha256' if role == 'train' else 'case_sha256']
            or archive.get('TEST_opened', archive.get('DEV_or_TEST_used'))
            or sha(stage / 'predictions.json') != archive['predictions_sha256']
            or role not in path.parts or sha(path) != old['grade_sha256' if role == 'train' else 'grading_sha256']
            or any(sha(stage / 'source_snapshot' / name) != h or sha(ROOT / name) != h
                   for name, h in old['source_sha256'].items())):
        raise ValueError('Expected the fixed PA comparison, frozen sources and original TRAIN/DEV labels')
    verifier = FrozenExecutor(None, stage, old['executor'])
    decode = tr.checked_response if role == 'train' else dv.verified_raw
    pairs, archived, physical = defaultdict(dict), {}, set()
    for case, pair in zip(cases, read(stage / 'predictions.json'), strict=True):
        key, task = case['source'], case['family']
        archived[key, task] = pair
        values = {}
        for arm in tr.ARMS:
            identity = pair[arm]['physical_call_id']
            response = decode(db, verifier, identity, case, arm)
            if response['finish_reason'] != 'stop' or identity in physical:
                raise ValueError('A form may be replayed only from a complete original distinct physical read')
            physical.add(identity)
            observation = json.loads(response['content'])
            jsonschema.validate(observation, module.contract(case, arm)[1])
            values[arm] = {a['description']: read_forms(observation[slot], arm)
                           for slot, a in case['public']['inventory'].items()}
        # The prediction path receives the case minus its independently audited reference.
        pairs[key][task] = ({k: v for k, v in case.items() if k != 'truth'}, values)
    if any(set(group) != set(TASKS) for group in pairs.values()):
        raise ValueError('Require the original EC and EV reads for each included mother')
    return pairs, archived, old['proof']['residuals'], path, physical, sha(stage / 'terminal.json')


def predictions(pairs, archived, consumers, role):
    outputs, coverage = {}, Counter()
    for key, pair in pairs.items():
        (ec, ec_rows), (ev, ev_rows) = (pair[t] for t in TASKS)
        public = form_context(ec)
        if public != form_context(ev):
            raise ValueError('The exact same asset, amount, use premise and regime must bind both views')
        combined = {}
        for arm in tr.ARMS:
            combined[arm] = {}
            for name, first in ec_rows[arm].items():
                second = ev_rows[arm][name]
                combined[arm][name] = merge_forms(first, second)
                coverage[arm + '_form_disagrees'] += first != second
                coverage[arm + '_disjoint'] += not bool(first & second)
        coverage['bound_asset_pairs'] += len(public['assets'])
        for task, (case, observations) in pair.items():
            view = case['native']
            claims = pa.claims(view)
            legacy = archived[key, task]
            results = {}
            for arm in tr.ARMS:
                single = project(case, observations[arm], consumers[task])
                merged = project(case, combined[arm], consumers[task])
                if role == 'dev' and single != legacy[arm]['raw']:
                    raise ValueError('Single-view execution must reproduce the original DEV decoder')
                results[arm + '_original'] = pa.apply(task, legacy[arm]['raw'], claims)
                results[arm + '_single'] = pa.apply(task, single, claims)
                results[arm + '_paired'] = pa.apply(task, merged, claims)
            if role == 'dev':
                results['direct_source_review'] = pa.apply(task, legacy['source_review'], claims)
            outputs.setdefault(key, {})[task] = results
    return outputs, dict(coverage)


def grade(outputs, pairs, labels):
    summary = {}
    for task in TASKS:
        bank = defaultdict(list)
        for key, group in outputs.items():
            view = pairs[key][task][0]['native']
            for arm, answer in group[task].items():
                value = grade_view('OpenExempt', view, labels[key][task], answer)['grade']
                bank[arm].append({'source': key, 'view': task, 'grade': value})
        summary[task] = {'native_F1': {k: mean(r['grade'] for r in rows) for k, rows in bank.items()},
            'paired_M1_vs_fixed': paired_source_effect(bank[tr.FIXED + '_paired'], bank[tr.RELATION + '_paired']),
            'paired_vs_single': {arm: paired_source_effect(bank[arm + '_single'], bank[arm + '_paired'])
                                 for arm in tr.ARMS}}
    return summary


def run():
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        ledger = dict(db.execute('SELECT status, count(*) FROM calls GROUP BY status'))
        if ledger.get('reserved'):
            raise ValueError('Run only against settled archive')
        data = {p: collect(m, p, db) for p, m in (('train', tr), ('dev', dv))}
        if len(data['train'][4] | data['dev'][4]) != 36:
            raise ValueError('Use all 36 original distinct fixed and relational readings')
    binding = {'stage': 'paired_asset_form_source_alignment', 'read_selection': 'entire original PA pair cohorts',
               'cross_view_read_budget_equalized': True, 'source_sha256': sha(Path(__file__)),
               'parent_sha256': {p: x[5] for p, x in data.items()}, 'monetary_source_sha256': sha(Path(pa.__file__))}
    out = HOME / digest(binding)
    immutable_json(out / 'binding.json', binding)
    if (out / 'terminal.json').exists():
        print(out, flush=True)
        return
    bank, counts = {}, {}
    for role, (pairs, archive, consumers, _, _, _) in data.items():
        bank[role], counts[role] = predictions(pairs, archive, consumers, role)
    prediction_sha = immutable_json(out / 'predictions.json', bank)
    report = sealed({'status': 'settled_oe_form_pairing', 'model_calls': 0, 'ledger': ledger,
                     'binding_sha256': digest(binding), 'predictions_sha256': prediction_sha, 'physical_cache_reads': 36,
                     'no_TEST_access': True, 'verified_pairs': counts,
                     'scores': {role: grade(bank[role], pairs, read(path))
                                for role, (pairs, _, _, path, _, _) in data.items()}}, 'terminal_sha256')
    immutable_json(out / 'terminal.json', report)
    pending = POINTER.with_suffix('.pending')
    pending.write_text(json.dumps({'artifact_root': str(out.relative_to(ROOT)),
                                   'terminal_sha256': report['terminal_sha256']}) + '\n')
    pending.replace(POINTER)
    print(out, flush=True)


if __name__ == '__main__':
    run()
