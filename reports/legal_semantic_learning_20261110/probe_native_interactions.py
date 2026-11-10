"""TRAIN-only feasibility probe; abstract condition-literal semantics, no LLM calls."""
import argparse
import copy
import hashlib
import itertools
import json
import random
from pathlib import Path


def paths(node, path=()):
    if 'op' not in node:
        yield path, node
    else:
        for i, child in enumerate(node['items']):
            yield from paths(child, path + (i,))


def get(node, path):
    for i in path:
        node = node['items'][i]
    return node


def key(leaf):
    return leaf.get('tag', ''), leaf.get('text', '')


def evaluate(node, assignment):
    if 'op' not in node:
        return assignment[key(node)]
    values = [evaluate(c, assignment) for c in node['items']]
    if node['op'] == 'AND':
        return all(values)
    if node['op'] == 'OR':
        return any(values)
    raise ValueError('Unsupported operator: ' + node['op'])


def run(dataset_path, manifest_path):
    raw = Path(dataset_path).read_bytes()
    dataset = json.loads(raw)
    manifest = json.loads(Path(manifest_path).read_bytes())
    assert hashlib.sha256(raw).hexdigest() == manifest['source_sha256']
    ids = {r['item_id'] for r in manifest['items'] if r['split'] == 'train'}
    records = []
    eligible = set()
    for item in dataset['items']:
        if item['item_id'] not in ids:
            continue
        rng = random.Random(item['item_id'])
        found = None
        for ui, unit in enumerate(item['gold']['units']):
            if found:
                break
            for bi, branch in enumerate(unit['branches']):
                root = branch['conditions']
                leaves = list(paths(root))
                # Distinct semantic leaves only. Swaps never create/drop nodes.
                unique = {}
                for p, leaf in leaves:
                    unique.setdefault(key(leaf), p)
                if len(unique) < 4:
                    continue
                eligible.add(item['item_id'])
                assignments = []
                keys = sorted(unique)
                if len(keys) <= 6:
                    bits = itertools.product((False, True), repeat=len(keys))
                else:
                    bits = [tuple(bool(rng.getrandbits(1)) for _ in keys) for _ in range(64)]
                assignments = [dict(zip(keys, v)) for v in bits]
                locations = list(unique.values())
                quartets = list(itertools.islice(itertools.combinations(locations, 4), 64))
                rng.shuffle(quartets)
                for quartet in quartets[:16]:
                    # Disjoint leaf swaps: choices are independent and all 4 trees valid.
                    pair_u = (quartet[0], quartet[2])
                    pair_v = (quartet[1], quartet[3])
                    graphs = []
                    original_multiset = sorted(key(v) for _, v in leaves)
                    for a, b in ((0, 0), (0, 1), (1, 0), (1, 1)):
                        graph = copy.deepcopy(root)
                        for active, pair in ((a, pair_u), (b, pair_v)):
                            if active:
                                left, right = get(graph, pair[0]), get(graph, pair[1])
                                saved_left, saved_right = copy.deepcopy(left), copy.deepcopy(right)
                                left.clear()
                                left.update(saved_right)
                                right.clear()
                                right.update(saved_left)
                        assert sorted(key(v) for _, v in paths(graph)) == original_multiset
                        graphs.append(graph)
                    for x in assignments:
                        y = [int(evaluate(g, x)) for g in graphs]
                        interaction = y[3] - y[2] - y[1] + y[0]
                        if interaction:
                            # G00 is reference. Verify signed error identity, too.
                            losses = [abs(v - y[0]) for v in y]
                            j = losses[3] - losses[2] - losses[1] + losses[0]
                            assert j == (1 - 2*y[0]) * interaction
                            found = {
                                'item_id': item['item_id'], 'unit_index': ui,
                                'branch_index': bi, 'pair_u': pair_u, 'pair_v': pair_v,
                                'assignment': [{'tag': k[0], 'text': k[1], 'value': int(v)} for k, v in x.items()],
                                'activation_00_01_10_11': y, 'interaction': interaction,
                                'directed_error_interaction': j,
                            }
                            break
                    if found:
                        break
                if found:
                    break
        if found:
            records.append(found)
    return {
        'purpose': 'native TRAIN structural-supervision feasibility, not learning performance',
        'source_sha256': hashlib.sha256(raw).hexdigest(),
        'train_sources': len(ids), 'sources_with_four_distinct_leaves_in_a_branch': len(eligible),
        'sources_with_observed_nonzero_interaction': len(records),
        'semantics': 'truth of normalized condition literals; not legal-case facts',
        'coverage': 'bounded deterministic search; missing witness does not prove zero interaction',
        'search': {'quartets_per_branch_max': 16, 'assignments_per_quartet_max': 64},
        'records': records,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', required=True)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = run(args.data, args.manifest)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'records'}, ensure_ascii=False))
