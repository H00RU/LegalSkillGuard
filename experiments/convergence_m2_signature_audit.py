"""Measure how many shared signatures the recorded M2 judgments distinguish."""

import argparse
import json
import sqlite3

from experiments.convergence_formal_train_fit import pointer as fit_pointer
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha
from legal_skill_guard.paired_interfaces.shared_semantics import matches_assertions
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


def _batches(through):
    for batch in range(3, through + 1):
        out = ROOT / read(fit_pointer(batch))['artifact_root']
        terminal = read(out / 'terminal.json')
        decisions = read(out / 'matched_decisions.json')
        if (terminal['status'] != 'completed_all_five_TRAIN_updates' or terminal['batch'] != batch
                or terminal['TEST_opened'] or digest(decisions) != terminal['matched_decisions_sha256']):
            raise ValueError('Use the unchanged TRAIN update and its sealed relation decisions')
        for dataset, candidate in decisions['relation'].items():
            if 'explanation_state' in candidate:
                yield f'B{batch}:{dataset}', out, candidate


def _pilots():
    for name, field in (('m2_positive_schema_probe_current.json', 'validation'),
                        ('m2_amount_judgment_probe_current.json', 'candidate_validation')):
        out = ROOT / read(HANDOFF / name)['artifact_root']
        terminal = read(out / 'terminal.json')
        if (terminal['TEST_opened'] or not terminal['status'].startswith('completed_')
                or out.name != digest(read(out / 'binding.json'))):
            raise ValueError('Use the completed TRAIN projection pilot')
        yield name.removesuffix('_current.json'), out, terminal[field]


def _observed_group(db, observation, control):
    allowed = observation['allowed_signatures']
    actual = observation['actual_signature']
    physical = observation['physical_call_ids']
    if (not observation['physical_model_evidence_verified'] or observation['evidence_kind'] != 'actual_model'
            or not allowed or len(actual) != len(physical) or len(physical) != len(observation['root_ids'])
            or control['source_ids'] != observation['source_ids']):
        raise ValueError('Use the exact train projection and its originally audited signatures')
    for call, source in zip(physical, observation['root_ids'], strict=True):
        saved = db.execute('select status,source,purpose from calls where id=?', (call,)).fetchone()
        if saved != ('completed', source, 'skill_actor'):
            raise ValueError('The projected judgment must refer to a settled physical TRAIN call')

    # Constant fields can verify evidence and entailed anchors, but cannot distinguish explanations.
    varying = [{key for key in expected if len({digest(row[i][key]) for row in allowed}) > 1}
               for i, expected in enumerate(allowed[0])]
    judgments = [{k: value if k in varying[i] else None for k, value in row.items()}
                 if isinstance(row, dict) else row for i, row in enumerate(actual)]
    retained = sum(matches_assertions(actual, signature) for signature in allowed)
    by_judgment = sum(matches_assertions(judgments, signature) for signature in allowed)
    if bool(retained) != observation['locally_allowed'] or by_judgment < retained:
        raise ValueError('Masking observations must preserve every previously compatible signature')
    unsupported = {(row['case_index'], row['field']) for row in control.get('unsupported_literal_assertions', [])}
    supported_judgments = [{k: None if (i, k) in unsupported else value for k, value in row.items()}
                           if isinstance(row, dict) else row for i, row in enumerate(judgments)]
    supported = sum(matches_assertions(supported_judgments, signature) for signature in allowed)
    return {'physical_call_ids': physical, 'allowed_signatures': len(allowed), 'matched_by_all_fields': retained,
            'matched_by_varying_fields': by_judgment, 'matched_by_supported_varying_fields': supported,
            'literal_gate_passed': not unsupported,
            'previous_nontrivial_observation_flag': observation['nontrivial_model_relation_observation'],
            'independent_completion_compatible': control['independent_per_case_compatible'],
            'varying_assertions_restrict_shared': by_judgment < len(allowed)}


def run(through):
    rows = []
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        for name, out, candidate in (*_pilots(), *_batches(through)):
            state = candidate['explanation_state']
            groups = [_observed_group(db, obs, control) for obs, control in
                      zip(state['observations'], candidate['matched_controls'], strict=True)]
            gated = all(row['literal_gate_passed'] for row in groups)
            gate = candidate.get('judgment_gate')
            native_gain = candidate['native_utility_sum_delta']
            isolated = (gated and gate in (None, 'passed') and native_gain > 0
                        and all(row['independent_completion_compatible'] for row in groups)
                        and candidate['status'] == 'rejected_by_shared_explanation')
            rows.append({'condition': name, 'terminal_sha256': sha(out / 'terminal.json'),
                         'patch_sha256': state['patch_sha256'], 'native_gain_sum': native_gain,
                         'selection_status': candidate['status'], 'judgment_gate': gate,
                         'isolated_shared_rejection': isolated, 'groups': groups})
    result = {'through_TRAIN_batch': through, 'rows': rows, 'runtime_decisions_edited': False,
              'external_annotation_opened': False, 'new_model_requests': 0}
    out = BASE / 'm2_signature_audit' / digest(result) / 'terminal.json'
    immutable_json(out, result)
    index = {'receipt': str(out.relative_to(ROOT)), 'conditions': len(rows),
             'isolated_shared_rejections': sum(row['isolated_shared_rejection'] for row in rows)}
    immutable_json(HANDOFF / f'M2_signature_through_B{through}_20261118.json', index)
    print(json.dumps(index, sort_keys=True), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--through', type=int, choices=range(3, 9), required=True)
    run(parser.parse_args().through)
