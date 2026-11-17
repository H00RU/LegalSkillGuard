"""Build a local M1 module from a preserved learned Airline consumer.

This is offline production integration, not the locked real-model pilot. The
original grader is never registered as a prediction tool. All consequences
come from the exact preserved teacher-acquired skill and its quoted premises.
"""
from __future__ import annotations

from copy import deepcopy
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from legal_skill_guard.paired_interfaces.residual import FiniteModule, propose, canonical
from legal_skill_guard.skill_evolution.span_compiler import validate_procedure
from legal_skill_guard.skill_evolution.objects import digest

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/two_method_followthrough_20261116/offline_airline_module'
LIBRARY = ROOT / 'artifacts/legal_skill_evolution_20261111/formal_v5/Full/B8.json'


def array_factorization_certificate(procedure, groups):
    tree = ast.parse(procedure)
    parents = {id(child): node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    limit_assignments = [node for node in ast.walk(tree) if isinstance(node, ast.Assign)
                         and any(isinstance(t, ast.Name) and t.id == 'standard_weight_limit' for t in node.targets)]
    if any(not isinstance(node.value, ast.Constant) for node in limit_assignments):
        raise ValueError('Weight limits have an unverified dynamic assignment')
    limits = {node.value.value for node in limit_assignments}
    if limits != {50, 70}:
        raise ValueError('The frozen consumer has a different weight-limit domain')
    thresholds, comparisons = set(), []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == 'weight' and isinstance(node.ctx, ast.Load):
            parent = parents[id(node)]
            if (not isinstance(parent, ast.Compare) or parent.left is not node or len(parent.ops) != 1
                    or not isinstance(parent.ops[0], (ast.Gt, ast.LtE))):
                raise ValueError('Weight has a non-comparison consumer use')
            for other in [parent.left, *parent.comparators]:
                if other is node:
                    continue
                if isinstance(other, ast.Constant) and isinstance(other.value, (int, float)):
                    thresholds.add(other.value)
                    comparisons.append((type(parent.ops[0]).__name__, other.value))
                elif isinstance(other, ast.Name) and other.id == 'standard_weight_limit':
                    thresholds.update(limits)
                    comparisons.extend((type(parent.ops[0]).__name__, v) for v in sorted(limits))
                else:
                    raise ValueError('Unbounded weight-comparison context')
    port_reads = [node for node in ast.walk(tree) if isinstance(node, ast.Subscript)
                  and isinstance(node.value, ast.Name) and node.value.id == 'inputs'
                  and isinstance(node.slice, ast.Constant) and node.slice.value == 'item_weights']
    if len(port_reads) != 1:
        raise ValueError('Weight port has another use outside the verified loop')
    item = parents[id(port_reads[0])]
    call = parents[id(item)]
    assignment = parents[id(call)]
    if (not isinstance(item, ast.Subscript) or not isinstance(call, ast.Call)
            or not isinstance(call.func, ast.Name) or call.func.id != 'float'
            or not isinstance(assignment, ast.Assign)
            or not any(isinstance(t, ast.Name) and t.id == 'weight' for t in assignment.targets)):
        raise ValueError('The weight-port dataflow is not the audited scalar comparison path')
    if sum(isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'weight' for t in node.targets)
           for node in ast.walk(tree)) != 1:
        raise ValueError('Weight has another assignment outside the verified input projection')
    for group in groups:
        actual = {tuple(w > t if op == 'Gt' else w <= t for op, t in comparisons) for w in group['members']}
        if len(actual) != 1:
            raise ValueError('The residual grouping changes a live scalar comparison')
    return {'kind': 'syntactic_weight_port_factorization', 'thresholds': sorted(thresholds),
            'domain': 'each weight is an integer 0..100', 'all_weight_loads_checked': True,
            'arbitrary_finite_bag_array_length': True,
            'all_other_inputs_and_premises_unchanged': True,
            'paired_representatives_preserve_each_live_comparison': True}


