"""Compare a compiled asset-form relation with fixed ports on reviewed PA TRAIN views."""

import argparse
import base64
from collections import Counter, defaultdict
import fcntl
from hashlib import sha256
from itertools import combinations, product
import json
from pathlib import Path
import re
import sqlite3
from statistics import mean

import jsonschema

from experiments.convergence_formal_train_observe import load_roster, pointer
from experiments.convergence_oe_natural_relation import OLD_TRAIN, REGISTRY
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision5_oe_asset_projection import FROZEN_ASSET_SKILL, inputs
from legal_skill_guard.paired_interfaces.asset_graph_pairs import reference_world
from legal_skill_guard.paired_interfaces.asset_interfaces import frozen_skill
from legal_skill_guard.paired_interfaces.asset_port_decoder_v2 import consume
from legal_skill_guard.paired_interfaces.convergence_ev_inventory import INVENTORY_FILES, public_inventory
from legal_skill_guard.paired_interfaces.program_residual import specialize
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view, record_schema
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE / 'revision5_OE_scoped_forms_20261119'
POINTER = HANDOFF / 'revision5_OE_scoped_forms_current.json'
REGIME = 'Federal and Pennsylvania'
FIXED, RELATION = 'fixed_ports', 'scoped_relation'
ARMS = (FIXED, RELATION)
PORTS = ('asset_is_personal_nonbusiness_property', 'asset_is_personal_tangible_property',
         'asset_is_wearing_apparel')
# The source-checked PA scope has three joint forms under the public personal-use premise.
# Ownership remains a separate assertion about the listed filing debtors.
FORMS = {'out_of_scope': (False, False), 'movable_nonapparel': (True, False),
         'wearing_apparel': (True, True)}
UNRESOLVED_TITLE = re.compile(r'\b(?:possess(?:es)?|assert ownership|disclosure of assets|estate of)\b', re.I)
ESTABLISHED_TITLE = re.compile(r'\b(?:owns?|owned by|under the ownership of|belonging to|property of)\b', re.I)

COMMON = """Read the three Pennsylvania asset predicates using the supplied public personal-use premise.
A listed item outside the qualifying personal-movable scope, such as real property or explicitly business
property, has both movable and apparel false. An ordinary movable object has movable true and apparel false.
Wearing apparel has both true. The personal-nonbusiness predicate also needs established filing-debtor
ownership of that asset. The public inventory ties each asset to its exact asset sentence. Use the supplied
sentence-level title status. Unresolved title stays unknown and does not make a movable object out of scope.
Use each asset description and its own sentence. Return factual observations alone and preserve ambiguity."""


def title_at_anchor(text):
    unknown, stated = (bool(p.search(text)) for p in (UNRESOLVED_TITLE, ESTABLISHED_TITLE))
    if unknown and not stated:
        return None
    if stated and not unknown:
        return True
    raise ValueError('The reviewed renderer sentence needs a verified title basis')


def worlds(title, forms=tuple(FORMS), fixed=None):
    """Compile joint port tuples without turning lack of established title into falsity."""
    titles = (False, True) if title is None else (title,)
    values = {(movable and held, movable, apparel)
              for form in forms for movable, apparel in (FORMS[form],) for held in titles}
    if fixed is not None:
        values = {w for w in values if all(v is None or v is t for v, t in zip(fixed, w, strict=True))}
    return tuple(sorted(values))


def proof():
    # Check equality at the unchanged consumer ABI for every declared nonempty form set.
    skill = frozen_skill()
    assert digest(skill) == FROZEN_ASSET_SKILL
    residuals = {family: specialize(skill['procedure'], {'governing_regime': REGIME, 'output_family': family},
                                   allowed_context_fields={'governing_regime', 'output_family'})
                 for family in ('EC', 'EV')}
    assert all(set(PORTS) == {f for f in r['input_fields'] if f.startswith('asset_is_')}
               for r in residuals.values())
    checks = 0
    for title in (False, True, None):
        for count in range(1, len(FORMS) + 1):
            for names in combinations(FORMS, count):
                reference = {v for v in product((False, True), repeat=3)
                             if v[1:] in {FORMS[k] for k in names}
                             and (v[0] == (v[1] and title) if title is not None else v[1] or not v[0])}
                assert reference == set(worlds(title, names))
                checks += 1
    return {'state_sets_verified': checks, 'frozen_consumer_sha256': FROZEN_ASSET_SKILL,
            'residuals': residuals,
            'equality': 'Both representations pass identical complete tuples to the unmodified F within the declared source scope.'}


