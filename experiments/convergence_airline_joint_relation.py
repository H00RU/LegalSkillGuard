"""Compile a nonlinear relation on the locked Airline TRAIN sources."""

import ast
import hashlib
import itertools
import json
from pathlib import Path
import re
from types import SimpleNamespace
from typing import Dict

import numpy as np

from experiments.convergence_pilot_b0 import BASE, HANDOFF, POINTER, ROOT, read
from legal_skill_guard.paired_interfaces.shared_semantics import (
    DerivedField, SourceCase, Theory, allowed_relation, source_variant,
)
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

LOCAL_RULES = ROOT / 'reports/legal_skill_convergence_20261117/prototypes/native_airline'
ROUTES = {('Austin', 'Denver'), ('Seattle', 'New York')}
BAG = re.compile(r'^(\d+)\. .+?: (\d+) x (\d+) x (\d+) inches, (\d+) lbs;$', re.M)


def native_surcharge_functions(path):
    # This projection has no check-in table lookup. Reuse the exact two
    # official local rules without importing the full scorer's table loader.
    definitions = {'compute_oversize', 'compute_overweight'}
    body = [node for node in ast.parse(path.read_text()).body
            if isinstance(node, ast.FunctionDef) and node.name in definitions]
    if {node.name for node in body} != definitions or len(body) != len(definitions):
        raise ValueError('The pinned official file no longer defines both local surcharge rules')
    namespace = {'np': np, 'Dict': Dict}
    exec(compile(ast.Module(body=body, type_ignores=[]), str(path), 'exec'), namespace)
    return SimpleNamespace(**{name: namespace[name] for name in definitions})


def reference(public, source_key, native, rule_binding):
    text = public['facts']
    flight = re.search(r'^.+? is an? (.+?) Class passenger flying from (.+?) to (.+?) with the following items:', text)
    if not flight or flight[1] != 'Main Plus' or tuple(flight.groups()[1:]) not in ROUTES:
        return None
    bags = list(BAG.finditer(text))
    if len(bags) != text.count(' lbs;') or [int(b[1]) for b in bags] != list(range(1, len(bags) + 1)):
        raise ValueError('Literal bag fields do not cover the complete stated inventory')
    spans = {f'bag_{b[1]}_weight': ('facts', *b.span(5)) for b in bags}
    dimensions = {f'bag_{b[1]}_weight': [int(b[i]) for i in (2, 3, 4)] for b in bags}
    values = {f'bag_{b[1]}_weight': int(b[5]) for b in bags}
    checked = tuple(list(values)[1:])
    scope = f'RuleArena:US:MainPlus:{rule_binding}'
    law = {'route': 'U.S.', 'cabin': 'Main Plus'}

    def fees(states, conditions):
        pairs = []
        for field in checked:
            bag = {'size': dimensions[field], 'weight': states[field]}
            over = native.compute_overweight(bag, conditions['route'], conditions['cabin'], False)
            if over != native.compute_overweight(bag, conditions['route'], conditions['cabin'], True):
                raise ValueError('This local relation needs invariant free-bag weight treatment')
            pairs.append((int(native.compute_oversize(bag, conditions['route'])), int(over)))
        return pairs

    def candidates(states):
        pairs = fees(states, law)
        oversize, overweight = map(sorted, zip(*pairs))
        return {'same_bag_max': sum(max(pair) for pair in pairs),
                'add_all_fees': sum(sum(pair) for pair in pairs),
                'sorted_unpaired_fees': sum(max(a, b) for a, b in zip(oversize, overweight))}

    theory = Theory({scope: [law]}, {source_key: [{}]},
                    lambda state, _: state['joint_surcharge'], rule_binding,
                    provenance=({'kind': 'official_task_assumption', 'evidence_sha256': rule_binding},
                                {'kind': 'explicit_source', 'evidence_sha256': digest(text)}),
                    derived=(DerivedField('joint_surcharge', checked,
                                          lambda state, _: candidates(state)['same_bag_max']),),
                    allowed_edits=frozenset(checked))
    source = SourceCase(source_key, source_key, scope, public, values, spans=spans)
    original = candidates(values)
    options = []
    for left, right in itertools.combinations(checked, 2):
        if values[left] == values[right]:
            continue
        changes = {left: values[right], right: values[left]}
        edited = source_variant(source, theory, changes, {field: str for field in changes})
        if edited['status'] != 'REALIZABLE':
            raise ValueError('An original weight did not bind its literal source span')
        parsed = {f'bag_{b[1]}_weight': int(b[5]) for b in BAG.finditer(edited['case'].public['facts'])}
        if parsed != {**values, **changes}:
            raise ValueError('The actual edit did not preserve all remaining bag weights')
        updated = candidates(parsed)
        delta = {name: updated[name] - original[name] for name in original}
        excluded = [name for name in delta if delta[name] != delta['same_bag_max']]
        if excluded:
            options.append((len(excluded), (left, right), edited, delta, excluded))
    if not options:
        return None
    _, _, edit, delta, excluded = min(options, key=lambda row: (-row[0], row[1]))
    signatures = list(allowed_relation(theory, [source, edit['case']])['signatures'].values())
    if len(signatures) != 1 or signatures[0][1] - signatures[0][0] != delta['same_bag_max']:
        raise ValueError('Compiled surcharge disagrees with the independently reparsed source edit')
    return {'source': source_key, 'source_edit': edit['receipt'], 'source_pair': [public, edit['case'].public],
            'nonlinear_native_rule_surcharge_pair': signatures[0], 'candidate_changes': delta,
            'excluded_symbolic_mutants': excluded, 'selected_entirely_from_source': True,
            'single_complete_local_rule_interpretation': True}


def run():
    pointer = read(POINTER)
    baseline = ROOT / pointer['artifact_root']
    if pointer['status'] != 'completed':
        raise ValueError('Keep the fixed TRAIN pilot locked before compiling quantity edits')
    native_file = LOCAL_RULES / 'compute_answer.py'
    native = native_surcharge_functions(native_file)
    files = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
             for path in [native_file, *sorted(LOCAL_RULES.glob('fee_tables/*/*.csv'))]}
    rule_binding = digest(files)
    rows = []
    originals = read(baseline / 'public_TRAIN_pilot.json')
    if digest(originals) != read(baseline / 'binding.json')['sources_digest']:
        raise ValueError('Frozen TRAIN pilot source binding changed')
    for source in originals:
        if source['dataset'] != 'RuleArena_Airline':
            continue
        result = reference(source['views'][0]['public'], source['key'], native, rule_binding)
        if result:
            rows.append(result)
    if not rows:
        raise ValueError('No source edit from the locked TRAIN cohort separates the nonlinear consumer')
    binding = {'official_local_rule_files': files, 'rule_sha256': rule_binding,
               'compiler_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               'fixed_pilot_source_sha256': digest(originals), 'new_generation_requests': 0,
               'native_labels_used': False, 'symbolic_mutants_not_actual_patch_gain': True}
    out = BASE / 'airline_joint_relation' / digest(binding)
    immutable_json(out / 'binding.json', binding)
    immutable_json(out / 'quantitative_source_edits.json', rows)
    receipt = {'artifact_root': str(out.relative_to(ROOT)), 'TRAIN_mothers_with_distinguishing_edits': len(rows),
               'nonlinear_certificate': [{'surcharge_pair': row['nonlinear_native_rule_surcharge_pair'],
                                          'candidate_changes': row['candidate_changes']} for row in rows],
               'new_generation_requests': 0, 'native_model_gain_measured': False}
    immutable_json(out / 'summary.json', receipt)
    (HANDOFF / 'airline_joint_relation_current.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    run()
