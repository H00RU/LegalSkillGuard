"""Finite source-compiler control after actual Qwen acquisition failures."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from experiments.rr_v2_legal_support_acquisition import COMMON, REVIEW_SCHEMA
from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.legal_support_ranges import (
    INPUTS, PAL_SCHEMA, PROFILE_SCHEMA, evaluate_pal, validate_profile)
from legal_skill_guard.rr.method_client import MethodTeacher
from legal_skill_guard.rr.method_ledger import MethodLedger

ROOT = Path(__file__).resolve().parents[1]
RUN = 'legal_support_teacher_v1_20261110'
STAGE = ROOT / 'artifacts/rr_method_redesign_20261109' / RUN
PROTOCOL = ROOT / 'reports/method_redesign_20261109/legal_support_teacher_protocol.md'


def read(path):
    return json.loads(path.read_text())


def prepare():
    old = read(ROOT / 'artifacts/rr_method_redesign_20261109/legal_support_acquisition_v1_20261110/seal.json')
    material = {k: v for k, v in old['material'].items() if k != 'frozen_previous_TRAIN_program'}
    review_schema = deepcopy(REVIEW_SCHEMA)
    review_schema['properties']['comparison']['type'] = 'string'
    schemas = {'profile': PROFILE_SCHEMA, 'pal': PAL_SCHEMA, 'review': review_schema}
    for name, schema in schemas.items():
        assert not strict_output_schema_issues(schema), (name, strict_output_schema_issues(schema))
    systems = {
        'profile': COMMON + (' Use the existing source-compiler role. Return a compositional upper-bound summary for all eight source blocks. '
            'Each output relation automatically includes its corresponding known_* input. '
            'supports/forwards add possible positive claimants to the declared output; amount_only/removes_only introduce none and have output none. '
            'Reference intermediate relations only in an acyclic dependency graph. Use the exact declared identifiers. '
            'An expression is one set function, not an enumeration of allowed grammar alternatives. '
            'The supplied source is complete for this task; no old local-module restrictions apply. Return only the schema.'),
        'pal': COMMON + (' Use the existing source-compiler role. Return one complete compact root deduction151 set expression. '
            'Use exact input identifiers and focus only, no intermediate relation names. '
            'Include all explicit positive interface inputs and all positive source constructors conservatively. '
            'An expression is one set function, not an enumeration of allowed grammar alternatives. '
            'The supplied source is complete for this task; no old local-module restrictions apply. '
            'Unresolved source meaning must be declared, never silently removed. Return only the schema.'),
        'review': ('Review the two independently generated support upper bounds against the full supplied source. '
            'Do not repair either output or give a replacement. Sound means every possible positive section151 claimant for focus/year is included under the declared inputs; it does not mean all candidates are entitled. '
            'Check explicit interface statuses, self/spouse, necessary152 relationship/household anchors, amount and removing-only effects, and any implicit closed-world assumption. '
            'Compare both equally; cite the supplied law. This is a source semantics judgment, not a formal proof of natural-language fidelity. Return only the schema.')}
    files = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in (
        'experiments/rr_v2_legal_support_teacher.py', 'experiments/rr_v2_legal_support_acquisition.py',
        'legal_skill_guard/rr/legal_support_ranges.py', 'legal_skill_guard/rr/method_client.py',
        'legal_skill_guard/rr/method_ledger.py', 'legal_skill_guard/rr/client.py',
        'legal_skill_guard/inference/codex_cli_client.py')}
    seal = {'run_id': RUN, 'files': files,
            'binding': {'code_hash': digest(files), 'config_hash': digest(old['config'])},
            'config': old['config'], 'sources': old['sources'], 'source_ids': old['source_ids'],
            'material': material, 'systems': systems, 'schemas': schemas,
            'protocol_sha256': hashlib.sha256(PROTOCOL.read_bytes()).hexdigest(),
            'same_source_both_arms': True, 'case_facts_queries_answers_or_DEV_provided': False,
            'old_partial_program_not_in_prompt': True, 'goal_complete': False}
    immutable_json(STAGE / 'seal.json', seal)
    return seal


def generate(seal, action):
    path = STAGE / (action + '.json')
    if path.exists():
        print(json.dumps({'existing': str(path)})); return
    schema = seal['schemas'][action]
    assert strict_output_schema_issues(schema) == [], 'Preflight before reserving a charged attempt'
    ledger = MethodLedger(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3',
        run_id=RUN, binding=seal['binding'], sources=seal['sources'],
        authorization_hash=seal['protocol_sha256'],
        question='Can the original teacher source compiler acquire source-safe support bounds, and does a compositional representation add actual value over independently acquired compact expressions? Prior executor failures preserved; no case labels or full build.')
    material = seal['material']
    if action == 'review':
        records = {k: read(STAGE / (k + '.json')) for k in ('profile', 'pal')}
        assert all(r['validation']['status'] == 'structurally_valid' for r in records.values())
        material = {'common_source_material': material,
                    'profile': records['profile']['value'], 'pal': records['pal']['value']}
    teacher = MethodTeacher(ledger, STAGE, seal['config']['teacher'])
    wire = teacher.summarize(RUN + ':' + action, source_ids=seal['source_ids'],
        system_prompt=seal['systems'][action], user_prompt=json.dumps(material, ensure_ascii=False),
        output_schema=schema)
    value = wire['value']
    try:
        if action == 'profile':
            validate_profile(value, seal['material']['source_blocks'])
        elif action == 'pal':
            evaluate_pal(value, {k: [] for k in INPUTS}, 'focus')
            if any(not q or not any(q in b for b in seal['material']['source_blocks'].values()) for q in value['quotes']):
                raise ValueError('PAL quote absent from source')
        validation = {'status': 'source_review_captured' if action == 'review' else 'structurally_valid',
                      'NL_source_soundness_proved': False}
    except Exception as exc:
        validation = {'status': 'rejected', 'error_type': type(exc).__name__, 'error': str(exc)}
    immutable_json(path, {'physical_response': wire, 'value': value, 'validation': validation})
    print(json.dumps({'action': action, 'validation': validation, 'value': value}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'profile', 'pal', 'review'])
    action = parser.parse_args().action
    seal = prepare()
    if action == 'prepare':
        print(json.dumps({'prepared': True, 'strict_schemas_valid': True, 'new_calls': 0}))
    else:
        generate(seal, action)
