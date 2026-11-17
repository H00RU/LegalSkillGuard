"""Preserve annotation diagnostics and a lossless source-anchor projection.

Literal quotes are already verified against the source. Replacing a display
name with that quote does not certify concepts, relations, completeness, or
legal meaning. Original names and all unresolved issues remain in the receipt.
"""
from copy import deepcopy
import json
from pathlib import Path

from legal_skill_guard.paired_interfaces import graph_interface as gi
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/two_method_followthrough_20261116/annotation_v1'


def project(graph, units):
    projected = deepcopy(graph)
    display_names = {}
    for node in projected['nodes']:
        display_names[node['id']] = node['name']
        node['name'] = node['quote']
    checks = gi.validate(projected, units)
    return projected, {'original_display_names': display_names,
        'literal_name_changed_ids': [n['id'] for n in graph['nodes'] if n['name'] != n['quote']],
        'semantic_nodes_and_relations_unchanged': True,
        'span_checks_after_literal_quote_projection': checks,
        'projection_is_not_semantic_reference_certification': True}


def main():
    rows = []
    for check_path in sorted((BASE / 'proposed_references').glob('*/source_checks.json')):
        check = json.loads(check_path.read_text())
        task = json.loads(check_path.with_name('task.json').read_text())
        result_path = BASE / 'calls' / digest(check['physical_call_id']) / 'result.json'
        result = json.loads(result_path.read_text())
        units = {v['view_id']: v['source_units'] for v in task['task']['views']}
        views, errors = [], []
        for view in result['value']['views']:
            try:
                graph, receipt = project(view['graph'], units[view['view_id']])
                views.append({'view_id': view['view_id'], 'graph': graph, 'projection_receipt': receipt})
            except (ValueError, KeyError) as error:
                errors.append(str(error))
        audit = {'source': check['source'], 'role': check['role'], 'views': views,
            'errors': errors, 'physical_call_id': check['physical_call_id'],
            'reference_ready': False, 'source_semantic_truth_verified': False,
            'native_labels_used': False, 'new_model_calls': 0,
            'required_next_audit': 'source meaning, scope and consumer support; do not clear unresolved to obtain a score'}
        immutable_json(check_path.with_name('anchor_projection.json'), audit)
        rows.append({'source': check['source'], 'views': len(views), 'errors': errors,
                     'reference_ready': False})
    print(json.dumps(rows, ensure_ascii=False))


if __name__ == '__main__':
    main()
