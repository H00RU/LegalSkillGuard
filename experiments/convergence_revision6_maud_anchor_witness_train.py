"""Compare anchor-indexed covenant witnesses with the original same-input readers."""

import argparse
import fcntl
import json
import sqlite3
from collections import Counter
from pathlib import Path

import jsonschema

from experiments import convergence_revision6_maud_operative_attribution as prior
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import maud_anchor_witnesses as witnesses
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

STAGE = 'revision6_maud_anchor_witness_train'
POINTER = HANDOFF / f'{STAGE}_current.json'
measured, fit, controls = prior.measured, prior.fit, prior.controls
GUIDE = (
    'Start from each candidate clause anchor. Determine the obligation attested by the anchor, then '
    'trace any exception that directly governs that obligation to a listed focus marker. '
    'For each anchor, give the first marker in source order that is an operative pandemic condition '
    'for that anchor. A marker can govern more than one anchor, but verify the attachment independently '
    'for each. Repeated excerpts and nearby pandemic wording alone do not establish the attachment. '
    'If you checked the anchor and ruled out every listed operative pandemic exception, return '
    f'{witnesses.EXCLUDED}. If an operative attachment remains unresolved, return null. '
    'Set checked_coverage for a family only if you checked all relevant clauses and exceptions.'
)


def query(case):
    public = case['public']
    enum = {'enum': [*public['focus_markers'], witnesses.EXCLUDED, None]}
    schema = fit.record_schema({
        'anchor_witnesses': fit.record_schema(dict.fromkeys(public['candidate_clause_anchors'], enum)),
        'checked_coverage': fit.record_schema({name: {'type': 'boolean'} for name in fit.TASKS}),
    })
    system = '\n'.join((measured.anchored.GUIDANCE, GUIDE))
    user = json.dumps(public, ensure_ascii=False, sort_keys=True)
    return [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}], schema


def decode(case, schema, result):
    missing = {family: {'answer': None, 'focus': None} for family in fit.TASKS}
    if result['finish_reason'] != 'stop':
        return missing, result['finish_reason']
    try:
        payload = json.loads(result['content'])
        jsonschema.validate(payload, schema)
    except (ValueError, jsonschema.ValidationError):
        return missing, 'invalid_transport'
    public = case['public']
    projection = witnesses.project(public['candidate_clause_anchors'], public['focus_markers'],
                                   payload['anchor_witnesses'])
    observations = {
        marker: {**{fit.FAMILIES[family]: state for family, state in rows.items()}, fit.TRIGGER_NAME: True}
        for marker, rows in projection.items()
    }
    return fit.consume(observations, payload['checked_coverage']), None


def prepare():
    executor, cases, observations, grade, exclusions = measured.anchored.materials()
    load = controls.branch.archive.bound_result
    old_path, old_spec, old = load(measured)
    attribution_path, attribution_spec, attribution = load(prior)
    proof = read(old_path / 'same_scope_proofs.json')
    preambles = read(attribution_path / 'source_proofs.json')
    old_prediction_file = old_path / 'sealed_predictions.json'
    old_wire = read(old_path / 'wire_tasks.json')
    prompts = {key: query(case) for key, case in cases.items()}
    if (len(cases) != 9 or sha(grade) != old_spec['reference_sha256']
            or sha(old_prediction_file) != old['predictions_sha256']
            or digest([proof['known'], proof['witness']]) != old_spec['source_evidence_sha256']
            or digest(preambles) != attribution_spec['proofs_sha256']
            or old['terminal_sha256'] != attribution_spec['operative_edges_terminal']):
        raise ValueError('Use the original matched TRAIN cohort, controls and shared source proofs')
    old_raw = read(old_prediction_file)['raw']
    calls, _ = prior.restored(cases, old_spec, executor, old_path, old_raw, old_wire)
    parent, fixed, physical = measured.archive.restore(executor, cases, grade, prompts)
    if (parent != old_spec['original_anchor_terminal'] or physical != old_spec['original_control_calls_sha256']
            or any(old_raw[role] != bank for role, bank in fixed.items())):
        raise ValueError('Require the original same-source, same-input archived calls')
    baseline = {**fixed, 'previous_operative': old_raw['synthesized']}
    proof['preamble'] = {key: (preambles['TRAIN'][key] or {}).get('answer', {}) for key in cases}
    proof['reference_conflicts'] = attribution['scope_label_disagreement_positions']
    dependencies = (__file__, witnesses.__file__, measured.__file__, measured.anchored.__file__,
                    prior.__file__, fit.__file__, controls.__file__, measured.visible.__file__)
    spec = {
        'stage': STAGE, 'partition': 'TRAIN', 'executor': executor, 'TEST_opened': False,
        'TRAIN_grade_sha256': sha(grade), 'TRAIN_observation_terminals': observations,
        'eligible_positions': [case['position'] for case in cases.values()], 'prior_exclusions': exclusions,
        'previous_operative_terminal': old['terminal_sha256'], 'shared_attribution_terminal': attribution['terminal_sha256'],
        'previous_operative_calls_sha256': digest(calls), 'anchored_archive_calls_sha256': physical,
        'matched_inputs_sha256': digest(prompts), 'control_bank_sha256': digest(baseline),
        'shared_proofs_sha256': digest(proof), 'planned_requests': len(prompts),
        'consumer_states': witnesses.check_equivalence(fit.consume, fit.FAMILIES, fit.TRIGGER_NAME),
        'source_sha256': {str(Path(f).relative_to(ROOT)): sha(Path(f)) for f in dependencies},
        'advance_rule': 'Positive mother-paired 95% lower bounds against the original fixed and direct controls '
                        'after identical shared rules. An improvement seen only against one control is reported '
                        'on this development comparison without opening more evaluations.',
    }
    out = BASE / STAGE / digest(spec)
    immutable_json(out / 'binding.json', spec)
    immutable_json(out / 'wire_tasks.json', prompts)
    fit.snapshot(out, spec['source_sha256'])
    return out, spec, cases, grade, prompts, baseline, proof


