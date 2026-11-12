"""One fixed, zero-model-call NQG baseline on existing TRAIN acquisition.

Prepare and induction do not read native answers.  Evaluation is separate and
only starts after the resulting grammar has been saved and hashed.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.compositional_compiler import (
    acquired_pairs, from_json, induce, induction_config, parse_source, rule_json)
from legal_skill_guard._vendor.nqg.model.qcfg import qcfg_parser
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.source_schema import TASKS
from legal_skill_guard.skill_evolution.span_compiler import execute
from experiments.legal_skill_evolution_role_TRAIN import physical_snapshot
from experiments.legal_skill_evolution_span_compiler import warm_base

RUN = 'legal_skill_evolution_compositional_compiler_20261112'


def read(path):return json.loads(path.read_text())


def prepare(root):
    folder = root / 'artifacts' / RUN; folder.mkdir(exist_ok=True)
    if (folder / 'protocol.json').exists():return folder
    old_path = root / 'artifacts/legal_skill_evolution_span_compiler_20261112/protocol.json'
    old = read(old_path)
    asset_path = root / 'reports/legal_skill_evolution_run_20261111/span_compiler_evidence/shared_compiler_baseline_v1.json'
    spec = read(asset_path)['spec']
    public = {s['key']: s for s in read(root / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
    materials = {k: public[k]['views'][0]['public']['source_text'] for k in old['teacher_sources']}
    pairs, shapes, rejected = acquired_pairs(spec, materials)
    paths = [Path(__file__).resolve(), root / 'legal_skill_guard/skill_evolution/compositional_compiler.py',
        root / 'tests/test_skill_evolution_compositional_compiler.py', root / 'pyproject.toml']
    paths += list((root / 'legal_skill_guard/_vendor/nqg').rglob('*.py'))
    paths += [root / 'legal_skill_guard/_vendor/nqg/UPSTREAM.json', root / 'legal_skill_guard/_vendor/nqg/LICENSE.txt']
    snapshots = {}
    for p in paths:
        rel = p.relative_to(root); target = folder / 'source_snapshot' / rel
        target.parent.mkdir(parents=True, exist_ok=True);target.write_bytes(p.read_bytes())
        snapshots[str(rel)] = hashlib.sha256(p.read_bytes()).hexdigest()
    protocol = {'created_utc': datetime.now(timezone.utc).isoformat(), 'same_goal': True,
        'goal_complete': False, 'type': 'Public NQG grammar baseline; shared acquired asset, not independent acquisition',
        'sources': old['teacher_sources'], 'history': old['history'], 'trigger': old['trigger'],
        'fixed_existing_TRAIN_diagnostics': old['frozen_TRAIN_probes'],
        'diagnostics_have_prior_results_not_new_blind_validation': True,
        'new_model_calls': 0, 'no_native_labels_in_induction': True,
        'config': induction_config()._asdict(), 'no_config_sweep': True,
        'asset_sha256': hashlib.sha256(asset_path.read_bytes()).hexdigest(),
        'source_snapshot': snapshots, 'pair_count': len(pairs), 'record_shapes': len(shapes),
        'rejected_acquired_annotations': rejected,
        'ledger_before': physical_snapshot(root / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'),
        'induction_wall_seconds_bound': 600,
        'decision': 'If grammar learns new compositions, evaluate source paths and native semantics. Generic grammar induction is common infrastructure and receives no new-contribution credit.'}
    if any(v.get('reserved', 0) for v in protocol['ledger_before'].values()):raise ValueError('Pending model requests')
    immutable_json(folder / 'acquired_examples.json', {'spec': spec, 'pairs': pairs, 'shapes': shapes})
    immutable_json(folder / 'protocol.json', protocol)
    return folder


def learn(root):
    folder = root / 'artifacts' / RUN
    if (folder / 'frozen_grammar.json').exists():return read(folder / 'frozen_grammar.json')
    data = read(folder / 'acquired_examples.json'); started = time.monotonic()
    rules = induce(data['pairs'])
    result = {'rules': [rule_json(r) for r in rules], 'wall_seconds': time.monotonic() - started,
        'compositional_rules': sum(r.arity > 0 for r in rules), 'roundtrips': [
            qcfg_parser.can_parse(p['source'], p['target'], rules) for p in data['pairs']],
        'new_model_calls': 0, 'before_native_evaluation': True, 'goal_complete': False}
    assert all(result['roundtrips'])
    immutable_json(folder / 'frozen_grammar.json', result)
    return result


def evaluate(root):
    folder = root / 'artifacts' / RUN
    if (folder / 'completed.json').exists():return read(folder / 'completed.json')
    protocol = read(folder / 'protocol.json'); data = read(folder / 'acquired_examples.json')
    frozen = read(folder / 'frozen_grammar.json'); rules = [from_json(r) for r in frozen['rules']]
    public = {s['key']: s for s in read(root / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
    # The grammar is frozen before this first grading-file access.
    grading = read(root / 'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
    old = read(root / 'artifacts/legal_skill_evolution_span_compiler_20261112/protocol.json')
    base = warm_base(root, old)
    results = []
    for key in protocol['sources'] + protocol['fixed_existing_TRAIN_diagnostics']:
        saved = folder / 'source_results' / (key.replace(':', '_') + '.json')
        if saved.exists():results.append(read(saved));continue
        source = public[key]; started = time.monotonic(); error = None
        try:records, rejected = parse_source(source['views'][0]['public']['source_text'], rules, data['shapes'], data['spec'])
        except (ValueError, TimeoutError) as e:records, rejected, error = [], [], str(e)
        oldviews = {v['view']: v for v in base[key]['views']};rows = []
        for view in source['views']:
            value = None
            if view['id'] in TASKS and error is None:
                try:value = execute(data['spec']['procedure'], {'task_id': view['id'], 'question': view['public']['question']}, {'records': records})
                except (ValueError, TypeError, KeyError) as e:error = str(e)
            core = value is not None and value['handled'] and error is None
            answer = value['answer'] if core else oldviews[view['id']]['execution']['answer']
            score = grade_view(source['dataset'], view, grading[key][view['id']], answer) if core else oldviews[view['id']]['score']
            rows.append({'view': view['id'], 'answer': answer, 'score': score,
                'core_executed': core, 'fallback': not core,
                'used_records': value['used_records'] if core else [],
                'error': error, 'fallback_basis': None if core else 'Preserved actual common warm-library/NoSkill result; no new-core credit'})
        result = {'source': key, 'wall_seconds': time.monotonic() - started,
            'records': records, 'rejected_decodings': rejected, 'views': rows,
            'core_views': sum(r['core_executed'] for r in rows),
            'core_correct': sum(r['core_executed'] and r['score']['correct'] for r in rows),
            'fallback_views': sum(r['fallback'] for r in rows),
            'native_grade': sum(r['score']['grade'] for r in rows) / len(rows)}
        immutable_json(saved, result);results.append(result)
        print(json.dumps({'source': key, 'records': len(records), 'core': result['core_views'], 'correct': result['core_correct'], 'seconds': result['wall_seconds']}), flush=True)
    ledger = physical_snapshot(root / 'artifacts/rr_v2_preflight/research_ledger.sqlite3')
    assert ledger == protocol['ledger_before']
    result = {'protocol_hash': digest(protocol), 'frozen_grammar_hash': digest(frozen),
        'results': results, 'ledger_after': ledger, 'new_model_calls': 0,
        'contribution_established': False, 'goal_complete': False}
    immutable_json(folder / 'completed.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser();parser.add_argument('stage', choices=['prepare', 'learn', 'evaluate'])
    args = parser.parse_args();root = Path(__file__).resolve().parents[1]
    if args.stage == 'prepare':print(prepare(root))
    elif args.stage == 'learn':
        r = learn(root);print(json.dumps({k: v for k, v in r.items() if k != 'rules'}))
    else:evaluate(root)
