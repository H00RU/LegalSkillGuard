"""Real TRAIN source, native-rule partial-oracle design check; zero model calls.

The base fare is deliberately unavailable to the relation constructor (a
controlled partial-annotation setting), NOT asserted missing from the source.
Native totals are used only after construction to check the inferred relation.
"""
import copy
import hashlib
import itertools
import json
from pathlib import Path
import re
from airline_real_relation import load_native, parse_prompt, native_local

OUT = Path(__file__).parent


def patch_weights(prompt, changes):
    pattern = re.compile(r'(?m)^(\d+)\. A .+?: \d+ x \d+ x \d+ inches, (\d+) lbs;')
    replacements = []
    for m in pattern.finditer(prompt):
        bag_id = int(m[1])
        if bag_id in changes:
            replacements.append((m.start(2), m.end(2), str(changes[bag_id])))
    assert len(replacements) == len(changes)
    result = prompt
    for start, end, value in reversed(replacements):
        result = result[:start] + value + result[end:]
    return result, replacements


def surcharge(module, bags, mode):
    pairs = [native_local(module, b) for b in bags[1:]]
    if mode == 'joint_max':
        return sum(max(p) for p in pairs)
    if mode == 'add_both':
        return sum(sum(p) for p in pairs)
    if mode == 'independent_marginals':
        # Loses bag binding and then pairs sorted marginals.
        a, b = sorted(p[0] for p in pairs), sorted(p[1] for p in pairs)
        return sum(max(x, y) for x, y in zip(a, b))
    raise ValueError(mode)


def run():
    fixture = json.loads((OUT/'airline_real_relation_fixture.json').read_text(encoding='utf8'))
    prompt = fixture['prompt']
    args, _ = parse_prompt(prompt)
    module, _ = load_native()
    # Generate source edits, not hand-pick expected fee changes or final labels.
    candidates = []
    for left, right in itertools.combinations(args['bag_list'][1:], 2):
        if left['weight'] == right['weight']:
            continue
        changes = {left['id']: right['weight'], right['id']: left['weight']}
        new_prompt, spans = patch_weights(prompt, changes)
        new_args, _ = parse_prompt(new_prompt)
        expected = copy.deepcopy(args)
        for bag in expected['bag_list']:
            if bag['id'] in changes:
                bag['weight'] = changes[bag['id']]
        assert new_args == expected
        # These are reviewed local native consumers, not either model answer.
        a = surcharge(module, args['bag_list'], 'joint_max')
        b = surcharge(module, new_args['bag_list'], 'joint_max')
        delta = b-a
        signatures = {}
        for mode in ['joint_max', 'add_both', 'independent_marginals']:
            signatures[mode] = surcharge(module, new_args['bag_list'], mode)-surcharge(module, args['bag_list'], mode)
        excluded = [mode for mode, value in signatures.items() if value != delta]
        candidates.append({'bag_ids': sorted(changes), 'source_delta': changes,
                           'allowed_output_relation': {'right_minus_left': delta},
                           'candidate_deltas': signatures, 'excluded': excluded,
                           'new_prompt': new_prompt, 'edited_spans': spans,
                           'new_args': new_args})
    assert candidates
    chosen = min(candidates, key=lambda c: (-len(c['excluded']), len(c['edited_spans']), c['bag_ids']))
    assert chosen['excluded'] == ['add_both', 'independent_marginals']
    delta = chosen['allowed_output_relation']['right_minus_left']
    # Shared unknown additive contribution B cancels. Here use a finite sample
    # solely to exhibit correlation; the algebraic difference holds for all B.
    a = surcharge(module, args['bag_list'], 'joint_max')
    b = surcharge(module, chosen['new_args']['bag_list'], 'joint_max')
    bases = [1000, 1000+abs(delta)]
    coupled = {(base+a, base+b) for base in bases}
    cartesian = set(itertools.product({x for x,_ in coupled}, {y for _,y in coupled}))
    assert all(y-x == delta for x,y in coupled)
    assert any(y-x != delta for x,y in cartesian)
    # Hold-out check within this TRAIN design fixture, never used to synthesize Q.
    total0, _ = module.compute_answer(**args, check_base_tables=module.check_base_tables)
    total1, _ = module.compute_answer(**chosen['new_args'], check_base_tables=module.check_base_tables)
    assert int(total1)-int(total0) == delta
    selected = {k:v for k,v in chosen.items() if k != 'new_args'}
    return {'status': 'native_rule_partial_oracle_design_check', 'model_calls': 0,
            'source_key': fixture['source_key'], 'source_prompt_sha256': fixture['prompt_sha256'],
            'generated_prompt_sha256': hashlib.sha256(chosen['new_prompt'].encode()).hexdigest(),
            'source_case_count': 1, 'eligible_source_edits': len(candidates),
            'setting': 'controlled_missing_intermediate_annotation_not_missing_source_text',
            'constructor_uses_native_total_labels': False,
            'constructor_uses_reviewed_local_rule_functions': True,
            'selected': selected, 'coupled_signature_examples': sorted(coupled),
            'independent_completion_adds_invalid_signatures': len(cartesian)-len(coupled),
            'native_total_after_construction': [int(total0), int(total1)],
            'native_delta_check': True, 'real_model_gain_measured': False,
            'partial_oracle_pass_is_global_correctness': False}


if __name__ == '__main__':
    result = run()
    (OUT/'airline_partial_relation_results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