def contract(case, arm):
    if arm == FIXED:
        bits = {p: {'type': ['boolean', 'null']} for p in PORTS}
        schema = record_schema(dict.fromkeys(case['public']['inventory'], record_schema(bits)))
        directions = 'Return the three separate truth values for each asset. Use null for an unestablished predicate.'
    else:
        row = {'type': 'array', 'items': {'type': 'string', 'enum': list(FORMS)}, 'minItems': 1, 'maxItems': 3}
        schema = record_schema(dict.fromkeys(case['public']['inventory'], row))
        directions = ('For each asset return all forms still possible among out_of_scope, movable_nonapparel, '
                      'and wearing_apparel. The decoder combines those forms with the supplied title scope.')
    return ([{'role': 'system', 'content': COMMON + '\n' + directions},
             {'role': 'user', 'content': json.dumps(case['public'], sort_keys=True, ensure_ascii=False)}], schema)


def materials():
    verified = proof()
    registry = read(REGISTRY)
    assert digest({k: v for k, v in registry.items() if k != 'registry_sha256'}) == registry['registry_sha256']
    earlier = ROOT / read(HANDOFF / 'revision5_OE_claim_projection_terminal_20261119.json')['artifact_root']
    observed = ROOT / read(pointer(3))['artifact_root']
    obs = read(observed / 'binding.json')
    assert observed.name == digest(obs) and not read(observed / 'terminal.json')['TEST_opened']
    study = read(ROOT / obs['checkpoint_root'] / 'binding.json')
    roster = load_roster(study)
    train = {s['key']: s for batch in roster for s in batch if s['dataset'] == 'OpenExempt'}
    old = {s['key']: s for s in read(OLD_TRAIN) if s['key'] in train}
    chosen = []
    for review in sorted(registry['reviews'], key=lambda row: (row['source'], row['view'])):
        if review['source'] not in train or review['kind'] != 'asset_program_ports':
            continue
        path = ROOT / review['path']
        assert sha(path) == review['sha256']
        card = read(path)
        if card['public_regime'] != REGIME:
            continue
        key, view = review['source'], review['view']
        assert train[key]['project_split'] == 'train' and train[key]['views'] == old[key]['views']
        assert digest(old[key]) == registry['source_public_sha256'][key]
        assert card['native_answers_used'] is False and card['source_semantic_truth_verified']
        task, native_ids = inputs(old[key])
        family, = (f for f, v in native_ids.items() if v == view)
        native, = (v for v in train[key]['views'] if v['id'] == family)
        units, = (r['source_units'] for r in task['views'] if r['view_id'] == view)
        reference_world(card, units, REGIME)
        full = native['public']['original_input']
        inventory = public_inventory(full)
        assert inventory is not None
        rows = {r['fields']['asset_descriptions']['value']: r for r in card['port_record']['assets']}
        assert {a['description'] for a in inventory.values()} == set(rows)
        debtor = card['port_record']['globals']['number_of_debtors']['value']
        marker = '(hereinafter the Debtors)' if '(hereinafter the Debtors)' in units[0]['text'] else '(hereinafter the Debtor)'
        assert units[0]['text'].count(marker) == 1 and debtor == (2 if marker.endswith('Debtors)') else 1)
        public = {'source_text': full, 'public_scope': REGIME, 'inventory': {}}
        truth = {}
        for slot, asset in inventory.items():
            description = asset['description']
            fields = rows[description]['fields']
            title = title_at_anchor(asset['source_quote'])
            title_review = rows[description].get('ownership_evidence')
            if title_review is not None:
                assert (title is True) == (title_review['status'] == 'stated')
            target = tuple(fields[p]['value'] for p in PORTS)
            assert target[1:] in FORMS.values() and target[0] == (title if target[1] else False)
            amount = float(asset['amount_quote'][1:].replace(',', ''))
            assert fields['asset_values']['value'] == amount
            public['inventory'][slot] = {**asset, 'filing_interest_established': title}
            truth[slot] = target
        chosen.append({'source': key, 'family': family, 'native': native, 'debtor': debtor, 'public': public,
                       'review_sha256': review['sha256'], 'truth': truth})
    assert len(chosen) == 8 and len({c['source'] for c in chosen}) == 4
    grade_path = Path(obs['native_grade_paths']['OpenExempt'])
    assert grade_path == OLD_TRAIN.with_name('grading.json').relative_to(ROOT)
    bound = {*INVENTORY_FILES, str(Path(__file__).relative_to(ROOT)),
             'legal_skill_guard/paired_interfaces/asset_port_decoder_v2.py',
             'legal_skill_guard/paired_interfaces/asset_interfaces.py',
             'legal_skill_guard/paired_interfaces/native_graph_consumers.py',
             'legal_skill_guard/paired_interfaces/partial_consumer_worker.py',
             'legal_skill_guard/paired_interfaces/program_residual.py',
             'legal_skill_guard/skill_evolution/clients.py', 'legal_skill_guard/rr/client.py',
             'legal_skill_guard/skill_evolution/ledger.py', 'legal_skill_guard/skill_evolution/native.py'}
    binding = {'experiment': 'PA_scoped_asset_form_relation', 'partition': 'TRAIN', 'arms': list(ARMS),
               'prior_archive_summary_sha256': sha(earlier / 'summary.json'),
               'reference_registry_sha256': sha(REGISTRY), 'training_roster_sha256': digest(roster),
               'cases_sha256': digest(chosen), 'grade': str(grade_path),
               'grade_sha256': obs['native_grade_sha256'][str(grade_path)],
               'source_sha256': {f: sha(ROOT / f) for f in sorted(bound)}, 'proof': verified,
               'executor': study['executor'], 'views': len(chosen), 'mothers': 4,
               'fixed_uses_same_source_title_and_joint_domain': True,
               'selection': 'All source-reviewed PA mothers in the existing original TRAIN roster.',
               'source_audits_excluded_from_model_inputs': True}
    return binding, chosen