def measure(out, spec, cases, grade, prompts, baseline, proof):
    ledger = fit.EvolutionLedger(LEDGER, run_id=f'{STAGE}-{out.name[:12]}',
                                 sources={'train': list(cases), 'dev': [], 'test': []}, binding=spec)
    client = fit.FrozenExecutor(ledger, out, spec['executor'])
    client.readiness()
    maximum = spec['executor']['context_tokens'] - spec['executor']['max_tokens']
    if any(client.tokenize(messages, thinking=False)['count'] > maximum for messages, _ in prompts.values()):
        raise ValueError('The frozen model must receive both complete excerpts')
    new = {}
    for key, (messages, schema) in prompts.items():
        call = f'{ledger.run_id}:{digest(key)}'
        write_status(out, {'status': 'running', 'settled': len(new), 'current_request': call}, POINTER)
        raw = client.generate(call, source=key, purpose='skill_actor', messages=messages, schema=schema, thinking=False)
        fit.verify_physical_response(client, identity=call, source=key, purpose='skill_actor',
                                     content_sha256=digest(raw['content']), usage=raw['usage'],
                                     finish_reason=raw['finish_reason'])
        native, error = decode(cases[key], schema, raw)
        new[key] = {'native': native, 'call_id': call, 'tokens': raw['usage']['total_tokens'], 'error': error}
        immutable_json(out / 'responses' / f'{digest(key)}.json', new[key])
        print(f'TRAIN reads settled {len(new)}/{len(cases)}', flush=True)
    raw_bank = {**baseline, 'synthesized': {key: row['native'] for key, row in new.items()}}
    visible = measured.visible
    shared = visible.common_scope(visible.revise(visible.common_scope(raw_bank, proof['known']), proof['witness']),
                                  proof['preamble'])
    prediction_hash = immutable_json(out / 'sealed_predictions.json', {'raw': raw_bank, 'shared': shared})
    if 'train' not in grade.parts or sha(grade) != spec['TRAIN_grade_sha256']:
        raise ValueError('Only score immutable TRAIN annotations after sealing the predictions')
    labels = read(grade)
    values = {role: controls.differences(cases, bank, labels)
              for role, bank in (('raw', raw_bank), ('shared', shared))}
    damage = set(tuple(position) for position in proof['reference_conflicts'])
    omit = {(key, fit.TASKS['negative']) for key, row in cases.items() if tuple(row['position']) in damage}
    sensitivity = prior.sensitivity(cases, shared, labels, omit)
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        totals = dict(db.execute('select status,count(*) from calls group by status'))
        own = dict(db.execute("select status,count(*) from calls where id like ? group by status",
                              (ledger.run_id + ':%',)))
    if own != {'completed': len(cases)} or totals.get('reserved'):
        raise ValueError('Require all physical TRAIN calls to settle before comparison')
    result = sealed({
        'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'predictions_sha256': prediction_hash,
        'scores': values, 'source_fidelity_sensitivity': sensitivity, 'ledger': totals,
        'supports_expanded_validation': all(
            values['shared']['paired_joint_scope'][role]['paired_source_bootstrap_95'][0] > 0
            for role in controls.CONTROLS
        ),
        'TEST_opened': False, 'new_executor_requests': len(new), 'new_teacher_requests': 0,
        'reused_executor_requests': len(baseline) * len(cases),
        'new_tokens': sum(row['tokens'] for row in new.values()),
        'errors': dict(Counter(row['error'] for row in new.values() if row['error'])),
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', result)
    write_status(out, {'status': result['status'], 'terminal_sha256': result['terminal_sha256']}, POINTER)
    print(out, flush=True)


def run(execute):
    out, spec, *inputs = prepare()
    if (out / 'terminal.json').exists():
        return
    if not execute:
        write_status(out, {'status': 'prepared', 'planned_requests': spec['planned_requests']}, POINTER)
        print(out, flush=True)
        return
    state = read(HANDOFF / 'run_state.json')
    if (out != ROOT / read(POINTER)['artifact_root']
            or [job['binding_sha256'] for job in state['active_tasks']] != [out.name]):
        raise ValueError('Register the exact immutable binding before physical dispatch')
    with (out / 'driver.lock').open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        measure(out, spec, *inputs)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('prepare', 'run'))
    run(parser.parse_args().phase == 'run')
