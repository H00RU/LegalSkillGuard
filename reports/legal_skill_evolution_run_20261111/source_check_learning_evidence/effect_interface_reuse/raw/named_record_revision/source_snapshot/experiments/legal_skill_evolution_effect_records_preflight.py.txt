"""One named-record revision after the preserved actual positional-slot failure."""
import argparse
import fcntl
import json
from pathlib import Path

from experiments.legal_skill_evolution_effect_slots_preflight import prepare, OUT, RUN
from experiments.legal_skill_evolution_refutation_learning import ROOT, sha, read
from experiments.legal_skill_evolution_residual_calibration import source_record
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.runtime import decoder_schema
from legal_skill_guard.skill_evolution.source_effect_records import messages, schema, decode

DEST = OUT/'named_record_revision'


def run(focus):
    old, bundle, source, units = prepare()
    if focus not in old['subsequent_actual_acquired_focus_units']:
        raise ValueError('Unplanned source focus')
    paths = [Path(__file__).resolve(), ROOT/'legal_skill_guard/skill_evolution/source_effect_records.py',
             ROOT/'tests/test_skill_evolution_source_effect_records.py']
    p = {'run_id': RUN+':named_record_revision', 'same_goal': True, 'goal_complete': False,
         'source': source['key'], 'profile': old['profile'], 'teacher_requests': 0,
         'focuses_from_original_acquired_plan': old['subsequent_actual_acquired_focus_units'],
         'first_actual_failure_sha256': sha(OUT/'focus_58/raw_result.json'),
         'failure_audit_sha256': sha(OUT/'first_failure_audit.json'),
         'change': 'Explicit named source fact fields, exact restriction phrases and model-supplied exception links; no DSL inventory or expression positions in model input. Deterministic lowering reuses acquired constructors.',
         'offline_evidence': 'Named-field regression preserves distinct actors and restrictions; rejects missing fields, invalid exception links, fabricated text, incompatible timing and old positional output.',
         'no_old_result_repair': True, 'no_same_prompt_retry': True,
         'shared_engineering_not_learned_method_or_new_source': True,
         'no_validation_repair_full_training_DEV_TEST_or_paper': True,
         'source_sha256': {str(p.relative_to(ROOT)): sha(p) for p in paths}}
    immutable_json(DEST/'protocol.json', p)
    for path, h in p['source_sha256'].items():
        assert sha(ROOT/path) == h
        dst = DEST/'source_snapshot'/path
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists(): assert dst.read_bytes() == (ROOT/path).read_bytes()
        else: dst.write_bytes((ROOT/path).read_bytes())
    folder = DEST/('focus_'+str(focus))
    if (folder/'raw_result.json').exists():
        raise ValueError('Actual result exists; do not repeat it')
    ledger = EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',
                            run_id=p['run_id'], sources={'train': [source['key']], 'dev': [], 'test': []},
                            binding=digest(p))
    client = FrozenExecutor(ledger, folder, p['profile'])
    client.readiness()
    wire, _ = decoder_schema(schema(u['id'] for u in units))
    r = client.generate(p['run_id']+':focus:'+str(focus), source=source['key'], purpose='skill_replay',
                        messages=messages(units, [focus]), thinking=False, schema=wire)
    immutable_json(folder/'raw_result.json', r)
    if r['finish_reason'] != 'stop':
        raise ValueError('Incomplete; no unchanged retry')
    output, facts = decode(bundle['spec'], units, [focus], r['content'])
    immutable_json(folder/'decoded.json', {'source_output': output, 'model_source_facts': facts,
                                          'source_semantics_verified': False})
    result = source_record(bundle, source, {'source_output': {**output, 'complete': False,
        'unresolved': ['Focus-only source check; remaining units are context.', *output['unresolved']]},
        'wire_result': r, 'not_full_source_or_method_success': True})
    immutable_json(folder/'result.json', result)
    print(json.dumps({'focus': focus, 'facts': facts, 'typed_roots': len(output['statements']),
                      'core': sum(v['core_executed'] for v in result['views']),
                      'native_correct': sum(bool(v['score'] and v['score']['correct']) for v in result['views']),
                      'tokens': r['usage'], 'seconds': r['elapsed_seconds'],
                      'source_semantic_review_required': True}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--focus', type=int, default=58)
    args = parser.parse_args()
    with (ROOT/'artifacts/rr_v2_preflight/current_refutation_learning_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        run(args.focus)