def answers(case, arm, response, compiled):
    _, schema = contract(case, arm)
    if response['finish_reason'] != 'stop':
        return {'raw': {}, 'audited': {}, 'invalid': 'nonterminal model output', 'supported': 0, 'unsafe': 0}
    try:
        observation = json.loads(response['content'])
        jsonschema.validate(observation, schema)
        if arm == RELATION and any(len(v) != len(set(v)) for v in observation.values()):
            raise ValueError('Duplicate joint forms')
    except (ValueError, jsonschema.ValidationError) as error:
        return {'raw': {}, 'audited': {}, 'invalid': type(error).__name__, 'supported': 0, 'unsafe': 0}

    plan = {'public_context': {'governing_regime': REGIME}, 'residual_program': compiled,
            'residual_required_fields': compiled['input_fields'],
            'array_fields': ['asset_descriptions', 'asset_values', *PORTS]}
    family = case['family']
    result = {'raw': {}, 'audited': {}, 'invalid': None, 'supported': 0, 'unsafe': 0}
    for slot, asset in case['public']['inventory'].items():
        name = asset['description']
        title = asset['filing_interest_established']
        target = case['truth'][slot]
        if arm == FIXED:
            read_ports = tuple(observation[slot][p] for p in PORTS)
            raw_worlds = worlds(title, fixed=read_ports)
            audit_worlds = worlds(title, fixed=tuple(t if t is v else None for t, v in zip(target, read_ports)))
        else:
            raw_worlds = worlds(title, observation[slot])
            # Mask the disputed coordinate while retaining supported implications of the relation.
            read_ports = tuple(next(iter(v)) if len(v) == 1 else None for v in map(set, zip(*raw_worlds)))
            expected_form, = (form for form, values in FORMS.items() if values == tuple(target[1:]))
            audit_worlds = (raw_worlds if expected_form in observation[slot] else
                            worlds(title, fixed=tuple(t if t is v else None for t, v in zip(target, read_ports))))
        result['supported'] += sum(v is not None and v is t for v, t in zip(read_ports, target))
        result['unsafe'] += sum(v is not None and v is not t for v, t in zip(read_ports, target))

        evaluated = {}
        for w in sorted(set(raw_worlds) | set(audit_worlds)):
            values = (name, float(asset['amount_quote'][1:].replace(',', '')), *w)
            fields = {p: {'value': v, 'status': 'stated'} for p, v in zip(plan['array_fields'], values, strict=True)}
            record = {'assets': [{'fields': fields}], 'inventory_complete': True, 'unresolved': [],
                      'globals': {'number_of_debtors': {'value': case['debtor'], 'status': 'stated'}}}
            predicted = consume(plan, record, family)
            assert predicted['handled'] and set(predicted['answer']) == {name}
            evaluated[w] = predicted['answer'][name]
        for mode, candidates in (('raw', raw_worlds), ('audited', audit_worlds)):
            copies = [evaluated[w] for w in candidates]
            if copies:
                common = [claim for claim in copies[0] if all(claim in other for other in copies[1:])]
                if common or all(not claims for claims in copies):
                    result[mode][name] = common
    return result


def checked_response(db, executor, identity, case, arm):
    r = db.execute('select status,role,source,purpose,request_hash,result from calls where id=?', (identity,)).fetchone()
    assert r[:4] == ('completed', 'executor', case['source'], 'skill_actor')
    raw = json.loads(r[5])
    folder = Path(raw['artifact_directory'])
    request, wire = (read(folder / name) for name in ('request.json', 'wire_request.json'))
    data = base64.b64decode(wire['body_b64'], validate=True)
    messages, schema = contract(case, arm)
    expect = executor.payload(messages=messages, thinking=False, schema=schema)
    assert sha256(data).hexdigest() == wire['body_sha256'] and json.loads(data) == request['payload'] == expect
    assert request['request_hash'] == r[4] == raw['request_hash'] and read(folder / 'result.json') == raw
    return raw


