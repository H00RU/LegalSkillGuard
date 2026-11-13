"""Finite controls for joint fields versus direct source-scope reading.

This diagnoses and composes an ordinary shared frontend. It is not a learned
method comparison, a new source, or a retry of the preserved whole-source run.
"""
import argparse
import fcntl
import json
from pathlib import Path

import jsonschema

from experiments.legal_skill_evolution_effect_slots_preflight import prepare, OUT, RUN
from experiments.legal_skill_evolution_refutation_learning import ROOT, read, sha
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.runtime import decoder_schema
from legal_skill_guard.skill_evolution.semantic_execution import strict_json
from legal_skill_guard.skill_evolution.source_effect_records import INFO, messages, schema, decode

DEST = OUT/'factorization_check'


def scope_schema():
    return record_schema({
        'retained_information_scope': {'type': 'string', 'enum': [*INFO, 'unknown']},
        'restriction_phrase': {'type': 'string'},
        'relation_to_return_duty': {'type': 'string',
            'enum': ['exception_to_return_duty', 'independent_effect', 'unknown']},
        'unresolved': {'type': 'array', 'items': {'type': 'string'}}})


def scope_messages(unit):
    return [{'role': 'system', 'content':
        'Read the current clause. What information may be maintained, under what '
        'quantity and purpose restrictions, and does this permission qualify the '
        'return duty in that same clause? Return retained_information_scope using '
        'confidential_information, copies_of_confidential_information, '
        'confidential_information_and_copies, copies_and_derivatives, derivatives, '
        'or unknown. Copy restriction_phrase as an exact continuous source phrase '
        'retaining ALL quantity and purpose restrictions; do not import prior '
        'archival or law-required conditions. Classify relation_to_return_duty as '
        'exception_to_return_duty, independent_effect, or unknown. Explain genuinely '
        'missing semantics in unresolved. Do not answer a downstream legal task.'},
        {'role': 'user', 'content': json.dumps({'current_clause': unit}, ensure_ascii=False)}]


def validate_scope(unit, content):
    value = strict_json(content)
    jsonschema.validate(value, scope_schema())
    if value['restriction_phrase'] and value['restriction_phrase'] not in unit['text']:
        raise ValueError('Restriction is not current-source literal text')
    return value


def run(arm):
    old, bundle, source, units = prepare()
    unit = next(u for u in units if u['id'] == 58)
    paths = [Path(__file__).resolve(), ROOT/'legal_skill_guard/skill_evolution/source_effect_records.py']
    p = {'run_id': RUN+':factorization_check', 'source': source['key'],
         'arms': ['JointNamedFocusOnly', 'DirectScopeFocusOnly'], 'same_goal': True,
         'goal_complete': False, 'profile': old['profile'], 'teacher_requests': 0,
         'whole_source_joint_result_sha256': sha(OUT/'named_record_revision/focus_58/raw_result.json'),
         'source_review_sha256': sha(OUT/'named_record_revision/focus_58/source_review.json'),
         'question': 'Compare source-context burden and joint-field generation using the same original58 clause. Each declared control runs once; no configuration scan or validation repair.',
         'not_method_contribution_or_full_source_validation': True,
         'possible_composition': 'Use actual earlier direct actor observations, supported duty fields and new independent scope/link observations. Preserve all original conflicting observations; never rewrite the old response or fill missing semantic fields.',
         'source_sha256': {str(q.relative_to(ROOT)): sha(q) for q in paths}}
    immutable_json(DEST/'protocol.json', p)
    for path, h in p['source_sha256'].items():
        assert sha(ROOT/path) == h
        target = DEST/'source_snapshot'/path
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists(): assert target.read_bytes() == (ROOT/path).read_bytes()
        else: target.write_bytes((ROOT/path).read_bytes())
    folder = DEST/arm
    if (folder/'raw_result.json').exists():
        raise ValueError('Physical result exists; no unchanged retry')
    if arm == 'JointNamedFocusOnly':
        prompt, host = messages([unit], [58]), schema([58])
    else:
        prompt, host = scope_messages(unit), scope_schema()
    wire, _ = decoder_schema(host)
    ledger = EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',
        run_id=p['run_id'], sources={'train': [source['key']], 'dev': [], 'test': []}, binding=digest(p))
    client = FrozenExecutor(ledger, folder, p['profile'])
    client.readiness()
    r = client.generate(p['run_id']+':'+arm, source=source['key'], purpose='skill_replay',
                        messages=prompt, thinking=False, schema=wire)
    immutable_json(folder/'raw_result.json', r)
    if r['finish_reason'] != 'stop':
        raise ValueError('Incomplete; do not resample')
    value = (decode(bundle['spec'], [unit], [58], r['content'])[1]
             if arm == 'JointNamedFocusOnly' else validate_scope(unit, r['content']))
    immutable_json(folder/'result.json', {'value': value, 'source_semantics_verified': False,
                                        'goal_complete': False})
    print(json.dumps({'arm': arm, 'value': value, 'usage': r['usage'],
                      'seconds': r['elapsed_seconds']}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('arm', choices=['JointNamedFocusOnly', 'DirectScopeFocusOnly'])
    args = parser.parse_args()
    with (ROOT/'artifacts/rr_v2_preflight/current_refutation_learning_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        run(args.arm)
