"""Shared current-Action conformance on already-paid TRAIN observations only.

Original frozen candidates, source outputs and scores remain immutable. This
repairs a consumer/checker interface and confers no source-learning credit.
"""
from copy import deepcopy
import hashlib
import json
import sqlite3
from pathlib import Path

from experiments import legal_skill_evolution_C_TRAIN_runtime as current
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.source_disposal_review import align_source_disposal_consumer
from legal_skill_guard.skill_evolution.span_compiler import validate_procedure

ROOT = current.ROOT
OUT = ROOT / 'artifacts/legal_skill_evolution_source_operator_alignment_20261115'


def ledger():
    with sqlite3.connect(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') as c:
        return c.execute('select role,status,count(*) from calls group by role,status').fetchall()


def run():
    assert (current.OUT / 'all24_reads_collected.json').exists()
    before = ledger()
    assert not any(status == 'reserved' for _, status, _ in before)
    p = current.read(current.OUT / 'protocol.json')
    verified = current.read(current.OUT / 'unbound_semantics_alignment/pre_repair_terminal_binding.json')
    assert verified['source_sha256'] == p['source_sha256']
    for path, sha in p['source_sha256'].items():
        snapshot = current.OUT / 'source_snapshot' / path
        assert hashlib.sha256(snapshot.read_bytes()).hexdigest() == sha
    summaries = {}
    for arm in ('C', 'FreeTeacher'):
        original = current.read(current.OUT / arm / 'candidate.json')
        library = deepcopy(original)
        library['spec']['decision_program'] = align_source_disposal_consumer(original['spec']['decision_program'])
        validate_procedure(library['spec']['decision_program'], allow_helpers=True)
        restored = deepcopy(library)
        restored['spec']['decision_program'] = original['spec']['decision_program']
        assert restored == original
        immutable_json(OUT / arm / 'aligned_candidate.json', library)
        variants = {'NoFit': library}
        if arm == 'C':
            all_rules = deepcopy(library)
            all_rules['selected_rule_ids'] = [r['id'] for r in library['language']['rules']]
            variants['AllRules_diagnosis_not_fitted'] = all_rules
        for name, variant in variants.items():
            rows, changes = [], []
            for sid in p['sources']:
                observation = current.read(current.OUT / arm / 'observations' / (digest(sid) + '.json'))
                result = current.assess(variant, observation, sid)
                old = current.read(current.OUT / arm / 'initial_rows' / (digest(sid) + '.json'))
                if name == 'NoFit':
                    assert result['source_output'] == old['source_output']
                    if (result['native_correct'], result['hard_source_pass']) != (old['native_correct'], old['hard_source_pass']):
                        changes.append({'source': sid, 'before_native': old['native_correct'],
                            'after_native': result['native_correct'], 'before_hard_source': old['hard_source_pass'],
                            'after_hard_source': result['hard_source_pass']})
                immutable_json(OUT / arm / name / (digest(sid) + '.json'), result)
                rows.append(result)
            summary = {'native_correct': sum(r['native_correct'] for r in rows),
                'native_total': sum(r['native_total'] for r in rows),
                'unresolved': sum(r['unresolved'] for r in rows),
                'hard_source_failures': [r['source'] for r in rows if not r['hard_source_pass']],
                'changes_from_saved_initial': changes, 'not_new_generalization_validation': True}
            immutable_json(OUT / arm / name / 'summary.json', summary)
            summaries[arm + '/' + name] = summary
            print(json.dumps({'arm': arm, 'variant': name, **summary}), flush=True)
    after = ledger()
    assert before == after
    immutable_json(OUT / 'result.json', {'summaries': summaries, 'new_model_calls': 0,
        'ledger_before': before, 'ledger_after': after,
        'same_consumer_and_checkers_both_arms': True,
        'source_outputs_unmodified': True, 'DEV_TEST_accessed': False,
        'not_a_learning_contribution': True, 'goal_complete': False})


if __name__ == '__main__':
    run()
