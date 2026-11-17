"""TRAIN-only finite relation-interface check against native RuleArena code.

This is a source-grounded deterministic fixture, NOT an LLM extraction result,
learned-reader evaluation, new dataset, or claim that scalar buckets are novel.
"""
import ast
import hashlib
import importlib.util
import itertools
import json
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
OUT = Path(__file__).parent
SOURCE_KEY = 'RuleArena_Airline:e88c2c8f441b03bf1e690f5c49450dc95e2fa39d19e589745164f6786caf47a8'
INPUTS = {}


def read(rel):
    p = ROOT / rel
    b = p.read_bytes()
    INPUTS[rel] = {'sha256': hashlib.sha256(b).hexdigest(), 'bytes': len(b)}
    return b


def canonical_hash(x):
    return hashlib.sha256(json.dumps(x, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def parse_prompt(prompt):
    header = re.search(r'^(\w+) is a (.+?) Class passenger flying from (.+?) to (.+?) with', prompt)
    assert header
    evidence = []
    bags = []
    pat = re.compile(r'(?m)^(\d+)\. A (.+?): (\d+) x (\d+) x (\d+) inches, (\d+) lbs;')
    for match in pat.finditer(prompt):
        i, name, a, b, c, w = match.groups()
        bags.append({'id': int(i), 'name': name, 'size': list(map(int, (a, b, c))), 'weight': int(w)})
        evidence.append({'bag_id': int(i), 'start': match.start(), 'end': match.end(), 'quote': match[0]})
    price = re.search(r"flight ticket is \$(\d+)\.", prompt)
    assert price and len(bags) == 5
    # Fixed route normalization is declared, not learned and not a new fact.
    assert (header[3], header[4]) == ('Phoenix', 'Rio de Janeiro')
    args = {'bag_list': bags, 'base_price': int(price[1]), 'customer_class': header[2],
            'direction': 0, 'routine': 'South America'}
    return args, evidence


def load_native():
    rel = 'native_airline'
    directory = ROOT / rel
    code = read(rel + '/compute_answer.py').decode()
    for p in sorted((directory / 'fee_tables').rglob('*.csv')):
        read(p.relative_to(ROOT).as_posix())
    spec = importlib.util.spec_from_file_location('rulearena_native_airline', directory / 'compute_answer.py')
    module = importlib.util.module_from_spec(spec)
    cwd = Path.cwd()
    try:
        os.chdir(directory)
        spec.loader.exec_module(module)
    finally:
        os.chdir(cwd)
    return module, code


def thresholds_from_native(code):
    thresholds = {'size': set(), 'weight': set()}
    for node in ast.walk(ast.parse(code)):
        if isinstance(node, ast.Compare) and len(node.comparators) == 1:
            right = node.comparators[0]
            left = ast.unparse(node.left)
            if isinstance(right, ast.Constant) and isinstance(right.value, int):
                if left == "np.sum(bag['size'])":
                    thresholds['size'].add(right.value)
                elif left == "bag['weight']":
                    thresholds['weight'].add(right.value)
    return {k: sorted(v) for k, v in thresholds.items()}


def encode_one(bag, features, thresholds):
    vals = {
        'dimensions': tuple(bag['size']),
        'dimension_sum': sum(bag['size']),
        'dimension_relations': tuple(sum(bag['size']) > t for t in thresholds['size']),
        'weight': bag['weight'],
        'weight_relations': tuple(bag['weight'] > t for t in thresholds['weight']),
    }
    return tuple(vals[x] for x in features)


def native_local(module, bag):
    # These are actual native intermediate consumers, not final labels.
    return (int(module.compute_oversize(bag, 'South America')),
            int(module.compute_overweight(bag, 'South America', 'Basic Economy', False)))


def fit_decoder(domain, labels, features, thresholds):
    table = {}
    for bag, y in zip(domain, labels):
        h = encode_one(bag, features, thresholds)
        if h in table and table[h] != y:
            return None
        table[h] = y
    return table


def enumerate_groupings(module, features, thresholds):
    # Representation grammar also varies whether it keeps the coupling of
    # dimensions and weight, and whether it keeps the physical-bag anchor.
    representatives = [{'size': [s - 2, 1, 1], 'weight': w}
                       for s in [3, 63, 66] for w in [1, 51, 54, 71]]
    worlds = list(itertools.product(representatives, repeat=2))
    results = {}
    for mode in ['unpaired_marginals', 'joint_unanchored', 'joint_anchored']:
        table = {}
        witness = None
        for world in worlds:
            h = [encode_one(b, features, thresholds) for b in world]
            if mode == 'unpaired_marginals':
                h = (tuple(sorted(x[0] for x in h)), tuple(sorted(x[1] for x in h)))
            elif mode == 'joint_unanchored':
                h = tuple(sorted(h))
            else:
                h = tuple(enumerate(h, start=1))
            local = tuple(native_local(module, b) for b in world)
            y = (local, sum(max(x) for x in local))
            if h in table and table[h][0] != y:
                witness = {'first_world': table[h][1], 'second_world': world,
                           'first_output': table[h][0], 'second_output': y}
                break
            table[h] = (y, world)
        results[mode] = {'valid_for_per_bag_and_total_consumers': witness is None,
                         'collision_witness': witness,
                         'decoder_states_if_valid': len(table) if witness is None else None}
    assert not results['unpaired_marginals']['valid_for_per_bag_and_total_consumers']
    assert not results['joint_unanchored']['valid_for_per_bag_and_total_consumers']
    assert results['joint_anchored']['valid_for_per_bag_and_total_consumers']
    return results


def main():
    source_fixture = json.loads((OUT/'airline_real_relation_fixture.json').read_text(encoding='utf8'))
    assert source_fixture['source_key'] == SOURCE_KEY and source_fixture['split'] == 'TRAIN'
    prompt = source_fixture['prompt']
    args, spans = parse_prompt(prompt)
    assert args == source_fixture['parsed_arguments']
    metadata = {'answer': source_fixture['original_native_answer_for_independent_check']}
    # Native first-bag exclusion is justified on this particular source text.
    assert all(v <= limit for v, limit in zip(args['bag_list'][0]['size'], [22, 14, 9]))
    assert all(sum(b['size']) > 62 for b in args['bag_list'][1:])
    module, code = load_native()
    thresholds = thresholds_from_native(code)
    assert thresholds == {'size': [62, 65], 'weight': [50, 53, 70]}
    # No source labels are used to construct candidates/decoder. Source bag
    # values are within this predeclared finite operational domain.
    domain = [{'size': [s - 2, 1, 1], 'weight': w}
              for s in range(3, 151) for w in range(1, 101)]
    labels = [native_local(module, b) for b in domain]
    grammar = ['dimensions', 'dimension_sum', 'dimension_relations', 'weight', 'weight_relations']
    # Illustrative interface complexity only. Real reader-conditioned learning
    # replaces this with paired model measurements; it is not simulated here.
    cost = dict(dimensions=6, dimension_sum=3, dimension_relations=1,
                weight=3, weight_relations=1)
    valid = []
    invalid = []
    for n in range(1, len(grammar) + 1):
        for features in itertools.combinations(grammar, n):
            table = fit_decoder(domain, labels, features, thresholds)
            if table is None:
                invalid.append(list(features))
            else:
                valid.append((sum(cost[f] for f in features), features, table))
    valid.sort(key=lambda x: (x[0], len(x[1]), x[1]))
    _, features, decoder = valid[0]
    assert features == ('dimension_relations', 'weight_relations')
    grouping_results = enumerate_groupings(module, features, thresholds)
    # Different exact values share an interface and cannot be reconstructed.
    b1, b2 = {'size': [38, 18, 9], 'weight': 64}, {'size': [37, 18, 10], 'weight': 63}
    assert b1 != b2 and encode_one(b1, features, thresholds) == encode_one(b2, features, thresholds)
    assert native_local(module, b1) == native_local(module, b2)
    per_bag = []
    native_total, native_info = module.compute_answer(**args, check_base_tables=module.check_base_tables)
    for b in args['bag_list'][1:]:
        h = encode_one(b, features, thresholds)
        # Decoder table used sums, not these particular triples. It only
        # consumes automatically enumerated threshold relations.
        o, w = decoder[h]
        assert (o, w) == native_local(module, b)
        per_bag.append({'id': b['id'], 'encoding': h, 'oversize': o,
                        'overweight': w, 'surcharge': max(o, w)})
    base_fees = list(map(int, module.compute_base(args['bag_list'][1:], args['direction'],
                     args['routine'], args['customer_class'], module.check_base_tables)))
    assert base_fees == list(map(int, native_info['base']))
    relation_total = args['base_price'] + sum(base_fees) + sum(x['surcharge'] for x in per_bag)
    assert relation_total == int(native_total) == metadata['answer']
    # A source-derived counterfactual is a test, not another real TRAIN row.
    # Unpaired histograms fail because max is taken within each physical bag.
    switched = json.loads(json.dumps(args))
    switched['bag_list'][1]['weight'], switched['bag_list'][3]['weight'] = (
        switched['bag_list'][3]['weight'], switched['bag_list'][1]['weight'])
    def unpaired(a):
        b = a['bag_list'][1:]
        return (sorted(sum(x['size']) for x in b), sorted(x['weight'] for x in b))
    assert unpaired(args) == unpaired(switched)
    switched_total, _ = module.compute_answer(**switched, check_base_tables=module.check_base_tables)
    assert int(switched_total) != int(native_total)
    joint_encoding = [(b['id'], encode_one(b, features, thresholds)) for b in args['bag_list'][1:]]
    fixture = source_fixture
    results = {'status': 'real_TRAIN_native_replay_and_finite_interface_synthesis',
               'source_key': SOURCE_KEY, 'source_count': 1, 'model_calls': 0,
               'prompt_sha256': fixture['prompt_sha256'],
               'source_record_sha256': fixture['record_canonical_sha256'],
               'thresholds_read_from_native_AST': thresholds,
               'finite_local_states': len(domain), 'candidate_subsets': 31,
               'valid_candidates': len(valid), 'invalid_candidates': len(invalid),
               'chosen_features': list(features), 'decoder_states': len(decoder),
               'grouping_candidates': grouping_results,
               'joint_encoding': joint_encoding, 'decoded_per_bag': per_bag,
               'base_fees': base_fees,
               'relation_decoder_total': relation_total, 'native_total': int(native_total),
               'noninvertible_pair_checked': True,
               'unpaired_histogram_counterexample': {'same_unpaired_inputs': True,
                   'original_total': int(native_total), 'counterfactual_total': int(switched_total),
                   'is_new_real_source': False},
               'gain_claimed': False, 'reader_conditioned_selection_tested': False,
               'limitations': ['Exact regex extraction and class/route context are fixed for this fixture.',
                   'Finite-domain preservation only; raw triples differing from domain representatives are covered by source sum-only native access, not new general theorem.',
                   'Single scalar bins are an existing baseline; actual proposed learning must select relation/grouping interfaces under native constraints and measured reader error.',
                   'Raw native functions have dataset-specific semantics; this check does not establish external airline policy correctness.']}
    (OUT / 'airline_real_relation_results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
