"""Test shared title on complementary value projections of the fixed TRAIN pair."""

import argparse
from dataclasses import replace
import inspect
import json
import sqlite3

import jsonschema

from experiments.convergence_oe_title_value_probe import POINTER as PRIOR, _materials, _spec, _validate
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces.convergence_oe_title_value import SCHEMA, decode_observation, selections
from legal_skill_guard.paired_interfaces.formal_actors import verify_physical_response
from legal_skill_guard.paired_interfaces.shared_semantics import DerivedField, allowed_relation
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest


POINTER = HANDOFF / 'm2_oe_title_partition_current.json'
ORIENTATIONS = (('forwarded', 'withheld'), ('withheld', 'forwarded'))
SYSTEM = (
    'Read only the named asset. Use the quoted program as guidance for evidence and local reasoning, '
    'while using only this output contract. In quote copy a continuous phrase that contains both the named '
    'asset and its stated value. In stated_value give those exact whole dollars. For ownership report true '
    'only for text establishing a current debtor owns the asset, false only for established nonownership, '
    'and null when the text establishes neither. In title_filtered_value answer for the requested component '
    'of this local filter. Under debtor ownership the full amount is forwarded and zero is withheld. Under '
    'nonownership zero is forwarded and the full amount is withheld. If the reading policy leaves which '
    'amount goes in the requested component unresolved, return null for that field. This is an intermediate '
    'value, independent of the native output format or a conclusion about an exemption or a property share. '
    'Supply the literal value quote regardless of the other fields.'
)


def _route_value(values, law):
    forwarded = values['requested_component'] == 'forwarded'
    return values['amount'] if values['ownership'] == forwarded else 0


def _project(values, law):
    return {'ownership': values['ownership'], 'stated_value': values['amount'],
            'title_filtered_value': values['title_filtered_value']}


def crossed_groups(original):
    """Keep the same audited source edits and counterbalance the queried component."""
    implementation = inspect.getsource(_route_value) + inspect.getsource(_project)
    theory = replace(original['theory'], reference=_project, reference_sha256=digest(implementation), derived=(
        DerivedField('title_filtered_value', ('amount', 'ownership', 'requested_component'), _route_value),
    ))
    groups = {}
    for orientation in ORIENTATIONS:
        cases = [replace(case, source_id=case.source_id + ':query:' + component,
                         primitives={**case.primitives, 'requested_component': component})
                 for case, component in zip(original['cases'], orientation, strict=True)]
        shared = allowed_relation(theory, cases)
        independent = allowed_relation(theory, cases, mode='independent_completions')
        shared_values = {tuple(row['title_filtered_value'] for row in signature)
                         for signature in shared['signatures'].values()}
        independent_values = {tuple(row['title_filtered_value'] for row in signature)
                              for signature in independent['signatures'].values()}
        amounts = [case.interventions.get('amount', case.primitives['amount']) for case in cases]
        if (shared_values != {(amounts[0], 0), (0, amounts[1])}
                or len(independent_values) != 4 or (0, 0) not in independent_values):
            raise ValueError('The asserted crossed relation must follow from the original positive amounts')
        name = '___'.join(orientation)
        groups[name] = {**original, 'cases': cases, 'theory': theory,
                        'shared': shared, 'independent': independent}
    return groups


def joint_group(groups):
    first, second = groups.values()
    theory = first['theory']
    cases = first['cases'] + second['cases']
    shared = allowed_relation(theory, cases)
    independent = allowed_relation(theory, cases, mode='independent_completions')
    if (len({case.source_id for case in cases}) != 4 or len({case.root_id for case in cases}) != 1
            or len(shared['signatures']) != 2 or len(independent['signatures']) != 16):
        raise ValueError('Every public query must share the original asset ownership explanation')
    return {**first, 'cases': cases, 'shared': shared, 'independent': independent}


def _bound():
    materials = _materials()
    stage, _, root, original, programs, native, visible, _ = materials
    previous = ROOT / read(PRIOR)['artifact_root']
    terminal = read(previous / 'terminal.json')
    prior_binding = read(previous / 'binding.json')
    if (previous.name != digest(prior_binding) or prior_binding['B4_terminal_sha256'] != sha(stage / 'terminal.json')
            or prior_binding['group_sha256'] != _spec(materials)['group_sha256']
            or terminal['status'] != 'completed_M2_natural_title_value_probe' or terminal['TEST_opened']
            or terminal['executor_calls'] != 4
            or [row['value']['title_filtered_value'] for row in terminal['measured']['candidate']] != [0, 0]):
        raise ValueError('The crossed test needs the actual prior two-zero observation and identical B4 controls')
    groups = crossed_groups(original)
    joint = joint_group(groups)
    files = set(prior_binding['source_sha256']) | {'experiments/convergence_oe_title_partition_probe.py'}
    binding = {'study': 'natural_OE_crossed_title_projection', 'root': root, 'executor': prior_binding['executor'],
               'previous_terminal_sha256': sha(previous / 'terminal.json'),
               'native_pairs_sha256': digest(native), 'programs_sha256': prior_binding['programs_sha256'],
               'groups_sha256': {name: digest({'public': [(case.source_id, case.public) for case in g['cases']],
                   'shared': g['shared']['signatures'], 'independent': g['independent']['signatures']})
                                 for name, g in {**groups, 'joint': joint}.items()},
               'reader_sha256': digest([SYSTEM, SCHEMA]),
               'all_orientations_reported': True, 'source_sha256': {p: sha(ROOT / p) for p in sorted(files)}}
    return binding, groups, joint, programs, native, visible


