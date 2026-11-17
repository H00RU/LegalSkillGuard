"""Lock the prescribed pilot and obtain source-only TRAIN graph annotations.

The annotation phase has its own immutable source snapshot. A paid annotation
is a proposed reference, never certified gold merely because its spans match.
No held-out labels or construction metadata are passed to the teacher.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues
from legal_skill_guard.paired_interfaces import graph_interface as gi
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.objects import digest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/two_method_followthrough_20261116'
OUT = BASE / 'annotation_v1'
LEDGER = ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
TRAIN = ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
PROFILE = ROOT / 'configs/legal_skill_evolution_formal_v5_20261111.json'
SYSTEM = gi.SYSTEM + '''
This is source annotation, not question answering or interface optimization.
Use only each view's supplied source units; do not combine facts across views.
Use one stable node per anchored entity/event/effect; link repeated mentions.
Extract all operative relationships expressible in the declared local ontology.
Do not invent an employer, an event link, an inquiry requirement, a permission,
or a covenant attachment from plausibility. A literal term may stay unspecified.
An effect's action, actor, recipient, material, conditions and trigger must refer
to their actual source scope. Keep separate effects and alternative triggers.
If the ontology cannot express a material condition, list it as unresolved.
Do not encode an unknown fact as false. A complete absence in the covered source
can be not_stated; partial reading or ambiguous meaning is unknown/unresolved.
The graph is a proposed reference and will be independently source-checked.
Return every supplied opaque view ID exactly once.'''


def read(path):
    return json.loads(Path(path).read_text())


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inputs(source):
    """Deduplicate identical native source bodies without merging other views."""
    views, mapping, seen = [], {}, {}
    for view in source['views']:
        units = gi.source_units(source, view)
        identity = digest(units)
        if identity not in seen:
            opaque = 'v' + str(len(views))
            seen[identity] = opaque
            views.append({'view_id': opaque, 'source_units': units})
        mapping[view['id']] = seen[identity]
    return {'views': views}, mapping


def output_schema(task):
    return record_schema({'views': {'type': 'array', 'items': record_schema({
        'view_id': {'type': 'string', 'enum': [v['view_id'] for v in task['views']]},
        'graph': gi.schema(),
    })}})


def source_structure(source, sara):
    """Pre-outcome grouping from public syntax; novelty needs a later audit."""
    task, mapping = inputs(source)
    text = '\n'.join(u['text'] for v in task['views'] for u in v['source_units'])
    lower = text.lower()
    bands = lambda n: 0 if n == 0 else 1 if n == 1 else 2
    structure = {
        'unique_source_views': len(task['views']),
        'source_units_band': bands(sum(len(v['source_units']) for v in task['views'])),
        'exception_connectives_band': bands(len(re.findall(r'\b(?:except|unless|provided that|notwithstanding)\b', lower))),
        'alternative_connectives_band': bands(len(re.findall(r'\bor\b', lower))),
        'explicit_date_mentions_band': bands(len(re.findall(r'\b(?:19|20)\d{2}\b', lower))),
        'service_mentions_band': bands(len(re.findall(r'\bservices?\b', lower))),
    }
    return {'public_structure_descriptor': structure,
            'public_structure_group': digest([source['dataset'], structure]),
            'rule_group': sara[source['key']]['query_clause'] if source['key'] in sara
                else digest([source['dataset'], [file_hash_from_text(v['public'].get('source_text', ''))
                                               for v in source['views']]]),
            'shared_SARA_auxiliary_dependencies_not_claimed_isolated': source['dataset'] == 'SARA_v2_Binary',
            'novel_relation_composition_not_established_by_syntax_group': True}


def file_hash_from_text(text):
    return hashlib.sha256(text.encode()).hexdigest()


def prepare():
    source_lock = read(BASE / 'prepared/source_lock.json')
    pilot = read(BASE / 'prepared/pilot_sources.json')
    train = {s['key']: s for s in read(TRAIN)}
    if len(train) != 128 or len(pilot['rows']) != 32:
        raise ValueError('The prescribed TRAIN/pilot cohort changed')
    if digest(pilot) != source_lock['pilot_source_sha256']:
        raise ValueError('Pilot cohort differs from its source lock')
    if file_hash(TRAIN) != source_lock['prepared_sha256']['train']['public']:
        raise ValueError('Preserved original TRAIN bytes changed')
    sara_path = ROOT / 'artifacts/legal_skill_evolution_five_train_20261114/SARA_native_kernel_bank.json'
    sara = {r['source']: r['kernel'] for r in read(sara_path)}
    airline = read(BASE / 'offline_airline_module/generated_interfaces.json')
    weight = airline['candidates']['candidates'][0]
    candidates = {d: gi.plans(weight if d == 'RuleArena_Airline' else None)
                  for d in sorted({s['dataset'] for s in train.values()})}
    if not weight['certificate'].get('array_factorization'):
        raise ValueError('Array-wide application needs the live comparison factorization proof')
    rows = []
    for row in pilot['rows']:
        source = train[row['key']]
        if digest(source) != row['public_sha256']:
            raise ValueError('Pilot source changed')
        rows.append({**row, **source_structure(source, sara),
                     'read_versions': [p['version'] for p in candidates[row['dataset']]]})
    by_group = defaultdict(set)
    for row in rows:
        by_group[row['public_structure_group']].add(row['role'])
    profile = read(PROFILE)
    modules = {
        'SARA_v2_Binary': {'asset': str(sara_path.relative_to(ROOT)), 'sha256': file_hash(sara_path),
                         'kind': 'preserved_native_logic_kernels'},
        'ContractNLI': {'asset': 'legal_skill_guard/paired_interfaces/legal_consumers.py',
                        'function': 'contract', 'kind': 'fixed_explicit_local_consumer'},
        'MAUD': {'asset': 'legal_skill_guard/paired_interfaces/legal_consumers.py',
                 'function': 'maud', 'kind': 'fixed_explicit_local_consumer'},
        'OpenExempt': {'asset': 'artifacts/legal_skill_evolution_20261111/formal_v5/Full/B8.json',
                        'skill': 'personal_asset_exemption_plan_by_solved_regime', 'kind': 'preserved_teacher_learned_program'},
        'RuleArena_Airline': {'asset': 'artifacts/legal_skill_evolution_20261111/formal_v5/Full/B8.json',
                             'skill': airline['fixed_skill_id'], 'kind': 'preserved_teacher_learned_program'},
    }
    for module in modules.values():
        module['sha256'] = file_hash(ROOT / module['asset'])
        module['full_source_meaning_audit_not_established_by_unit_tests'] = True
    locked_files = ['legal_skill_guard/paired_interfaces/graph_interface.py',
        'legal_skill_guard/paired_interfaces/legal_consumers.py',
        'legal_skill_guard/paired_interfaces/residual.py',
        'legal_skill_guard/paired_interfaces/structural_channel.py',
        'legal_skill_guard/paired_interfaces/consumer_worker.py',
        'experiments/two_method_airline_module.py']
    lock = {'protocol': 'two-method-locked-pilot-v1', 'rows': rows,
        'source_lock_sha256': file_hash(BASE / 'prepared/source_lock.json'),
        'upstream_plan_sha256': file_hash(ROOT / 'reports/two_method_followthrough_20261116/PLAN.md'),
        'upstream_protocol_sha256': file_hash(ROOT / 'reports/two_method_followthrough_20261116/protocol.json'),
        'candidate_cap': {'baseline': 1, 'new_per_module': 2, 'no_outcome_driven_additions': True},
        'plans': candidates, 'modules': modules,
        'initial_implementation_sha256': {p: file_hash(ROOT / p) for p in locked_files},
        'executor': profile['executor'], 'teacher': profile['teacher'],
        'role_counts': dict(Counter(r['role'] for r in rows)),
        'shared_public_structure_groups': sorted(k for k, roles in by_group.items() if len(roles) > 1),
        'relation_composition_novelty_audit': 'after source annotation, without resampling or changing roles',
        'M2_unknown_modes': ['unrestricted', 'detectable_residual_conditional_model'],
        'M2_conditional_assumptions': ['fixed read version', 'context conditional stationary edit mixture',
                                      'unknown outcomes outside known edit images in the restrictive mode'],
        'M2_cost_only_selection_is_not_mechanism_evidence': True,
        'structure_evaluation_truth_hidden_from_dictionary_calibration_and_selection': True,
        'source_reference_status': 'teacher_proposed_then_root_source_audited_no_independent_human_claim',
        'no_NEW_DEV_TEST_truth_for_repairs': True,
        'training_mothers': 128, 'training_batches': 8,
        'new_model_calls_before_this_lock': 0,
    }
    immutable_json(BASE / 'pilot_lock.json', lock)
    immutable_json(OUT / 'plans.json', candidates)
    phase_files = locked_files + ['experiments/two_method_annotate.py',
        'legal_skill_guard/skill_evolution/clients.py', 'legal_skill_guard/skill_evolution/ledger.py',
        'legal_skill_guard/skill_evolution/native.py', 'legal_skill_guard/skill_evolution/objects.py',
        'legal_skill_guard/rr/ledger.py', 'legal_skill_guard/rr/checkpoint.py',
        'legal_skill_guard/inference/codex_cli_client.py']
    hashes = {p: file_hash(ROOT / p) for p in phase_files}
    for path, expected in hashes.items():
        target = OUT / 'source_snapshot' / path
        target.parent.mkdir(parents=True, exist_ok=True)
        raw = (ROOT / path).read_bytes()
        if target.exists() and target.read_bytes() != raw:
            raise FileExistsError('Annotation source snapshot changed: ' + path)
        if not target.exists():
            target.write_bytes(raw)
    protocol = {'run_id': 'two_method_annotation_v1_20261116',
        'pilot_lock_sha256': file_hash(BASE / 'pilot_lock.json'),
        'source_lock_sha256': file_hash(BASE / 'prepared/source_lock.json'),
        'source_sha256': hashes, 'teacher': profile['teacher'], 'executor': profile['executor'],
        'annotation_system': SYSTEM, 'annotation_schema': output_schema({'views': [{'view_id': 'v0'}]}),
        'source_only': True, 'teacher_reference_is_not_automatically_gold': True,
        'no_unrequested_retry_or_model_change': True,
    }
    immutable_json(OUT / 'protocol.json', protocol)
    return protocol, lock, source_lock, train


def annotate(stop_after):
    protocol, lock, sources, train = prepare()
    # Verify all frozen phase files immediately before reserving a request.
    for path, expected in protocol['source_sha256'].items():
        if file_hash(ROOT / path) != expected:
            raise ValueError('Annotation source differs from frozen snapshot: ' + path)
    with sqlite3.connect('file:' + str(LEDGER) + '?mode=ro', uri=True) as db:
        if db.execute("select count(*) from calls where status='reserved'").fetchone()[0]:
            raise RuntimeError('An existing physical request must settle before dispatch')
    ledger = EvolutionLedger(LEDGER, run_id=protocol['run_id'], sources=sources['sources'],
        binding={'phase': 'source_only_annotation', 'protocol_sha256': file_hash(OUT / 'protocol.json')})
    teacher = FrozenTeacher(ledger, OUT, protocol['teacher'])
    # Inspect a new CNI development annotation first at a paid-request boundary.
    order = sorted(lock['rows'], key=lambda r: (
        0 if r['dataset'] == 'ContractNLI' and r['role'] == 'development' else 1,
        {'development': 0, 'calibration': 1, 'structure_evaluation': 2}[r['role']], r['key']))
    attempted = 0
    for row in order:
        folder = OUT / 'proposed_references' / digest(row['key'])
        if (folder / 'source_checks.json').exists():
            continue
        task, mapping = inputs(train[row['key']])
        output = output_schema(task)
        issues = strict_output_schema_issues(output)
        if issues:
            raise ValueError(issues)
        metadata = {'source': row['key'], 'role': row['role'], 'task': task,
            'native_view_to_opaque_source_view': mapping, 'system_sha256': digest(SYSTEM),
            'output_schema': output, 'no_native_answers_or_questions': True}
        immutable_json(folder / 'task.json', metadata)
        call_id = protocol['run_id'] + ':annotate:' + digest(metadata)
        print(json.dumps({'event': 'teacher_dispatch', 'source': row['key'], 'role': row['role'],
                          'view_count': len(task['views']), 'call_id': call_id}), flush=True)
        response = teacher.propose(call_id, source_ids=[row['key']], system_prompt=SYSTEM,
            user_prompt=json.dumps(task, ensure_ascii=False, sort_keys=True), output_schema=output)
        value = response['value']
        expected = {v['view_id']: v['source_units'] for v in task['views']}
        checks, seen, errors = {}, set(), []
        for view in value['views']:
            identity = view['view_id']
            if identity not in expected or identity in seen:
                errors.append('Unexpected or duplicate opaque source view: ' + identity)
                continue
            seen.add(identity)
            try:
                checks[identity] = gi.validate(view['graph'], expected[identity])
            except (ValueError, KeyError) as error:
                errors.append(identity + ': ' + str(error))
        if seen != set(expected):
            errors.append('Missing supplied source views')
        immutable_json(folder / 'source_checks.json', {
            'source': row['key'], 'role': row['role'], 'physical_call_id': call_id,
            'checks': checks, 'errors': errors, 'proposed_value_sha256': digest(value),
            'source_semantic_truth_verified': False, 'reference_ready': False,
            'requires_root_source_review_before_use': True,
            'independent_human_annotation_claimed': False,
        })
        print(json.dumps({'event': 'teacher_settled', 'source': row['key'],
                          'span_checks_passed': not errors, 'reference_ready': False,
                          'checks': checks, 'errors': errors}), flush=True)
        attempted += 1
        if stop_after is not None and attempted >= stop_after:
            break


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--prepare', action='store_true', help='Lock inputs without a model request')
    parser.add_argument('--stop-after', type=int, default=None, help='Stop at a settled physical request boundary')
    args = parser.parse_args()
    if args.stop_after is not None and args.stop_after < 1:
        parser.error('--stop-after must be positive')
    if args.prepare:
        protocol, lock, sources, train = prepare()
        print(json.dumps({'pilot_mothers': len(lock['rows']), 'role_counts': lock['role_counts'],
                          'plans_per_dataset': {d: len(v) for d, v in lock['plans'].items()},
                          'phase': protocol['run_id'], 'new_model_calls': 0}))
    else:
        annotate(args.stop_after)


if __name__ == '__main__':
    main()