def build():
    library = json.loads(LIBRARY.read_text())
    skills = library['skills']
    if isinstance(skills, dict):
        skills = skills.values()
    skill = next(s for s in skills if s['id'] == 'domestic_main_or_first_bag_total')
    procedure = skill['procedure']
    validate_procedure(procedure)
    train = json.loads((ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json').read_text())
    public = {s['key']: s for s in train}
    anchors = []
    for name, premise in skill['premises'].items():
        if premise['mode'] != 'constant':
            raise ValueError('A nonconstant premise needs actual source reading before evaluation')
        origin = premise['origin']
        view = next(v for v in public[origin['source_id']]['views'] if v['id'] == origin['view_id'])
        text = view['public']['source_text']
        quote = origin['quote']
        # Whitespace folding is recorded explicitly; it does not add a value
        # absent from the frozen TRAIN source.
        exact = quote in text
        folded = ' '.join(quote.split()) in ' '.join(text.split())
        if not folded:
            raise ValueError('Preserved consumer premise lacks its original source anchor: ' + name)
        anchors.append({'premise': name, 'source': origin['source_id'], 'view': origin['view_id'],
                        'quote': quote, 'exact_span': exact, 'whitespace_folded_match': folded})
    premises = {name: p['value'] for name, p in skill['premises'].items()}
    contexts = [{'cabin': cabin, 'region': region, 'geometry': geometry}
                for cabin in ('Main Cabin', 'Business', 'First', 'Premium Economy')
                for region in ('domestic_us', 'south_america_other', 'east_asia')
                for geometry in ('ordinary', 'small_oversize', 'large_oversize')]
    calls, identities = [], []
    for weight in range(101):
        for context in contexts:
            lengths = {'ordinary': 25, 'small_oversize': 32, 'large_oversize': 40}
            inputs = {'ticket_price': 100, 'cabin_class': context['cabin'],
                      'route_fee_region': context['region'],
                      'item_lengths': [10, lengths[context['geometry']]],
                      'item_widths': [10, 20], 'item_heights': [5, 12], 'item_weights': [10, weight]}
            calls.append({'inputs': inputs})
            identities.append((weight, canonical(context)))
    worker = ROOT / 'legal_skill_guard/paired_interfaces/consumer_worker.py'
    result = subprocess.run([sys.executable, '-I', '-S', str(worker)],
        input=json.dumps({'procedure': procedure, 'premises': premises, 'calls': calls}),
        capture_output=True, text=True, timeout=30, cwd='/tmp', env={'LANG': 'C.UTF-8'})
    if result.returncode:
        raise ValueError('Frozen consumer table failed: ' + result.stderr[-1500:])
    values = json.loads(result.stdout)
    if len(values) != len(identities):
        raise ValueError('Frozen consumer returned an incomplete finite output table')
    outputs = dict(zip(identities, values))
    def consumer(local, context):
        # Full original totals vary over the remaining cabin/route/size
        # contexts. H sees one bag weight only, not these contexts or a label.
        return outputs[local['bag_weight_lbs'], canonical(context)]
    module = FiniteModule.build('preserved_airline_checked_weight', {'bag_weight_lbs': list(range(101))},
        contexts, consumer, consumer_sha256=hashlib.sha256(procedure.encode()).hexdigest(),
        source_scope={'source_fields': ['facts'], 'local_unit': 'one identified checked bag weight',
                      'field_meanings': {'bag_weight_lbs': 'the identified bag weight in pounds, as an integer'},
                      'reader_receives_question_or_expected_fee': False,
                      'finite_domain': 'integer pounds 0..100 only; other weights unsupported'},
        program_source='')
    candidates = propose(module)
    partition = next(f for f in candidates['candidates'][0]['features'] if f['operation'] == 'residual_bucket')
    array_certificate = array_factorization_certificate(procedure, partition['groups'])
    for candidate in candidates['candidates']:
        candidate['certificate']['array_factorization'] = array_certificate
        candidate['version'] = digest({k: v for k, v in candidate.items() if k != 'version'})
    return {'module_binding': module.binding, 'fixed_skill_id': skill['id'],
            'frozen_library_path': str(LIBRARY.relative_to(ROOT)),
            'frozen_library_sha256': hashlib.sha256(LIBRARY.read_bytes()).hexdigest(),
            'consumer_sha256': module.consumer_sha256, 'source_anchors': anchors,
            'finite_states': len(module.states), 'remaining_contexts': len(contexts),
            'candidates': candidates, 'new_model_calls': 0,
            'not_a_pilot_or_method_efficacy_result': True,
            'semantic_boundary': 'Preserves this learned consumer on declared domain; source-meaning audit and real model/native end-to-end pilot remain required.'}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    value = build()
    path = OUT / 'generated_interfaces.json'
    content = json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    if path.exists() and path.read_text() != content:
        archive = OUT / 'versions'
        archive.mkdir(exist_ok=True)
        (archive / (hashlib.sha256(path.read_bytes()).hexdigest() + '.json')).write_bytes(path.read_bytes())
    path.write_text(content)
    print(json.dumps({'finite_states': value['finite_states'], 'remaining_contexts': value['remaining_contexts'],
                      'operations': [c['operation'] for c in value['candidates']['candidates']],
                      'read_domains': [c['domains'] for c in value['candidates']['candidates']],
                      'new_model_calls': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()
