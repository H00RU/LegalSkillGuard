"""Compare a composed operative-edge reader with the archived same-input MAUD controls."""

import argparse
import fcntl
import json
import sqlite3
from pathlib import Path

import jsonschema

from experiments import convergence_revision6_maud_joint_forward as archive
from experiments import convergence_revision6_maud_negative_witness as visible
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import maud_operative_edges as edges
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


STAGE = 'revision6_maud_operative_edges'
POINTER = HANDOFF / f'{STAGE}_current.json'
fit, anchored, controls = archive.fit, archive.archived, archive.calibration
GUIDE = (
    'For each marker, report the two local relations between that occurrence and the two covenant families. '
    'A clause ID means the marker is an operative pandemic condition whose legal effect expressly '
    'governs that covenant anchor. Both parts must be verified. A nearby name, a different governing '
    'action or a different condition does not form that relation. '
    'Choose no_ordinary_edge or no_negative_edge only when you have ruled out the corresponding '
    'relation for this marker. Put null in a slot if its remaining relation is unresolved. '
    'At most one entry may concern each family. The two slots are order independent. '
    'Set checked_coverage for a family only if all relevant markers and visible text for it were checked.'
)


def query(case):
    public = case['public']
    domain = {'enum': [*public['candidate_clause_anchors'], *edges.EXCLUDED, None]}
    record = fit.record_schema({'first': domain, 'second': domain})
    schema = fit.record_schema({
        'observations': fit.record_schema(dict.fromkeys(public['focus_markers'], record)),
        'checked_coverage': fit.record_schema({name: {'type': 'boolean'} for name in fit.TASKS}),
    })
    return ([{'role': 'system', 'content': '\n'.join((anchored.GUIDANCE, anchored.INSTRUCTIONS, GUIDE))},
             {'role': 'user', 'content': json.dumps(public, ensure_ascii=False, sort_keys=True)}], schema)


def decode(case, schema, result):
    missing = {family: {'answer': None, 'focus': None} for family in fit.TASKS}
    if result['finish_reason'] != 'stop':
        return missing, result['finish_reason']
    try:
        payload = json.loads(result['content'])
        jsonschema.validate(payload, schema)
    except (ValueError, jsonschema.ValidationError):
        return missing, 'invalid_transport'
    local = {}
    anchors = case['public']['candidate_clause_anchors']
    for marker, row in payload['observations'].items():
        value = edges.project(anchors, row['first'], row['second'])
        local[marker] = {**dict(zip(fit.FAMILIES.values(), value, strict=True)), fit.TRIGGER_NAME: True}
    return fit.consume(local, payload['checked_coverage']), None


def prepare():
    executor, cases, observations, grade, exclusions = anchored.materials()
    _, _, roster = fit.previous.archive_context()
    sources = {r['key']: r for batch in roster[4:] for r in batch if r['dataset'] == fit.MAUD}
    if len(cases) != 9 or not set(cases) <= set(sources) or any(s['project_split'] != 'train' for s in sources.values()):
        raise ValueError('Use all nine already registered later TRAIN cases with their original two inputs')
    known = {key: controls.resolved(controls.public_proofs(sources[key])) for key in cases}
    witness = {key: visible.source_evidence(sources[key], case['position']) for key, case in cases.items()}
    prompts = {key: query(case) for key, case in cases.items()}
    parent, baseline, physical = archive.restore(executor, cases, grade, prompts)
    _, _, early = controls.branch.archive.bound_result(visible)
    paths = (__file__, edges.__file__, edges.scope.__file__, anchored.__file__, archive.__file__,
             controls.__file__, visible.__file__, visible.witness.__file__, fit.__file__)
    spec = {
        'stage': STAGE, 'TEST_opened': False, 'partition': 'TRAIN', 'executor': executor,
        'reference_sha256': sha(grade), 'formal_TRAIN_observation_terminals': observations,
        'original_anchor_terminal': parent, 'original_control_calls_sha256': physical,
        'applicability': {'original_unrestricted_later_mothers': len(sources), 'positions': [c['position'] for c in cases.values()],
                          'prior_public_exclusions': exclusions},
        'matched_wire_sha256': digest(prompts), 'controls_sha256': digest(baseline),
        'source_evidence_sha256': digest([known, witness]), 'visibility_terminal': early['terminal_sha256'],
        'local_equivalence_states': edges.check_equivalence(), 'planned_new_requests': len(prompts),
        'source_sha256': {str(Path(f).relative_to(ROOT)): sha(Path(f)) for f in paths},
        'forecast': 'Composing condition and scope at each marker improves late TRAIN native classification over both '
                    'same-input controls after the same public-scope and witness rules. Count source-matched pairs, '
                    'and enlarge validation only if the paired lower bounds are positive against both controls.',
        'design': 'Reuses the complete earlier registered B5–B8 scope as a previously examined TRAIN comparison.',
    }
    root = BASE / STAGE / digest(spec)
    immutable_json(root / 'binding.json', spec)
    immutable_json(root / 'wire_tasks.json', prompts)
    immutable_json(root / 'same_scope_proofs.json', {'known': known, 'witness': witness})
    fit.snapshot(root, spec['source_sha256'])
    return root, spec, cases, prompts, grade, baseline, known, witness