def run(phase):
    binding, cases = materials()
    out = HOME / digest(binding)
    immutable_json(out / 'binding.json', binding)
    immutable_json(out / 'cases.json', cases)
    if (out / 'terminal.json').exists():
        print(json.dumps(read(out / 'terminal.json')), flush=True)
        return
    if phase == 'prepare':
        write_status(out, {'status': 'prepared', 'planned_requests': 2 * len(cases)}, POINTER)
        print(str(out.relative_to(ROOT)), flush=True)
        return
    assert ROOT / read(POINTER)['artifact_root'] == out
    driver = (out / 'driver.lock').open('a')
    fcntl.flock(driver, fcntl.LOCK_EX | fcntl.LOCK_NB)
    for name, expected in binding['source_sha256'].items():
        snapshot = out / 'source_snapshot' / name
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        if not snapshot.exists():
            with snapshot.open('xb') as output:
                output.write((ROOT / name).read_bytes())
        assert sha(snapshot) == expected
    run_id = 'convergence-revision5-OE-scoped-forms-' + out.name[:16]
    ledger = EvolutionLedger(LEDGER, run_id=run_id, sources={
        'train': sorted({c['source'] for c in cases}), 'dev': [], 'test': []}, binding=binding)
    executor = FrozenExecutor(ledger, out, binding['executor'])
    executor.readiness()
    records = []
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        assert not db.execute("select 1 from calls where status='reserved'").fetchone()
        for index, case in enumerate(cases):
            pair = {}
            for arm in (ARMS if index % 2 == 0 else ARMS[::-1]):
                identity = f'{run_id}:{index}:{arm}'
                write_status(out, {'status': 'running', 'verified_pairs': index, 'current_call_id': identity}, POINTER)
                messages, schema = contract(case, arm)
                executor.generate(identity, source=case['source'], purpose='skill_actor', messages=messages,
                                  thinking=False, schema=schema)
                raw = checked_response(db, executor, identity, case, arm)
                pair[arm] = {'physical_call_id': identity, 'tokens': raw['usage']['total_tokens'],
                             **answers(case, arm, raw, binding['proof']['residuals'][case['family']])}
                print(json.dumps({'settled_call': identity}), flush=True)
            immutable_json(out / 'paired_reads' / f'{index}.json', pair)
            records.append(pair)
        counts = dict(db.execute('select status,count(*) from calls group by status'))
    immutable_json(out / 'predictions.json', records)
    grades = ROOT / binding['grade']
    assert sha(grades) == binding['grade_sha256']
    gradebook = read(grades)
    table, usage, native = defaultdict(list), Counter(), []
    for case, pair in zip(cases, records, strict=True):
        row = {}
        for arm, result in pair.items():
            usage[arm] += result['tokens']
            for mode in ('raw', 'audited'):
                f = case['family']
                grade = grade_view('OpenExempt', case['native'], gradebook[case['source']][f], result[mode])['grade']
                assert grade is not None
                table[arm, f, mode].append(grade)
                row[arm, mode] = grade
        native.append({'source': case['source'], 'family': case['family'],
                       **{'_'.join(k): v for k, v in row.items()}})
    immutable_json(out / 'scores.json', native)
    summary = {'status': 'settled_OE_scoped_form_relation_TRAIN', 'mothers': binding['mothers'], 'views': len(cases),
               'completion_sets_verified': binding['proof']['state_sets_verified'], 'verified_calls': 2 * len(cases),
               'tokens': dict(usage), 'ledger': counts, 'new_teacher_requests': 0, 'DEV_or_TEST_used': False,
               'official_mean_f1': {'_'.join(k): mean(v) for k, v in table.items()},
               'supported_assertions': {a: sum(p[a]['supported'] for p in records) for a in ARMS},
               'unsupported_assertions': {a: sum(p[a]['unsafe'] for p in records) for a in ARMS},
               'invalid_responses': {a: sum(bool(p[a]['invalid']) for p in records) for a in ARMS},
               'runner_sha256': sha(Path(__file__)), 'predictions_sha256': sha(out / 'predictions.json'),
               'scores_sha256': sha(out / 'scores.json')}
    immutable_json(out / 'terminal.json', summary)
    write_status(out, {'status': summary['status'], 'verified_pairs': len(cases)}, POINTER)
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('prepare', 'run'))
    run(parser.parse_args().phase)
