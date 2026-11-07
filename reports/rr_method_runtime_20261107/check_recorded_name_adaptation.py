"""Test reversible alpha-renaming on actual complete outputs, without repair of meaning."""
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.learning import SkillLibrary
from legal_skill_guard.rr.preflight import science_files
from legal_skill_guard.rr.source_code import decode_compiler_response
from legal_skill_guard.rr.source_inference import _decode
from legal_skill_guard.rr.source_program import compile_source
from legal_skill_guard.rr.source_execution import assess_source


def rename(program, names):
    result = deepcopy(program)
    def expression(value):
        if isinstance(value, dict):
            if set(value) == {'var'}:
                return {'var': names.get(value['var'], value['var'])}
            return {key: expression(item) for key, item in value.items()}
        if isinstance(value, list):
            return [expression(item) for item in value]
        return value
    def graph(value):
        value = deepcopy(value)
        if 'slot' in value:
            value['slot'] = names.get(value['slot'], value['slot'])
        elif 'pattern' in value:
            if isinstance(value['slots'], dict):
                value['slots'] = {key: names.get(item, item) if isinstance(item, str) else item
                                  for key, item in value['slots'].items()}
        else:
            value['inputs'] = [graph(item) for item in value['inputs']]
            if isinstance(value.get('params'), dict):
                value['params'] = {key: names.get(item, item) if key.endswith('_slot') and isinstance(item, str) else item
                                  for key, item in value['params'].items()}
        return value
    for row in result['observations'] + result['rule_residuals']:
        row['name'] = names.get(row['name'], row['name'])
    for binding in result['bindings']:
        if binding['type'] == 'slot_list' and isinstance(binding['value'], list):
            binding['value'] = [names.get(item, item) if isinstance(item, str) else item for item in binding['value']]
    for node in result['nodes']:
        if node['kind'] == 'expression':
            node['body'] = expression(node['body'])
        else:
            node['body']['graph'] = graph(node['body']['graph'])
    for scope in result['scopes']:
        scope['condition'] = expression(scope['condition'])
    for clause in result['clauses']:
        for key in ('value', 'otherwise'):
            clause[key] = expression(clause[key])
    result['query'] = expression(result['query'])
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    stage = root / 'artifacts/rr_method_runtime_20261107' / args.run_id
    seal = json.loads((stage / 'seal.json').read_text())
    assert science_files(root) == seal['files']
    packet = json.loads((root / 'data/packets/rr_v2/public_train.json').read_text())
    assert packet['split'] == 'train' and not packet['contains_gold_or_reference_program']
    sources = {source['key']: source for source in packet['sources']}
    library, rows, source_count = SkillLibrary(stage='formal_train'), [], 0
    for source in seal['sources']['train']:
        path = stage / 'build/sources' / (digest(source) + '.json')
        if not path.exists():
            break
        record = json.loads(path.read_text()); source_count += 1
        assert record['library_before_hash'] == digest(library.export())
        for call in record['prediction']['calls']:
            raw = call.get('raw_content')
            row = {'source': source, 'step': call['step'],
                   'raw_sha256': hashlib.sha256(raw.encode()).hexdigest() if raw else None}
            try:
                program = decode_compiler_response(_decode(raw))
            except Exception as exc:
                row.update(status='no_complete_declarative_IR', error_type=type(exc).__name__)
                rows.append(row); continue
            symbols = [item['name'] for field in ('bindings','observations','rule_residuals','nodes','scopes','clauses')
                       for item in program[field]]
            if len(symbols) != len(set(symbols)):
                row.update(status='ambiguous_duplicate_symbols_no_adaptation')
                rows.append(row); continue
            occupied = set(symbols); names = {}
            for item in program['observations'] + program['rule_residuals']:
                if re.fullmatch(r'b_[A-Za-z0-9_]{1,62}', item['name']):
                    continue
                index = len(names)
                while 'b__alpha_' + str(index) in occupied:
                    index += 1
                target = 'b__alpha_' + str(index)
                names[item['name']] = target; occupied.add(target)
            adapted = rename(program, names)
            assert rename(adapted, {value: key for key, value in names.items()}) == program
            row.update(renaming=names, reversible=True, source_quotes_and_literal_values_unchanged=True)
            try:
                compiled = compile_source(sources[source], adapted, library=library.export())
                row.update(status='compiled_after_names_only' if names else 'already_compiles_without_adaptation')
                try:
                    assessment = assess_source(compiled)
                    row.update(assessment_status=assessment['status'], conditional_certificate=bool(assessment['certificate']))
                except Exception as exc:
                    row.update(status='compiled_but_execution_or_native_assessment_invalid',
                               assessment_error_type=type(exc).__name__, assessment_error=str(exc)[:1800])
            except Exception as exc:
                row.update(status='still_invalid_after_names_only', error_type=type(exc).__name__,
                           error=getattr(exc, 'message', str(exc))[:1800],
                           field_path=list(exc.path) if hasattr(exc, 'path') else None)
            rows.append(row)
        if record['learning'].get('learned_pattern'):
            library.add(record['learning']['learned_pattern'], source=source)
    result = {'checked_utc': datetime.now(timezone.utc).isoformat(), 'run_id': args.run_id,
        'prefix_sources_checked': source_count, 'rows': rows, 'statuses': dict(Counter(row['status'] for row in rows)),
        'live_records_or_scientific_source_modified': False, 'adapter_installed_in_production': False,
        'rules_facts_or_missing_operands_invented': False, 'grading_packets_opened': False,
        'new_model_or_oracle_calls': 0, 'interpretation': 'Diagnostic alpha-renaming only. No truncated output was completed, no semantic fault repaired, no result accepted as core success.'}
    Path(__file__).with_name(args.run_id + '_name_adaptation_check.json').write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'prefix_sources_checked': source_count, 'statuses': result['statuses'], 'new_model_or_oracle_calls': 0}))


if __name__ == '__main__':
    main()
