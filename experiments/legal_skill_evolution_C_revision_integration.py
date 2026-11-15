"""Freeze the learned guarded revision and execute it through the current API.

Actual previously paid 8B readings are reused; φ/G and the source revision run
again from current text. Cached per-source outputs are comparison evidence only,
never inputs to the new inference module.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3

from experiments import legal_skill_evolution_C_TRAIN_runtime as current
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.source_concept_execution import convert
from legal_skill_guard.skill_evolution.source_revision_execution import execute as execute_revision

ROOT = current.ROOT
OUT = ROOT / 'artifacts/legal_skill_evolution_C_revision_integration_20261115'
UPDATE = ROOT / 'artifacts/legal_skill_evolution_C_diagnostic_refinement_20261115'
FIT = ROOT / 'artifacts/legal_skill_evolution_C_guarded_revision_20261115'


def counts():
    with sqlite3.connect('file:' + str(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') + '?mode=ro', uri=True) as c:
        return c.execute('select role,status,count(*) from calls group by role,status').fetchall()


def run():
    read = current.read; before = counts()
    assert not any(status == 'reserved' for _, status, _ in before)
    p = read(FIT / 'protocol.json'); learned = read(FIT / 'C/fit.json')
    assert learned['accepted']
    old = read(UPDATE / 'C/initial_library.json')
    new = read(UPDATE / 'C/candidates/UpdatedPreviousG.json')
    assert old['operations'] == new['operations'] and old['planner_program'] == new['planner_program']
    library = deepcopy(old)
    library['source_revision'] = {'previous': old, 'proposed': new, 'policy': learned['policy']}
    immutable_json(OUT / 'selected_library.json', library)
    files = [Path(__file__), Path(current.__file__),
             ROOT / 'experiments/legal_skill_evolution_open_acquisition_train.py']
    files += sorted((ROOT / 'legal_skill_guard/skill_evolution').glob('*.py'))
    files += [OUT / 'selected_library.json', FIT / 'C/fit.json']
    files += [current.OUT / arm / 'raw_observations' / (digest(sid) + '.json')
              for arm in ('C', 'FreeTeacher') for sid in p['sources']]
    binding = {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    immutable_json(OUT / 'protocol.json', {'sources': p['sources'], 'source_sha256': binding,
        'all_original_TRAIN_only': True, 'real_new_model_calls': 0, 'thinking_OFF_unchanged': True,
        'no_DEV_TEST': True, 'goal_complete': False})
    for f in files:
        target = OUT / 'source_snapshot' / f.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(f.read_bytes())
    rows = []; conversion_parity = []
    for sid in p['sources']:
        raw = read(current.OUT / 'C/raw_observations' / (digest(sid) + '.json'))
        for label, child in [('previous', old), ('proposed', new)]:
            # New core extractor must preserve every old ABI field, not only
            # final answers on a few examples.
            assert convert(child, raw) == current.convert(child, raw)
            conversion_parity.append({'source': sid, 'producer': label, 'complete_observation_equal': True})
        row = current.assess(library, current.convert(library, raw), sid)
        expected = read(FIT / 'C/selected_rows' / (digest(sid) + '.json'))
        assert row['source_output'] == expected['source_output'] and row['feedback'] == expected['feedback']
        assert row['hard_source_pass']
        immutable_json(OUT / 'rows' / (digest(sid) + '.json'), row); rows.append(row)
    # The same runtime must also execute the ordinary compiler, without G or
    # dependence on method output. This is an ABI check, not an accepted policy.
    free_old = read(UPDATE / 'FreeTeacher/initial_library.json')
    free_new = read(UPDATE / 'FreeTeacher/candidates/UpdatedSuggested.json')
    free = deepcopy(free_old)
    free['source_revision'] = {'previous': free_old, 'proposed': free_new,
        'policy': {'guards': {'disclosure': [None], 'disposal': [None], 'retention': [None]}}}
    ordinary_checks = []
    for sid in read(UPDATE / 'protocol.json')['acquisition_sources']:
        raw = read(current.OUT / 'FreeTeacher/raw_observations' / (digest(sid) + '.json'))
        actual = execute_revision(free, raw)
        expected = read(ROOT / 'artifacts/legal_skill_evolution_C_frame_revision_20261115/FreeTeacher/executed_proposal' / (digest(sid) + '.json'))
        assert actual['source_output'] == expected['source_output']
        ordinary_checks.append({'source': sid, 'actual_ordinary_program_equal': True})
    for path, sha in binding.items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == sha
    assert counts() == before
    immutable_json(OUT / 'result.json', {'native_correct': sum(r['native_correct'] for r in rows), 'native_total': 96,
        'all_existing_partial_source_checks_passed': True, 'core_conversion_parity_checks': conversion_parity,
        'ordinary_runtime_checks': ordinary_checks, 'actual_current_execution_entry_used': True,
        'per_source_output_tables_not_loaded_by_inference': True, 'new_model_calls': 0,
        'TRAIN_fit_not_generalization_or_contribution_completion': True, 'goal_complete': False})
    print(json.dumps({'native_correct': sum(r['native_correct'] for r in rows), 'complete_conversion_parity': len(conversion_parity),
        'ordinary_runtime_parity': len(ordinary_checks), 'new_model_calls': 0, 'goal_complete': False}), flush=True)


if __name__ == '__main__':
    run()
