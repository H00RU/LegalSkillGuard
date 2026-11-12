"""Finite shared-codec repair validation; reuse the settled acquired skills.

No new teacher acquisition, source pool, sampling configuration or answer rule.
The first real source pair is inspected before continuing the fixed cohort.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

from legal_skill_guard.rr.client import WireError
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.grounded_relations import (
    read_grounded_relations, role_mentions, pointer_schema)
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.relational_compiler import apply
from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues
from legal_skill_guard.skill_evolution.runtime import decoder_schema, FrozenReads

from experiments.legal_skill_evolution_span_compiler import warm_base
from experiments.legal_skill_evolution_role_TRAIN import physical_snapshot

RUN = 'legal_skill_evolution_grounded_relations_20261113'
PARENT = 'legal_skill_evolution_relational_acquisition_v2_20261113'
ARMS = ('ScopedAcquisition', 'FreeAcquisition')
read = lambda p: json.loads(p.read_text())


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ValueError('Preserve existing result: ' + str(path))
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True) + '\n')


def prepare(root):
    folder = root / 'artifacts' / RUN
    if (folder / 'protocol.json').exists():
        return folder, read(folder / 'protocol.json')
    prior = root / 'artifacts' / PARENT
    settled = read(prior / 'completed.json')
    assert settled['ledger_after']['executor']['total'] == 9324
    before = physical_snapshot(root / 'artifacts/rr_v2_preflight/research_ledger.sqlite3')
    if any(x.get('reserved', 0) for x in before.values()):
        raise ValueError('Reconcile actual pending requests before preparing')
    sources = [next(r['source'] for r in settled['results'][ARMS[0]]
        if r['source'].split(':')[1].startswith(prefix)) for prefix in ('354623', '62fda7', 'de427b', '5cad3f')]
    public = {s['key']: s for s in read(root / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
    shared = read(prior / 'shared_prior_asset.json')
    specs = {a: read(prior / a / 'frozen_candidate.json')['spec'] for a in ARMS}
    offline = []
    for arm in ARMS:
        for key in sources:
            spans, mentions, ambiguous = role_mentions(public[key], specs[arm], shared['spec']['lexicons'])
            schema, _ = decoder_schema(pointer_schema(specs[arm], spans, mentions))
            issues = strict_output_schema_issues(schema)
            if issues:
                raise ValueError(str(issues))
            offline.append({'arm': arm, 'source': key, 'current_lexical_occurrences': len(mentions),
                'ambiguous_occurrences': len(ambiguous), 'strict_decoder_schema_issues': issues})
    paths = list((root / 'legal_skill_guard/skill_evolution').glob('*.py'))
    paths += list((root / 'tests').glob('test_skill_evolution*.py')) + [Path(__file__).resolve()]
    paths += [root / 'configs/legal_skill_evolution_formal_v5_20261111.json',
        root / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json',
        root / 'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json']
    hashes = {}
    for path in sorted(paths):
        rel = path.relative_to(root)
        target = folder / 'source_snapshot' / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
        hashes[str(rel)] = hashlib.sha256(path.read_bytes()).hexdigest()
    profile = read(root / 'configs/legal_skill_evolution_formal_v5_20261111.json')
    protocol = {'run_id': RUN, 'created_utc': datetime.now(timezone.utc).isoformat(),
        'same_goal': True, 'goal_complete': False, 'parent_settled_run': PARENT,
        'question': 'Does grounding array values in acquired current-source lexical occurrences reduce actual role hallucination and preserve applicable native judgments, without changing acquired meanings or programs?',
        'fixed_original_TRAIN_sources': sources, 'arms': list(ARMS),
        'selection': 'The two already observed historical failures354/62f and the two previously fixed TRAIN reuse contractsde427/5cad. No new source pool or blind-data claim.',
        'change': 'Both arms use the same current-source lexical occurrence ID codec for array fields. Only already acquired unambiguous role forms can map to concepts. String fields and frozen procedures remain unchanged. No old response is rewritten.',
        'comparison': 'Shared public codec repair on both frozen independently acquired skills; matched prior semantic-array responses are retained. This is execution-interface validation, not fresh independent acquisition or a contribution claim.',
        'decision_boundary': 'Run the first actual source pair, inspect raw/type/grounding/semantic evidence, then continue only the same fixed cohort if this addresses the concrete failure. No unchanged retries, parameter scans or full study.',
        'new_teacher_calls': 0, 'automatic_retries': 0,
        'executor_profile': profile['executor'], 'source_snapshot': hashes,
        'ledger_before': before, 'no_new_full_training_DEV_TEST_or_paper': True}
    save(folder / 'frozen_skills.json', specs)
    save(folder / 'shared_prior_asset.json', shared)
    save(folder / 'offline_schema_preflight.json', offline)
    save(folder / 'protocol.json', protocol)
    with sqlite3.connect(root / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') as db:
        save(folder / 'ledger_rows_before.json', db.execute('select * from calls order by id').fetchall())
    return folder, protocol


def evaluate(root, through):
    folder, protocol = prepare(root)
    for name, expected in protocol['source_snapshot'].items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
            raise ValueError('Bound source changed: ' + name)
    ledger = EvolutionLedger(root / 'artifacts/rr_v2_preflight/research_ledger.sqlite3',
        run_id=RUN, sources={'train': protocol['fixed_original_TRAIN_sources'], 'dev': [], 'test': []},
        binding=digest(protocol))
    if any(x.get('reserved', 0) for x in physical_snapshot(ledger.path).values()):
        raise ValueError('Wait for actual pending requests; do not restart')
    public = {s['key']: s for s in read(root / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
    grading = read(root / 'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
    old = read(root / 'artifacts/legal_skill_evolution_span_compiler_20261112/protocol.json')
    base = warm_base(root, old)
    specs = read(folder / 'frozen_skills.json')
    lexicons = read(folder / 'shared_prior_asset.json')['spec']['lexicons']
    executor = FrozenExecutor(ledger, folder, protocol['executor_profile'])
    executor.readiness()
    reads = FrozenReads(executor)
    results = []
    for key in protocol['fixed_original_TRAIN_sources'][:through]:
        source = public[key]
        for arm in ARMS:
            path = folder / arm / (key.replace(':', '_') + '.json')
            if path.exists():
                results.append(read(path))
                continue
            records, event, failure = [], None, None
            try:
                records, event = read_grounded_relations(reads, source, specs[arm], lexicons)
            except WireError:
                raise
            except (ValueError, TypeError, KeyError) as exc:
                failure = type(exc).__name__ + ': ' + str(exc)
            inherited = {v['view']: v for v in base[key]['views']}
            views = []
            for view in source['views']:
                value, error = None, failure
                if view['id'] in ('nda-5', 'nda-7') and error is None:
                    try:
                        value = apply(specs[arm], source, view, records)
                    except (ValueError, TypeError, KeyError) as exc:
                        error = type(exc).__name__ + ': ' + str(exc)
                core = value is not None and value['handled'] and error is None
                answer = value['answer'] if core else inherited[view['id']]['execution']['answer']
                proof = sorted({s['public_sentence_id'] for i in value['used_records']
                    for s in records[i]['source_evidence'] if 'public_sentence_id' in s}) if core else []
                score = grade_view(source['dataset'], view, grading[key][view['id']], answer, proof) if core else inherited[view['id']]['score']
                views.append({'view': view['id'], 'answer': answer, 'score': score,
                    'core_executed': core, 'fallback': not core, 'execution': value,
                    'actual_proof_sentence_ids': proof, 'error': error})
            result = {'arm': arm, 'source': key, 'records': records, 'source_event': event,
                'views': views, 'core_views': sum(v['core_executed'] for v in views),
                'core_correct': sum(v['core_executed'] and v['score']['correct'] for v in views),
                'source_semantic_review_pending': True, 'goal_complete': False}
            save(path, result)
            results.append(result)
            print(json.dumps({'arm': arm, 'source': key, 'core': result['core_views'],
                'correct': result['core_correct'], 'error': failure}, ensure_ascii=False), flush=True)
    snapshot = {'results': results, 'ledger_after': physical_snapshot(ledger.path),
        'through_sources': through, 'goal_complete': False, 'semantic_review_pending': True}
    save(folder / ('boundary_' + str(through) + '.json'), snapshot)
    return snapshot


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['prepare', 'evaluate'])
    parser.add_argument('--through', type=int, choices=[1, 2, 3, 4], default=1)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.stage == 'prepare':
        print(prepare(root)[0])
    else:
        evaluate(root, args.through)
