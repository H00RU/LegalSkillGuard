"""Verify the delivered plan/manifest consistency without datasets, APIs, or model calls."""
from pathlib import Path
from itertools import combinations
import hashlib
import json

ROOT = Path(__file__).resolve().parent
protocol = json.loads((ROOT / 'protocol.json').read_text(encoding='utf-8'))
manifest = json.loads((ROOT / 'mixed256_candidate_manifest.json').read_text(encoding='utf-8'))
unsigned = {k: v for k, v in manifest.items() if k != 'sha256'}
canonical = json.dumps(unsigned, sort_keys=True, ensure_ascii=False,
                       separators=(',', ':'), allow_nan=False).encode('utf-8')
assert hashlib.sha256(canonical).hexdigest() == manifest['sha256']
assert set(protocol['data']['quota']) == set(manifest['datasets'])
counts = {}
for dataset, splits in manifest['datasets'].items():
    group_sets = {}
    counts[dataset] = {}
    for split in ('train', 'dev', 'test'):
        rows = splits[split]
        assert len(rows) == protocol['data']['quota'][dataset][split]
        counts[dataset][split] = len(rows)
        if dataset == 'NormBench':
            assert len({x['item_id'] for x in rows}) == len(rows)
            group_sets[split] = {x['family_id'] for x in rows}
        else:
            assert len({x['key'] for x in rows}) == len(rows)
            assert len({x['group'] for x in rows}) == len(rows)
            group_sets[split] = {x['group'] for x in rows}
    for a, b in combinations(group_sets, 2):
        assert not group_sets[a] & group_sets[b], (dataset, a, b)
totals = {s: sum(v[s] for v in counts.values()) for s in ('train','dev','test')}
assert totals == protocol['data']['total'] == manifest['allocation']
assert len(protocol['systems']) == protocol['acceptance']['systems'] == 7
assert protocol['phase']['full_mixed_train256'] is True
assert protocol['phase']['test160'] is False
assert protocol['M1']['weak_MML_in_M1_arm'] is False
assert protocol['M2']['contractnli_structure_and_directed_interaction_gold_mask'] == 0
checks = json.loads((ROOT / 'M1_FINITE_CHECK.json').read_text(encoding='utf-8'))
assert len(checks['grid']) == 9
assert checks['external_calls'] == checks['training_runs'] == 0
assert checks['main']['logit_ascent_directions']['robust_common_contexts_0_1'] == 0
summary = {
    'status': 'passed', 'dataset_counts': counts, 'totals': totals,
    'source_group_split_overlap': 0, 'canonical_manifest_sha256': manifest['sha256'],
    'seven_system_matrix': True, 'test_kept_closed': True,
    'finite_algebraic_cases': 9, 'new_model_calls': 0,
    'not_verified_here': ['server latest private exposure', 'server current PID and checkpoint',
                          'learned M1 or M2 performance', 'every native adapter production path']
}
(ROOT / 'PACKET_CHECK.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))
