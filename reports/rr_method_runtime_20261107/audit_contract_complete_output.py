"""Replay the current build's second complete response without model or grading calls."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from unittest.mock import patch

from legal_skill_guard.rr.compiler_contract import decode_compiler_response
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.learning import SkillLibrary
from legal_skill_guard.rr.preflight import science_files
from legal_skill_guard.rr.scoped_program import expression_reads
from legal_skill_guard.rr.source_program import compile_source
from legal_skill_guard.rr.source_structure import inspect_source
from legal_skill_guard.rr.source_validation import validation_feedback
from legal_skill_guard.rr.wire_validation import validate_wire


def main():
    root = Path(__file__).resolve().parents[2]
    run_id = 'method_runtime_ast_v1_20261107'
    stage = root / 'artifacts/rr_method_runtime_20261107' / run_id
    seal = json.loads((stage / 'seal.json').read_text())
    assert science_files(root) == seal['files']
    source_key = seal['sources']['train'][9]
    assert source_key == 'ContractNLI:e671a984356facb0c0666809e219fa44fa18d30e4f6252bbb33d8869fc43b1c9'
    record_path = stage / 'build/sources' / (digest(source_key) + '.json')
    record = json.loads(record_path.read_text())
    manifest = json.loads((root / seal['source_manifest']).read_text())
    packet_path = root / 'data/packets/rr_v2/public_train.json'
    assert hashlib.sha256(packet_path.read_bytes()).hexdigest() == manifest['packet_sha256']['public_train']
    packet = json.loads(packet_path.read_text())
    assert packet['split'] == 'train' and not packet['contains_gold_or_reference_program']
    source = next(row for row in packet['sources'] if row['key'] == source_key)
    library = SkillLibrary(stage='formal_train')
    for key in seal['sources']['train'][:9]:
        earlier = json.loads((stage / 'build/sources' / (digest(key) + '.json')).read_text())
        learned = earlier['learning'].get('learned_pattern')
        if learned:
            library.add(learned, source=key)
    assert digest(library.export()) == record['library_before_hash']
    call_id = run_id + ':build:' + digest(source_key) + ':0'
    with sqlite3.connect('file:' + str(root / seal['ledger_path']) + '?mode=ro', uri=True) as db:
        status, encoded = db.execute('select status,result from calls where id=?', (call_id,)).fetchone()
    result = json.loads(encoded)
    assert status == 'completed' and result['finish_reason'] == 'stop'
    content = result['content']
    assert record['prediction']['calls'][0]['raw_content'] == content
    request_path = stage / 'build/journals' / digest(source_key) / 'request0.json'
    dispatch = json.loads(json.loads(request_path.read_text())['dispatch_json'])
    candidate = json.loads(content)
    with patch('socket.create_connection', side_effect=AssertionError('Offline audit forbids networking')), \
            patch('subprocess.Popen', side_effect=AssertionError('Offline audit forbids subprocesses')):
        validate_wire(candidate, dispatch['schema'])
        program = decode_compiler_response(candidate, source, library.export())
        feedback = validation_feedback(source, program)
        try:
            compile_source(source, program, library=library.export())
        except Exception as error:
            rejection = {'type': type(error).__name__, 'message': str(error)}
        else:
            raise AssertionError('Previously rejected candidate unexpectedly compiled')
    assert rejection == record['prediction']['calls'][0]['analysis']['error']
    groups = ('bindings', 'observations', 'rule_residuals', 'nodes', 'scopes', 'clauses')
    declared = {row['name'] for group in groups for row in program[group]}
    query_reads = expression_reads(program['query'])
    unbound = sorted(query_reads - declared)
    assert not program['clauses'] and query_reads == {'s19'} and not unbound
    type_errors = [row for row in feedback['issues']
                   if row['expected'] == 'boolean' and row['actual'] == ['string']]
    assert type_errors
    system = dispatch['messages'][0]['content']
    assert 'The final query combines guarded clause outputs and public inputs' in system
    assert 'a string is a literal, not a variable or a request to read a source unit' in system
    structure = inspect_source(source)
    receipt = {
        'checked_utc': datetime.now(timezone.utc).isoformat(), 'run_id': run_id,
        'source': source_key, 'physical_call_id': call_id,
        'source_record_sha256': hashlib.sha256(record_path.read_bytes()).hexdigest(),
        'raw_response_sha256': hashlib.sha256(content.encode()).hexdigest(),
        'request_journal_sha256': hashlib.sha256(request_path.read_bytes()).hexdigest(),
        'wire_schema_acceptance_replayed': True, 'canonical_decoder_acceptance_replayed': True,
        'compiler_rejection_replayed': rejection, 'finish_reason': result['finish_reason'],
        'usage': result['usage'], 'elapsed_seconds': result['elapsed_seconds'],
        'declarations': {group: len(program[group]) for group in groups},
        'query_reads': sorted(query_reads), 'undeclared_query_symbols': unbound,
        'query_binding_types': {row['name']: row['type'] for row in program['bindings']
                                if row['name'] in query_reads},
        'query_binding_values': {row['name']: row['value'] for row in program['bindings']
                                 if row['name'] in query_reads},
        'referenced_public_unit_roles': {name: structure.roles.get(name) for name in query_reads},
        'independent_type_diagnostics': type_errors,
        'source_only_feedback': feedback,
        'prompt_explicitly_requires_declared_symbols_and_guarded_outputs': True,
        'primary_failure_class': 'model_output_error',
        'reason': 'The model copies all20 public paragraphs into string bindings and emits no guarded clauses. Its nested query consumes the declared string s19 (the public hypothesis) as a Boolean. Complete JSON does not translate the source reasoning.',
        'semantic_preserving_format_adapter_available': False,
        'adapter_reason': 'The existing response needs no formatting recovery. Adding a legal clause or the missing symbol meaning would introduce absent semantics.',
        'candidate_modified': False, 'grading_packets_opened': False,
        'new_model_or_oracle_calls': 0, 'bound_science_unchanged': science_files(root) == seal['files'],
        'this_is_rejection_evidence_not_core_success': True,
    }
    output = Path(__file__).with_name(run_id + '_ContractNLI_complete_output_audit.json')
    output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({key: receipt[key] for key in ('source', 'declarations', 'undeclared_query_symbols',
        'compiler_rejection_replayed', 'primary_failure_class', 'new_model_or_oracle_calls')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
