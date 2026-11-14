"""Replay real paid observations after a common native-interface correction.

Original outputs/contracts/scores remain immutable. No model, label-based fact
repair, or removal of inconvenient observations is available in this review.
"""
import ast
from copy import deepcopy
import json

from experiments import legal_skill_evolution_observation_reuse as previous
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.case_observation_contract import apply_adapter, execute_alternatives
from legal_skill_guard.skill_evolution.literal_facts import literal_bindings
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


OUT = previous.OUT / 'unbound_native_interface_review'


def remove_onset_gate(program):
    """An absent end is native data, not a requirement to prove persistence.

    Only the explicitly identified unsupported extra gate is removed. No
    observation values, dates, positive/negative facts or other guards change.
    """
    tree = ast.parse(program)
    candidates = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if (isinstance(test, ast.Compare) and isinstance(test.left, ast.Name)
                and test.left.id == 'form' and len(test.ops) == 1
                and isinstance(test.ops[0], ast.Eq)
                and len(test.comparators) == 1
                and isinstance(test.comparators[0], ast.Constant)
                and test.comparators[0].value == 'onset_only'):
            assert not node.orelse
            assert any(isinstance(n, ast.Continue) for n in node.body)
            candidates.append(node)
    assert len(candidates) == 1
    node = candidates[0]
    lines = program.splitlines(keepends=True)
    removed = ''.join(lines[node.lineno - 1:node.end_lineno])
    updated = ''.join(lines[:node.lineno - 1] + lines[node.end_lineno:])
    return updated, {'removed_exact_code': removed, 'before_sha256': digest(program),
        'after_sha256': digest(updated), 'no_fact_or_endpoint_added': True}


def question_only_records(value, path=()):
    """Locate record-level query witnesses for semantic review, not auto-repair.

    A view's aggregate witness list can include its query. A death/event record
    cannot establish a positive case fact from that question. This diagnostic
    returns the offending paths and leaves the original record untouched.
    """
    result = []
    if isinstance(value, dict):
        witnesses = value.get('witnesses')
        if (isinstance(witnesses, list) and witnesses
                and all(w.get('field') == 'question' for w in witnesses)):
            result.append({'path': list(path), 'record': deepcopy(value)})
        for key, child in value.items():
            if key != 'witnesses':
                result.extend(question_only_records(child, path + (key,)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            result.extend(question_only_records(child, path + (index,)))
    return result


def run():
    read = previous.read
    contracts = read(previous.OUT / 'frozen_contracts.json')
    public = {s['key']: s for s in read(previous.common.OUT / 'corrected_TRAIN_views.json')}
    kernels = {k['name']: k for k in read(previous.OUT / 'kernel_bank.json')}
    grading = read(previous.ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
    original_rows = read(previous.OUT / 'scored_results.json')['rows']
    changes = {}
    for arm in previous.ARMS:
        contract = contracts[arm]['surviving_spouse_death_window']
        contract['binding_program'], changes[arm] = remove_onset_gate(contract['binding_program'])
    immutable_json(OUT / 'corrected_contracts.json', contracts)
    rows = []
    for original in original_rows:
        source = public[original['source']]
        pub = source['views'][0]['public']
        kernel = kernels[original['kernel']]
        contract = contracts[original['arm']][kernel['name']]
        grounded = apply_adapter(contract, kernel, pub, original['observation'],
            literal_context=literal_bindings({'public': pub}))
        execution = execute_alternatives(kernel, grounded)
        score = grade_view(source['dataset'], source['views'][0],
            grading[source['key']][source['views'][0]['id']], execution['answer'])
        issues = question_only_records(original['observation'])
        rows.append({'source': source['key'], 'arm': original['arm'],
            'raw_observation_sha256': digest(original['observation']),
            'raw_native_score': original['native_score'], 'common_fix_execution': execution,
            'common_fix_score': score, 'query_only_record_witnesses': issues,
            'semantic_review': 'invalid_positive_death_from_query' if issues else 'no_query_only_record_detected',
            'partial_review_is_not_full_semantic_certificate': True,
            'invalid_records_removed': False, 'new_model_calls': 0})
    result = {'rows': rows, 'common_corrections': changes, 'new_model_calls': 0,
        'raw_native_correct': {a: sum(r['raw_native_score']['correct'] for r in rows if r['arm'] == a) for a in previous.ARMS},
        'common_fix_native_correct': {a: sum(r['common_fix_score']['correct'] for r in rows if r['arm'] == a) for a in previous.ARMS},
        'independent_second_contribution_supported': False,
        'query_is_not_evidence_of_positive_case_event': True,
        'all_raw_observations_retained': True, 'goal_complete': False}
    immutable_json(OUT / 'result.json', result)
    print(json.dumps({k: v for k, v in result.items() if k not in ('rows', 'common_corrections')}), flush=True)


if __name__ == '__main__':
    run()
