"""Repair the strong control's actual list-scope defect, then fit fairly.

The same source-only syntax transport is public. C already preserves the actual
de42 list, so its frozen 76/96 candidate is unchanged. This repair receives no
method credit and adds no teacher/executor request or semantic default.
"""
import ast
from copy import deepcopy
import hashlib
import inspect
import json
from pathlib import Path

from experiments import legal_skill_evolution_C_frame_revision as frames
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.source_clause_groups import shared_list_group
from legal_skill_guard.skill_evolution.source_effect_update import function_update
from legal_skill_guard.skill_evolution.source_frame_revision import FAMILIES, candidate_masks, merge
from legal_skill_guard.skill_evolution.source_revision_execution import execute as execute_revision
from legal_skill_guard.skill_evolution.source_revision_guards import vocabulary, fit
from legal_skill_guard.skill_evolution.span_compiler import execute_json

ROOT = frames.ROOT
OUT = ROOT / 'artifacts/legal_skill_evolution_C_control_list_scope_20261116'
PARENT = ROOT / 'artifacts/legal_skill_evolution_C_diagnostic_refinement_20261115'


def run():
    read = frames.stage.read; before = frames.stage.ledger_counts()
    assert not any(status == 'reserved' for _, status, _ in before)
    p = read(PARENT / 'protocol.json')
    old = read(PARENT / 'FreeTeacher/initial_library.json')
    new = read(PARENT / 'FreeTeacher/candidates/UpdatedSuggested.json')
    original = new['composition_program']; tree = ast.parse(original)
    group = ast.get_source_segment(original, next(n for n in tree.body if n.name == 'ft_group_clause'))
    line = '    uid,text=valid[index]\n'
    assert group.count(line) == 1
    group = group.replace(line, '''    grouped=shared_list_group(valid,index)
    if grouped[2]:
        return grouped
''' + line, 1)
    new['composition_program'] = function_update(original, [inspect.getsource(shared_list_group), group])
    immutable_json(OUT / 'repaired_proposal.json', new)
    immutable_json(OUT / 'repair.json', {'original_program_sha256': digest(original),
        'repaired_program_sha256': digest(new['composition_program']),
        'only_syntactic_colon_list_scope_transport_changed': True,
        'no_legal_trigger_or_fact_added': True, 'public_helper_also_available_to_C': True,
        'C_frozen_candidate_unchanged': True, 'not_method_credit': True})
    files = [Path(__file__), ROOT / 'legal_skill_guard/skill_evolution/source_clause_groups.py']
    files += sorted((ROOT / 'legal_skill_guard/skill_evolution').glob('*.py'))
    immutable_json(OUT / 'protocol.json', {'sources': p['sources'], 'all_original_TRAIN': True,
        'fit_timeout_seconds': 120, 'new_model_calls': 0,
        'source_sha256': {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
        'goal_complete': False})
    bank = read(frames.stage.current.generation.OUT / 'raw_source_bank.json')
    previous = frames.stage.saved_rows('FreeTeacher'); texts = []; table = []
    for sid in p['sources']:
        raw = read(frames.stage.current.OUT / 'FreeTeacher/raw_observations' / (digest(sid) + '.json'))
        v = raw['visible_inputs']; texts.append(v['source_text'])
        output = execute_json(new['composition_program'], {'source_text': v['source_text'], 'source_spans': v['units'],
            'source_output': v['source_output'], 'semantic_answers': v['answers']}, {}, allow_helpers=True)
        proposed = frames.assess_output(new, output, sid)
        immutable_json(OUT / 'executed_proposal' / (digest(sid) + '.json'), proposed)
        options = {}
        for mask in candidate_masks():
            number = sum(2 ** sorted(FAMILIES).index(f) for f in mask)
            combined, receipt = merge(previous[sid]['source_output'], output, mask)
            row = frames.assess_output(old, combined, sid); row['revision_receipt'] = receipt
            immutable_json(OUT / 'outcomes' / digest(sid) / (('+'.join(mask) or 'Before') + '.json'), row)
            options[number] = {'native_correct': row['native_correct'], 'source_valid': row['hard_source_pass']}
        table.append(options)
        print(json.dumps({'source': sid, 'proposal_native': proposed['native_correct'],
                          'proposal_source_valid': proposed['hard_source_pass']}), flush=True)
    features = vocabulary([old['composition_program'], new['composition_program']], texts)
    result = fit(features, texts, table, timeout_seconds=120)
    immutable_json(OUT / 'fit.json', result)
    rows = []
    if result['accepted']:
        library = deepcopy(old)
        library['source_revision'] = {'previous': old, 'proposed': new, 'policy': result['policy']}
        immutable_json(OUT / 'selected_library.json', library)
        for sid in p['sources']:
            raw = read(frames.stage.current.OUT / 'FreeTeacher/raw_observations' / (digest(sid) + '.json'))
            executed = execute_revision(library, raw)
            row = frames.assess_output(library, executed['source_output'], sid)
            assert row['hard_source_pass']
            immutable_json(OUT / 'selected_rows' / (digest(sid) + '.json'), row); rows.append(row)
        assert sum(r['native_correct'] for r in rows) == result['native_correct']
    assert frames.stage.ledger_counts() == before
    summary = {k: result[k] for k in ('accepted', 'native_correct', 'optimization_complete', 'policy', 'reason') if k in result}
    immutable_json(OUT / 'result.json', {'FreeTeacher': summary, 'C_unchanged_native_correct': 76,
        'native_total': 96, 'new_model_calls': 0, 'public_correctness_repair_not_method_credit': True,
        'all_results_TRAIN_fit_not_generalization': True, 'goal_complete': False})
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    run()
