"""One preregistered official OE inventory generation; no outcome filtering.

The old 72-source inventory is exhausted. This adds prospective source stock
for DEV/TEST, not TRAIN. It leaves the native generator, grader, old sources,
and all exposure records unchanged. Final fresh splits require a later audit.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
from pathlib import Path
import random
import sqlite3
import time

from legal_skill_guard.openexempt import COMMIT, FAMILIES, UPSTREAM, public_case_key, public_task, upstream
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/two_method_followthrough_20261116/prospective_inventory/OpenExempt'
SEED, COUNT = 20261116, 128


def public_structure(case):
    # Do not use the derived applicable jurisdiction, exemption lists, category
    # labels, target scores, party names, amounts, or exact dates for selection.
    return {'joint_debtor_present': case['joint_debtor'] is not None,
            'asset_descriptions': sorted(a['description'] for a in case['assets']),
            'domicile_jurisdiction_sequence': [value for date, value in sorted(case['domicile_dates'].items())]}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    packet = OUT / 'construction_and_grading_only.json'
    old_path = ROOT / 'history/rr_v2_20261106/data/cache/rr_v2/openexempt_generated.json'
    old = json.loads(old_path.read_text())
    old_keys = {s['group'] for s in old['sources']}
    old_structures = {digest(public_structure(s['construction_only_case'])) for s in old['sources']}
    ledger_path = ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
    ledger_hash = hashlib.sha256(ledger_path.read_bytes()).hexdigest()
    db = sqlite3.connect('file:' + str(ledger_path) + '?mode=ro', uri=True)
    used = {row[0] for row in db.execute("SELECT DISTINCT source FROM calls WHERE source LIKE 'OpenExempt:%'")}
    db.close()
    settings = json.loads((UPSTREAM / 'config.json').read_text())
    settings.update(old['generation_overrides'])
    for key in ('data_directory', 'asset_directory', 'statute_directory', 'template_directory'):
        settings[key] = str(UPSTREAM / settings[key])
    settings.update(dataset_size=COUNT, start_task_id=2,
                    output_directory=str(OUT / 'unused_official_output'))
    lock = {'native_commit': COMMIT, 'seed': SEED, 'inventory_mothers': COUNT,
            'purpose': 'prospective DEV/TEST stock; does not expand the 128-source TRAIN',
            'target_DEV_TEST_mothers': [16, 32],
            'pool_size_rationale': 'One fixed pool allows source and public-structure exclusions before selecting 48 sources.',
            'settings': settings, 'old_pool_sha256': hashlib.sha256(old_path.read_bytes()).hexdigest(),
            'source_hashes': {str(p.relative_to(UPSTREAM)): hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in sorted((UPSTREAM / 'source').glob('*.py'))},
            'selection': 'public-source and public-structure exclusion, then fixed salted source hash; no labels or model outcomes',
            'external_rerolls': False,
            'native_internal_tie_rejection': 'Unchanged official generator rejects ambiguous domicile ties internally.',
            'new_model_calls': 0}
    immutable_json(OUT / 'generation_lock.json', lock)
    if packet.exists():
        saved = json.loads(packet.read_text())
        if saved['lock_sha256'] != digest(lock):
            raise ValueError('Existing generated stock belongs to another lock')
        print(json.dumps({'reused_existing_inventory': True, 'mothers': len(saved['sources']), 'new_model_calls': 0}))
        return
    Config = upstream('source.config').Config
    CaseGenerator = upstream('source.case_generator').CaseGenerator
    TaskGenerator = upstream('source.task_generator').TaskGenerator
    random.seed(SEED)
    configs = {family: Config({**settings, 'terminal_task_id': task_id}, 'two_method_inventory_' + family, False)
               for family, task_id in FAMILIES.items()}
    cases = CaseGenerator(configs['EC'])
    generators = {family: TaskGenerator(config) for family, config in configs.items()}
    sources, seen, candidates, excluded = [], set(), [], []
    started = time.monotonic()
    with contextlib.redirect_stdout(io.StringIO()):
        for index in range(COUNT):
            case = cases.generate_case()
            key = public_case_key(case)
            if key in seen:
                immutable_json(OUT / 'generation_failure.json', {'index': index, 'reason': 'duplicate generated source', 'group': key})
                raise ValueError('Duplicate official source; no reroll authorized')
            seen.add(key)
            tasks, targets = {}, {}
            for family, generator in generators.items():
                task = generator.generate_task(case)
                tasks[family] = public_task(task, index + 1, key, family)
                targets[family] = task.solution
            source_key = 'OpenExempt:' + digest(key)
            structure = digest(public_structure(case.serialize()))
            sources.append({'group': key, 'tasks': tasks, 'targets': targets,
                            'construction_only_case': case.serialize()})
            reasons = []
            if key in old_keys or source_key in used:
                reasons.append('historically_selected_or_called_source')
            if structure in old_structures:
                reasons.append('same_public_structure_as_old_inventory')
            entry = {'key': source_key, 'group': key, 'public_structure_sha256': structure}
            (excluded if reasons else candidates).append({**entry, **({'reasons': reasons} if reasons else {})})
    immutable_json(packet, {'upstream_commit': COMMIT, 'seed': SEED, 'source_cases': COUNT,
                            'generation_overrides': old['generation_overrides'], 'sources': sources,
                            'lock_sha256': digest(lock), 'model_calls': 0, 'resampled_by_outcome': False})
    candidates.sort(key=lambda s: digest({'salt': 'two-method-prospective-OE-v1', 'source': s['key']}))
    audit = {'generated_mothers': COUNT, 'eligible_candidates': candidates, 'excluded': excluded,
             'generation_elapsed_seconds': time.monotonic() - started,
             'packet_sha256': hashlib.sha256(packet.read_bytes()).hexdigest(),
             'final_DEV_TEST_not_locked': True,
             'old_ledger_unchanged': hashlib.sha256(ledger_path.read_bytes()).hexdigest() == ledger_hash,
             'shared_native_rule_package_and_generator_disclosed': True,
             'new_legal_rules_or_M2_structural_transfer_claimed': False,
             'older_nonledger_exposure_audit_pending': True,
             'new_model_calls': 0, 'labels_used_for_selection_or_printed': False}
    immutable_json(OUT / 'inventory_audit.json', audit)
    print(json.dumps({'generated_mothers': COUNT, 'eligible_after_public_exclusions': len(candidates),
                      'excluded_mothers': len(excluded), 'DEV_TEST_locked': False,
                      'new_model_calls': 0, 'old_ledger_unchanged': audit['old_ledger_unchanged']}))


if __name__ == '__main__':
    main()