def prepare():
    binding, groups, _, _, _, _ = _bound()
    out = BASE / 'm2_oe_title_partition' / digest(binding)
    immutable_json(out / 'binding.json', binding)
    if not (out / 'terminal.json').exists():
        write_status(out, {'status': 'prepared', 'groups': list(groups), 'executor_calls_planned': 8,
                           'new_native_requests': 0, 'new_teacher_requests': 0}, POINTER)
    print(json.dumps(read(POINTER), sort_keys=True), flush=True)


def _measure(reader, out, arm, program, orientation, group):
    policy = '\n'.join(p['prompt'] for p in program['predicates'])
    rows = []
    for case, anchor in zip(group['cases'], group['anchors'], strict=True):
        payload = {'source': case.public['text'], 'named_asset': case.public['asset'],
                   'requested_component': case.primitives['requested_component'], 'quoted_reader_policy': policy}
        messages = [{'role': 'system', 'content': SYSTEM},
                    {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False, sort_keys=True)}]
        identity = reader.ledger.run_id + ':component:' + digest([case.source_id, messages, SCHEMA])
        raw = reader.generate(identity, source=case.root_id, purpose='skill_actor', messages=messages,
                              schema=SCHEMA, thinking=False)
        verify_physical_response(reader, identity=identity, source=case.root_id, purpose='skill_actor',
                                 content_sha256=digest(raw['content']), usage=raw['usage'], finish_reason=raw['finish_reason'])
        try:
            value, anchored = decode_observation(raw, case, anchor)
            failure = None
        except (ValueError, jsonschema.ValidationError) as error:
            value, anchored, failure = None, False, type(error).__name__
        row = {'case': case.source_id, 'source_sha256': digest(case.public), 'arm': arm,
               'orientation': orientation, 'component': payload['requested_component'],
               'physical_call_id': identity, 'value': value, 'anchored': anchored, 'failure': failure}
        immutable_json(out / 'projection_reads' / (digest(identity) + '.json'), row)
        rows.append(row)
    return rows


def run():
    binding, groups, joint, programs, native, visible = _bound()
    out = ROOT / read(POINTER)['artifact_root']
    if out.name != digest(binding) or read(out / 'binding.json') != binding:
        raise ValueError('The source, operator, or frozen evidence changed after preparation')
    if (out / 'terminal.json').exists():
        print(json.dumps(read(POINTER), sort_keys=True), flush=True)
        return
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        if db.execute("select 1 from calls where status='reserved'").fetchone():
            raise ValueError('Wait for the serial model stage to settle')
    run_id = 'convergence-M2-OE-title-partition-' + out.name[:16]
    ledger = EvolutionLedger(LEDGER, run_id=run_id, sources={'train': [binding['root']], 'dev': [], 'test': []}, binding=binding)
    reader = FrozenExecutor(ledger, out, binding['executor'])
    reader.readiness()
    measured = {}
    neutral = [{**row, 'patch_utility': row['baseline_utility']} for row in native]
    for orientation, group in groups.items():
        measured[orientation] = {}
        for arm, program in programs.items():
            write_status(out, {'status': 'running', 'orientation': orientation, 'arm': arm}, POINTER)
            rows = _measure(reader, out, arm, program, orientation, group)
            result = _validate(program, group, rows, native if arm == 'candidate' else neutral, visible)
            scored = selections(group, rows, result['native_utility_sum_delta'] > 0, result)
            measured[orientation][arm] = {'rows': rows, 'validation': result, 'comparison': scored}
    with ledger.transaction() as db:
        physical = db.execute('select status,result from calls where id like ?', (run_id + ':%',)).fetchall()
    if len(physical) != 8 or any(status != 'completed' for status, _ in physical):
        raise ValueError('Every orientation and program needs its own two completed responses')
    comparisons = {orientation: {arm: row['comparison'] for arm, row in members.items()}
                   for orientation, members in measured.items()}
    joint_evaluations = {}
    comparisons['joint'] = {}
    for arm, program in programs.items():
        rows = [row for members in measured.values() for row in members[arm]['rows']]
        result = _validate(program, joint, rows, native if arm == 'candidate' else neutral, visible)
        joint_evaluations[arm] = result
        comparisons['joint'][arm] = selections(joint, rows, result['native_utility_sum_delta'] > 0, result)
    result = {'status': 'completed_M2_natural_title_partition_probe', 'measured': measured,
              'comparison': comparisons, 'joint_validation': joint_evaluations, 'executor_calls': len(physical),
              'executor_tokens': sum(json.loads(raw)['usage']['total_tokens'] for _, raw in physical),
              'new_native_requests': 0, 'new_teacher_requests': 0, 'formal_updates_changed': False, 'TEST_opened': False}
    immutable_json(out / 'terminal.json', result)
    write_status(out, {'status': result['status'], 'executor_calls': len(physical), 'comparison': comparisons}, POINTER)
    print(json.dumps(read(POINTER), sort_keys=True), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('prepare', 'run'))
    (prepare if parser.parse_args().phase == 'prepare' else run)()
