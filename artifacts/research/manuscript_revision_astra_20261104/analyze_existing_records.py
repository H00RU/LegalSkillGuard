"""Bounded, model-free analysis for the astra manuscript revision.

Reads immutable records. Writes derivative evidence only in this revision folder.
No teacher, actor, embedding, network, threshold tuning or original-record writes.
"""
import copy
import csv
import hashlib
import json
import socket
import sys
from collections import Counter
from functools import lru_cache
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.append('/media/sangfor/vdb/legal-skill-runtime/inference-qwen3-8b-vllm0102/lib/python3.11/site-packages')

def no_network(*args, **kwargs):
    raise RuntimeError('Network disabled for this analysis')
socket.socket.connect = no_network
socket.create_connection = no_network

from tokenizers import Tokenizer
import experiments.openexempt_online as online
from legal_skill_guard.learning.task_scoped_skills import legal_edit_coordinates, compose_legal_edits
from legal_skill_guard.learning.legal_namespace import allowable_namespaces
from legal_skill_guard.openexempt import metrics
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

def read(path):
    return json.loads((ROOT / path).read_text())

def write(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

def report(value):
    print(json.dumps(value, ensure_ascii=False), flush=True)

tokenizer_path = (sys.argv[1] if len(sys.argv) > 1 else
                  '/media/sangfor/vdb/legal-skill-runtime/models/Qwen3-8B/b968826d9c46dd6066d109eabc6255188de91218/tokenizer.json')
tokenizer = Tokenizer.from_file(tokenizer_path)
@lru_cache(maxsize=None)
def token_count(serialized):
    return len(tokenizer.encode(serialized, add_special_tokens=False).ids)

rows = read('data/packets/openexempt_closed_feedback_public_assets128_20261021/inputs.json')['rows']
row_map = {(r['case_id'], r['family']): r for r in rows}
original_asset_catalog = online.public_asset_catalog
original_law_catalog = online.public_catalog
asset_catalog = {k: original_asset_catalog(r) for k, r in row_map.items()}
law_catalog = {k: original_law_catalog(r) for k, r in row_map.items()}
# Pure public encodings are memoized; actor_payload and all policy/scoring code
# remain the frozen implementations. No server tokenizer or model is contacted.
online.public_asset_catalog = lambda r: copy.deepcopy(asset_catalog[r['case_id'], r['family']])
online.public_catalog = lambda r: copy.deepcopy(law_catalog[r['case_id'], r['family']])
wire_cache = {}
def wire(bank, row, generation):
    key = csha(bank), row['case_id'], row['family']
    if key not in wire_cache:
        messages, schema, _ = online.actor_payload(row, bank, grounded=True,
            direct_numeric=True, asset_references=True)
        wire_cache[key] = csha({'messages': messages, 'schema': schema, 'generation': generation})
    return wire_cache[key]

def assess(parent, proposed, parent_rows, proposed_rows, seen, current_ids, cfg, contract):
    pc = [r for r in parent_rows if r['case_id'] in current_ids]
    pp = [r for r in parent_rows if r['case_id'] not in current_ids]
    qc = [r for r in proposed_rows if r['case_id'] in current_ids]
    qp = [r for r in proposed_rows if r['case_id'] not in current_ids]
    whole = online.acceptance(pc, qc, pp, qp, contract=contract)
    coords = legal_edit_coordinates(parent, proposed, seen)
    gates = online.legal_scope_admission(coords, pc, qc, pp, qp, contract=contract)
    admitted = [c['id'] for c in coords if gates[c['id']]['accepted']]
    pmap = {(r['case_id'], r['family']): r for r in parent_rows}
    qmap = {(r['case_id'], r['family']): r for r in proposed_rows}
    composition, comp_gate, comp_rows, comp_error = None, None, None, None
    if admitted:
        try:
            composition = compose_legal_edits(parent, proposed, coords, admitted)
            if token_count(json.dumps(composition, ensure_ascii=False, separators=(',', ':'))) > cfg['library_token_hard_cap']:
                raise ValueError('composed library exceeds recorded token cap')
            comp_rows = []
            for row in seen:
                key = row['case_id'], row['family']
                value = wire(composition, row, cfg['generation'])
                if value == wire(parent, row, cfg['generation']):
                    comp_rows.append(pmap[key])
                elif value == wire(proposed, row, cfg['generation']):
                    comp_rows.append(qmap[key])
                else:
                    raise ValueError('composed full request matches neither measured side')
            cc = [r for r in comp_rows if r['case_id'] in current_ids]
            cp = [r for r in comp_rows if r['case_id'] not in current_ids]
            comp_gate = online.acceptance(pc, cc, pp, cp, contract=contract)
        except ValueError as exc:
            comp_error = str(exc)
    wg = online.balanced_replay_gain(parent_rows, proposed_rows, contract=contract) if whole['accepted'] else None
    cg = (online.balanced_replay_gain(parent_rows, comp_rows, contract=contract)
          if comp_gate and comp_gate['accepted'] and comp_error is None else None)
    selected = ('joint' if wg is not None and (cg is None or wg >= cg)
                else 'dependency_components' if cg is not None else 'none')
    bank = proposed if selected == 'joint' else composition if selected == 'dependency_components' else parent
    return {'selected': selected, 'bank_sha256': csha(bank), 'whole_accepted': whole['accepted'],
            'whole_current': whole['candidate_current'], 'parent_current': whole['parent_current'],
            'whole_prior': whole['candidate_prior'], 'parent_prior': whole['parent_prior'],
            'whole_gain': wg, 'composition_gain': cg, 'accepted_components': admitted,
            'component_gates': gates, 'component_definitions': coords,
            'composition_error': comp_error, 'composition_bank_sha256': csha(composition) if composition is not None else None}

run_names = ('legal_openexempt_complete_output_utility_public_assets128_20261030_run01',
             'legal_openexempt_v6_strict_policy_control_public_assets128_20261030_run01')
policy_results, decision_mismatches = {}, []
for run_name in run_names:
    cfg = read('configs/' + run_name.removeprefix('legal_') + '.json')
    run = Path('runs') / run_name
    parent, latest, records = [], {}, []
    for batch in range(1, 9):
        first = read(run / 'batches' / f'b{batch}_prequential_records.json')['skills']
        latest.update({(r['case_id'], r['family']): r for r in first})
        current_ids = {r['case_id'] for r in first}
        seen = [r for r in rows if r['case_id'] <= max(current_ids)]
        pub = read(run / 'publications' / f'b{batch}.json')
        for step, d in enumerate(pub['training_decisions'], 1):
            name = f'b{batch}_candidate{step}'
            entry = {'step': name, 'task': d.get('teaching_task'), 'actual_accepted': d['accepted'],
                     'actual_selected': d.get('adaptive_commit_selection', {}).get('selected'),
                     'parent_sha256': csha(parent), 'actual_reason': d.get('reason')}
            if 'actual_replay' in d and 'proposed_bank' in d:
                prows = [latest[r['case_id'], r['family']] for r in seen]
                qrows = d.get('proposed_replay', d['actual_replay'])
                for label, contract in (('utility', online.UTILITY_ADMISSION), ('strict', online.LEGACY_ADMISSION)):
                    entry[label] = assess(parent, d['proposed_bank'], prows, qrows, seen, current_ids, cfg, contract)
                actual = entry['utility' if cfg['admission_contract'] == online.UTILITY_ADMISSION else 'strict']
                wanted = d['candidate'] if d['accepted'] else parent
                if (actual['selected'] != entry['actual_selected'] or actual['bank_sha256'] != csha(wanted)):
                    decision_mismatches.append([run_name, name, actual['selected'], entry['actual_selected']])
                entry['same_pool_policy_choice_differs'] = entry['utility']['bank_sha256'] != entry['strict']['bank_sha256']
                if d['accepted']:
                    parent = d['candidate']
                    latest = {(r['case_id'], r['family']): r for r in d['actual_replay']}
            records.append(entry)
        assert csha(parent) == pub['bank_sha256']
        report({'phase': 'recorded_policy_analysis', 'run': run_name, 'batch': batch})
    policy_results[run_name] = records
assert not decision_mismatches, decision_mismatches
write('recorded_candidates_both_policies.json', {'scope': 'Both policies are read out on the same saved proposal and actual parent at each recorded step. This does not simulate alternate future teaching paths.',
      'actual_decision_reproduction_mismatches': decision_mismatches, 'runs': policy_results,
      'pure_public_catalog_memoization_only': True, 'new_actor_teacher_embedding_calls': 0})

scores = read('runs/legal_openexempt_v6_frozen_source_isolated_IID128_20261031_run01/scored_records.json')
scores['skillcommit_paper45'] = read('runs/legal_openexempt_skillcommit_paper_public_assets128_seed45_20261102_run05/TEST_scored_records.json')
gold_root = ROOT / 'data/packets/openexempt_IID128_confirmatory_TEST_20261030/grading_only'
gold = {int(p.stem): json.loads(p.read_text()) for p in gold_root.glob('*.json')}
error_summary, source_rows = {}, []
for arm, values in scores.items():
    by_task = {}
    for task in ('EC', 'EV'):
        counts = Counter()
        for row in [r for r in values if r['family'] == task]:
            fb = online.native_claim_feedback(row, gold[row['case_id']]['targets'][task])
            counts['sources'] += 1
            counts['invalid'] += int(fb['invalid_response'])
            counts['perfect_complete_score_sources'] += int(row['score']['full_output_f1'] == 1)
            for key in ('correct', 'missing', 'incorrect_value', 'extra_or_duplicate', 'incorrect_value_predictions'):
                counts[key] += fb.get(key, 0)
                counts['sources_with_' + key] += int(fb.get(key, 0) > 0)
            source_rows.append({'condition': arm, 'case_id': row['case_id'], 'source_key': row['source_key'], 'task': task,
                               **row['score'], 'feedback': fb})
        by_task[task] = dict(counts)
    error_summary[arm] = by_task
write('all_condition_error_decomposition.json', {'scope': 'Counts of observed errors in parseable answers; invalid answers are separate, retain zero F1 and are not assigned fabricated claim counts. Source categories can overlap.', 'conditions': error_summary})
with (OUT / 'all_2816_source_scores_and_claim_counts.csv').open('w', newline='') as stream:
    fields = ('condition', 'case_id', 'source_key', 'task', 'f1', 'full_output_f1', 'exact_target', 'invalid_format',
              'full_output_claim_tp', 'full_output_claim_fp', 'full_output_claim_fn')
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(source_rows)

dataset = {}
for split, folder in (('TRAIN', 'openexempt_closed_feedback_public_assets128_20261021'), ('TEST', 'openexempt_IID128_confirmatory_TEST_20261030')):
    split_rows = read(f'data/packets/{folder}/inputs.json')['rows']
    assets, claims, contexts, legal_sets, descriptions = [], [], Counter(), Counter(), set()
    for row in split_rows:
        if row['family'] != 'EC':
            continue
        g = read(f'data/packets/{folder}/grading_only/{row["case_id"]}.json')['targets']['EC']
        assets.append(len(g)); claims.append(sum(len(v) for v in g.values()))
        descriptions.update(g)
        contexts['+'.join(sorted(allowable_namespaces(row)))] += 1
        legal_sets['|'.join(sorted({c for vv in g.values() for c in vv}))] += 1
    dataset[split] = {'sources': len(assets), 'asset_count_histogram': dict(sorted(Counter(assets).items())),
                      'target_claims_min_median_max': [min(claims), float(np.median(claims)), max(claims)],
                      'public_jurisdiction_combinations': dict(contexts), 'distinct_target_citation_sets': len(legal_sets),
                      'distinct_asset_descriptions': len(descriptions), 'asset_descriptions': sorted(descriptions), 'target_citation_sets': sorted(legal_sets)}
dataset['shared_asset_descriptions'] = len(set(dataset['TRAIN']['asset_descriptions']) & set(dataset['TEST']['asset_descriptions']))
dataset['shared_target_citation_sets'] = len(set(dataset['TRAIN']['target_citation_sets']) & set(dataset['TEST']['target_citation_sets']))
write('data_distribution_and_overlap.json', dataset)

stats = read('paper/tables/utility_frozen_results_20261101.json')['paired_statistics']
labels, vectors = [], []
for name, contrast in stats['contrasts'].items():
    for task in ('EC', 'EV'):
        labels.append((name, task))
        vectors.append(contrast['endpoints'][task]['paired_source_differences_pp'])
delta = np.asarray(vectors).T
rng = np.random.Generator(np.random.PCG64(stats['bootstrap_seed']))
draws = np.empty((200000, len(labels)))
for start in range(0, len(draws), 5000):
    idx = rng.integers(len(delta), size=(min(5000, len(draws) - start), len(delta)))
    draws[start:start + len(idx)] = delta[idx].mean(axis=1)
quantiles = [0.025 / 18, 1 - 0.025 / 18]
q20 = np.quantile(draws[:20000], quantiles, axis=0, method='linear')
q200 = np.quantile(draws, quantiles, axis=0, method='linear')
sensitivity = []
for j, (name, task) in enumerate(labels):
    original = stats['contrasts'][name]['endpoints'][task]['conditional_Bonferroni_interval_pp']
    assert np.allclose(q20[:, j], original, atol=1e-11)
    sensitivity.append({'contrast': name, 'task': task, 'original_20000_interval_pp': original,
                        'diagnostic_200000_interval_pp': q200[:, j].tolist(),
                        'positive_lower_bound_unchanged': bool((q20[0, j] > 0) == (q200[0, j] > 0))})
write('bootstrap_numerical_sensitivity_not_replacement.json', {'purpose': 'Numerical tail sensitivity only; original prespecified 20000-draw intervals remain the reported primary intervals.', 'draws': 200000, 'seed': stats['bootstrap_seed'], 'endpoints': sensitivity})
report({'complete': True, 'same_pool_policy_disagreements': {name: [r['step'] for r in data if r.get('same_pool_policy_choice_differs')] for name, data in policy_results.items()},
        'actual_policy_decision_reproduction_errors': len(decision_mismatches),
        'all18_bootstrap_sign_decisions_unchanged_at200k': all(r['positive_lower_bound_unchanged'] for r in sensitivity),
        'error_summary_main': error_summary['utility45']})
