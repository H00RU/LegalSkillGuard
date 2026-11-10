"""Bounded single/mean/robust analysis of the exact shared TRAIN tables.

This does not retrain a model or use DEV/TEST outcomes. Local semantic error is
reported only where an independent native annotation identifies the local fact
or record; case-answer consistency is never relabelled as local semantic truth.
"""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import argparse
import json
import math
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from legal_skill_guard.lsl.data import load_json, write_json, sha
from legal_skill_guard.lsl.local_credit import preference
from legal_skill_guard.lsl.projection import compact


def local_errors(record, primary, block):
    choices = block.get('choices', [])
    if len(choices) != 2:
        return None
    if record['dataset'] == 'ProofWriter_OWA_depth5':
        from legal_skill_guard.rr.public_horn import parse_atom
        from legal_skill_guard.lsl.horn_codec import normalize, atom
        quote = block.get('quote')
        if quote not in record['public']['facts']:
            return None
        annotation = parse_atom(quote)
        expected = [annotation.predicate, list(annotation.arguments), annotation.positive]
        if expected not in normalize(record['grade']['horn'])['facts']:
            return None
        return [int(choice is None or atom(choice) != expected) for choice in choices]
    if record['dataset'] == 'NormBench':
        from legal_skill_guard.lsl.native_semantics import norm_graph
        from legal_skill_guard.lsl.composition_data import gold_graph, canonical_graph
        from legal_skill_guard.lsl.role_codec import encode_native
        graph = norm_graph(record, primary)
        gold = gold_graph(record['native_record'])
        index = block.get('slot')
        if type(index) is not int or not 0 <= index < len(graph['nodes']):
            return None
        def context(value, slot):
            value = deepcopy(value)
            value['nodes'][slot].update(tag='__LOCAL_SLOT__', text='__LOCAL_SLOT__')
            return canonical_graph(value)
        signature = context(graph, index)
        targets = {compact(encode_native({'tag': node['tag'], 'text': node['text']}))
                   for i, node in enumerate(gold['nodes'])
                   if node['kind'] == 'leaf' and node['unit'] == graph['nodes'][index]['unit']
                   and context(gold, i) == signature}
        if len(targets) != 1:
            return None
        return [int(compact(choice) not in targets) for choice in choices]
    # Neither a model judgement nor a single case label identifies an arbitrary
    # SARA/Airline rule assignment's full local semantics.
    return None


def signed_preference(value):
    return 0 if value > 0 else 1 if value < 0 else None


def analyze(out, bank):
    rows = {r['key']: r for r in load_json(out / 'open_dataset.json')['records'] if r['split'] == 'train'}
    tables = load_json(bank / 'local/tables.json')
    primary = {r['source']: r['result'].get('parsed') for r in load_json(bank / 'results.json')}
    assert len(tables) == 256 and {t['source'] for t in tables} == set(rows) == set(primary)
    evidence = []
    summaries = {}
    for dataset in sorted({r['dataset'] for r in rows.values()}):
        selected = [t for t in tables if t['dataset'] == dataset]
        summaries[dataset] = {'sources': len(selected), 'valid_primary': sum(t['valid'] for t in selected),
            'sources_with_blocks': sum(bool(t.get('blocks')) for t in selected), 'blocks': 0,
            'credit_statuses': Counter(), 'methods': {m: {'updates': 0, 'independently_scored': 0, 'local_semantic_errors': 0}
                for m in ('single', 'mean', 'robust')}, 'robust_multi_completion': 0,
            'robust_independently_fixed_singleton': 0, 'robust_exhaustive_singleton': 0,
            'single_vs_robust_disagreements': 0, 'mean_vs_robust_disagreements': 0}
    for table in tables:
        record = rows[table['source']]
        summary = summaries[record['dataset']]
        for index, block in enumerate(table.get('blocks', [])):
            summary['blocks'] += 1
            losses = block.get('loss_table', [])
            item = {'source': record['key'], 'dataset': record['dataset'], 'block': index,
                'quote': block.get('quote'), 'choices': block.get('choices'), 'loss_table': losses,
                'independently_fixed': bool(block.get('independently_fixed')),
                'exhaustive': bool(block.get('exhaustive')),
                'saved_status': block.get('credit', {}).get('status')}
            summary['credit_statuses'][item['saved_status']] += 1
            if not losses:
                item['analysis_status'] = 'no_common_independently_scorable_completion'
                evidence.append(item)
                continue
            assert all(len(pair) == 2 and all(math.isfinite(x) for x in pair) for pair in losses)
            differences = [pair[1] - pair[0] for pair in losses]
            robust = preference(losses, independently_fixed=item['independently_fixed'], exhaustive=item['exhaustive'])
            decisions = {'single': signed_preference(differences[0]),
                'mean': signed_preference(sum(differences) / len(differences)), 'robust': robust['preferred']}
            errors = local_errors(record, primary[record['key']], block)
            item.update(differences=differences, decisions=decisions, robust=robust,
                        independent_local_errors=errors, semantic_error_masked=errors is None)
            for method, choice in decisions.items():
                if choice is None:
                    continue
                stats = summary['methods'][method]
                stats['updates'] += 1
                if errors is not None:
                    stats['independently_scored'] += 1
                    stats['local_semantic_errors'] += errors[choice]
            summary['single_vs_robust_disagreements'] += decisions['single'] != decisions['robust']
            summary['mean_vs_robust_disagreements'] += decisions['mean'] != decisions['robust']
            if robust['preferred'] is not None:
                if len(losses) >= 2:
                    summary['robust_multi_completion'] += 1
                elif item['independently_fixed']:
                    summary['robust_independently_fixed_singleton'] += 1
                else:
                    assert item['exhaustive']
                    summary['robust_exhaustive_singleton'] += 1
            evidence.append(item)
    for summary in summaries.values():
        summary['credit_statuses'] = dict(summary['credit_statuses'])
        for stats in summary['methods'].values():
            n = stats['independently_scored']
            stats['local_semantic_error_rate'] = stats['local_semantic_errors'] / n if n else None
    return {'bank': str(bank.relative_to(ROOT)), 'source_tables_sha256': sha(bank / 'local/tables.json'),
        'primary_results_sha256': sha(bank / 'results.json'), 'fixed_TRAIN_sources': 256,
        'physical_model_requests': 0, 'teacher_calls': 0, 'DEV_TEST_labels_used': False,
        'bounded_same_table_analysis_not_three_retrained_arms': True,
        'unknown_local_semantics_not_filled_from_task_answers': True,
        'summary': summaries, 'blocks': evidence}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--bank', required=True)
    args = parser.parse_args()
    out = ROOT / 'artifacts/lsl_mixed256_20261110'
    bank = Path(args.bank).resolve()
    result = analyze(out, bank)
    write_json(bank / 'local/credit_analysis.json', result)
    print(json.dumps({'bank': result['bank'], 'summary': result['summary'], 'model_calls': 0}, ensure_ascii=False))
