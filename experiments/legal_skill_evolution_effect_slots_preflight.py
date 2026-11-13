"""Bounded original-TRAIN source frontend check, preserving every old result."""
import argparse
import fcntl
import json
from pathlib import Path

from experiments.legal_skill_evolution_refutation_learning import ROOT, read, sha
from experiments.legal_skill_evolution_residual_calibration import source_record
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import source_spans
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.runtime import decoder_schema
from legal_skill_guard.skill_evolution.scoped_grammar import material_public
from legal_skill_guard.skill_evolution.source_effect_slots import messages, schema, decode
from legal_skill_guard.skill_evolution.source_python import plan
from legal_skill_guard.skill_evolution.span_compiler import execution_source_units

RUN = 'legal_skill_evolution_effect_slots_20261113'
OUT = ROOT/'artifacts'/RUN


def prepare():
    prior = ROOT/'artifacts/legal_skill_evolution_refutation_learning_20261113'
    old = read(prior/'protocol.json')
    bundle = read(prior/'effect_actor_bridge/revised_bundle.json')
    source_id = read(OUT/'qualification_audit.json')['actual_TRAIN_source']
    source = next(s for s in read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')
                  if s['key'] == source_id)
    pub = source['views'][0]['public']
    units, _ = execution_source_units(pub['source_text'], source_spans(material_public(pub)))
    queries = plan(bundle['program'], bundle['operations'], pub['source_text'], units)
    focuses = [q['unit_ids'][-1] for q in queries if q['operation'] == 'disposal_retention_clause_role']
    paths = [Path(__file__).resolve(), ROOT/'legal_skill_guard/skill_evolution/source_effect_slots.py',
             ROOT/'tests/test_skill_evolution_source_effect_slots.py']
    protocol = {'run_id': RUN, 'same_goal': True, 'goal_complete': False,
                'source': source_id, 'profile': old['executor_profile'],
                'teacher_requests_planned': 0, 'original_acquisition_TRAIN_only': True,
                'first_focus_unit': 58, 'subsequent_actual_acquired_focus_units': focuses,
                'first_question': 'Can separate literal actors and source-literal typed condition arguments remove the demonstrated shared-interface constraints?',
                'shared_engineering_not_method_contribution': True,
                'only_continue_other_original_source_focuses_after_first_type_and_source_review': True,
                'no_unchanged_retry': True, 'no_new_full_training_DEV_TEST_or_paper': True,
                'no_closed_validation_used_for_repair': True,
                'spec_sha256': digest(bundle['spec']), 'source_public_sha256': digest(pub),
                'source_sha256': {str(p.relative_to(ROOT)): sha(p) for p in paths}}
    immutable_json(OUT/'protocol.json', protocol)
    for p in paths:
        target = OUT/'source_snapshot'/p.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists(): assert target.read_bytes() == p.read_bytes()
        else: target.write_bytes(p.read_bytes())
    return protocol, bundle, source, units


def run(focus):
    p, bundle, source, units = prepare()
    if focus not in p['subsequent_actual_acquired_focus_units']:
        raise ValueError('Undeclared source focus')
    for path, h in p['source_sha256'].items():
        assert sha(ROOT/path) == h, 'Frozen current run source changed'
    folder = OUT/('focus_'+str(focus))
    if (folder/'raw_result.json').exists():
        raise ValueError('A physical result already exists; inspect it rather than rerunning')
    ledger = EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',
                            run_id=RUN, sources={'train': [source['key']], 'dev': [], 'test': []},
                            binding=digest(p))
    client = FrozenExecutor(ledger, folder, p['profile'])
    client.readiness()
    prompt = messages(bundle['spec'], units, [focus])
    wire, _ = decoder_schema(schema(bundle['spec'], [u['id'] for u in units]))
    identity = RUN+':focus:'+str(focus)
    result = client.generate(identity, source=source['key'], purpose='skill_replay',
                             messages=prompt, thinking=False, schema=wire)
    immutable_json(folder/'raw_result.json', result)
    if result['finish_reason'] != 'stop':
        raise ValueError('Incomplete source reading preserved; no unchanged retry')
    output, audit = decode(bundle['spec'], units, [focus], result['content'])
    immutable_json(folder/'decoded.json', {'source_output': output, 'text_argument_audit': audit,
                                          'source_semantics_verified': False})
    scored = source_record(bundle, source, {'source_output': {**output, 'complete': False,
        'unresolved': ['Focus-only frontend check; other source units are context.', *output['unresolved']]},
        'wire_result': result, 'focus_only_not_full_source_or_method_success': True})
    immutable_json(folder/'result.json', scored)
    print(json.dumps({'focus': focus, 'terms': output['statements'], 'unresolved': output['unresolved'],
                      'core': sum(v['core_executed'] for v in scored['views']),
                      'native_correct': sum(bool(v['score'] and v['score']['correct']) for v in scored['views']),
                      'tokens': result['usage'], 'seconds': result['elapsed_seconds'],
                      'source_semantic_review_required': True}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--focus', type=int, default=58)
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    with (ROOT/'artifacts/rr_v2_preflight/current_refutation_learning_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.prepare_only:
            p, _, _, _ = prepare()
            print(json.dumps(p, ensure_ascii=False), flush=True)
        else:
            run(args.focus)