def measure(out, spec, cases, prompts, grade, baseline, known, witness):
    ledger = fit.EvolutionLedger(LEDGER, run_id=f'{STAGE}-{out.name[:12]}',
                                 sources={'train': list(cases), 'dev': [], 'test': []}, binding=spec)
    client = fit.FrozenExecutor(ledger, out, spec['executor'])
    client.readiness()
    capacity = spec['executor']['context_tokens'] - spec['executor']['max_tokens']
    if any(client.tokenize(messages, thinking=False)['count'] > capacity for messages, _ in prompts.values()):
        raise ValueError('No matched original excerpt may be truncated')
    candidate, records = {}, {}
    for index, (key, (messages, schema)) in enumerate(prompts.items()):
        call = f'{ledger.run_id}:{digest(key)}'
        write_status(out, {'status': 'running', 'requests_settled': index, 'current_request': call}, POINTER)
        result = client.generate(call, source=key, purpose='skill_actor', messages=messages, schema=schema, thinking=False)
        fit.verify_physical_response(client, identity=call, source=key, purpose='skill_actor',
                                     content_sha256=digest(result['content']), usage=result['usage'],
                                     finish_reason=result['finish_reason'])
        candidate[key], error = decode(cases[key], schema, result)
        records[key] = {'id': call, 'tokens': result['usage']['total_tokens'], 'decode_error': error}
        immutable_json(out / 'responses' / f'{digest(key)}.json', {**records[key], 'native': candidate[key]})
        print(f'TRAIN responses settled {index + 1}/{len(cases)}', flush=True)
    raw = {**baseline, 'synthesized': candidate}
    same_scope = visible.common_scope(raw, known)
    comparable = visible.revise(same_scope, witness)
    pred = immutable_json(out / 'sealed_predictions.json', {'raw': raw, 'same_scope': same_scope, 'comparable': comparable})
    if sha(grade) != spec['reference_sha256'] or 'train' not in grade.parts:
        raise ValueError('Score only fixed TRAIN labels after sealing the predictions')
    labels = read(grade)
    results = {name: controls.differences(cases, bank, labels)
               for name, bank in (('raw', raw), ('shared_scope', same_scope), ('shared_visibility', comparable))}
    advance = all(results['shared_visibility']['paired_joint_scope'][arm]['paired_source_bootstrap_95'][0] > 0
                  for arm in controls.CONTROLS)
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        total = dict(db.execute('select status,count(*) from calls group by status'))
        own = dict(db.execute('select status,count(*) from calls where id like ? group by status',
                              (ledger.run_id + ':%',)))
    if own != {'completed': len(cases)} or total.get('reserved'):
        raise ValueError('The experiment must settle all planned physical reads')
    result = sealed({
        'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'predictions_sha256': pred,
        'scores': results, 'train_mothers': len(cases), 'old_responses_reused': 3 * len(cases),
        'new_executor_requests': len(cases), 'new_tokens': sum(row['tokens'] for row in records.values()),
        'decode_errors': sum(bool(row['decode_error']) for row in records.values()),
        'supports_expanded_validation': advance, 'ledger': total, 'new_teacher_requests': 0, 'TEST_opened': False,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', result)
    write_status(out, {'status': result['status'], 'terminal_sha256': result['terminal_sha256']}, POINTER)
    print(out, flush=True)


def run(dispatch):
    out, spec, *inputs = prepare()
    if (out / 'terminal.json').exists():
        print(out, flush=True)
        return
    if not dispatch:
        write_status(out, {'status': 'prepared', 'planned_requests': spec['planned_new_requests']}, POINTER)
        print(out, flush=True)
        return
    if ROOT / read(POINTER)['artifact_root'] != out:
        raise ValueError('Use the registered binding for the original matched TRAIN cohort')
    with (out / 'driver.lock').open('a') as flag:
        fcntl.flock(flag, fcntl.LOCK_EX | fcntl.LOCK_NB)
        measure(out, spec, *inputs)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('prepare', 'run'))
    run(parser.parse_args().phase == 'run')
