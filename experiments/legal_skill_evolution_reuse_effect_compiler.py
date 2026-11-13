"""Reuse the actual acquired compiler; parameterize its effect actor inputs.

No old result is repaired or overwritten. A new program consumes preserved
real neural actor observations. Other acquired semantics stay byte-for-byte
equivalent in AST; the source is then executed and scored again offline.
"""
import ast
from pathlib import Path

from experiments.legal_skill_evolution_effect_slots_preflight import OUT
from experiments.legal_skill_evolution_refutation_learning import ROOT, read, sha
from experiments.legal_skill_evolution_residual_calibration import source_record
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.effect_actor_binding import bind
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.native import source_spans
from legal_skill_guard.skill_evolution.scoped_grammar import material_public
from legal_skill_guard.skill_evolution.source_python import execute, merge_functions, validate
from legal_skill_guard.skill_evolution.span_compiler import execution_source_units

DEST = OUT/'reused_compiler'


def revise(program):
    functions = {n.name: n for n in ast.parse(program).body}
    entry = ast.get_source_segment(program, functions['apply'])
    parser = ast.get_source_segment(program, functions['parse_disposal'])
    old_call = "parse_disposal(raw,[s.get('id')],statements)"
    # Use AST formatting so whitespace in preserved teacher programs is immaterial.
    entry = ast.unparse(ast.parse(entry).body[0])
    parser = ast.unparse(ast.parse(parser).body[0])
    old_call = "parse_disposal(raw, [s.get('id')], statements)"
    if entry.count(old_call) != 1 or entry.count('unresolved = []') != 1:
        raise ValueError('Unexpected actual compiler entry structure')
    entry = entry.replace("    spans = inputs.get('source_spans', [])",
                          "    spans = inputs.get('source_spans', [])\n    unresolved = []")
    entry = entry.replace(old_call,
        "parse_disposal(raw, [s.get('id')], statements, inputs.get('effect_actor_bindings', {}).get('source_'+str(s.get('id'))+'_', {}), unresolved)")
    # Retain the new early unresolved list rather than resetting actor failures.
    reset = entry.rfind('    unresolved = []\n')
    entry = entry[:reset] + entry[reset:].replace('    unresolved = []\n', '', 1)
    assignment = "    actor = ['named_recipient', 'Volunteer'] if 'volunteer' in t else ['receiving_party']"
    if parser.count(assignment) != 1:
        raise ValueError('Actual old inferred actor assignment changed')
    parser = parser.replace('def parse_disposal(raw, ids, out):',
                            'def parse_disposal(raw, ids, out, actors, unresolved):')
    parser = parser.replace(assignment,
        "    disposal_actor = actors.get('disposal_obligation')\n"
        "    permission_actor = actors.get('retention_permission')\n"
        "    prohibition_actor = actors.get('retention_prohibition')")
    parser = parser.replace(
        "        add_statement(out, ['retention_permission', actor, retention_information(t), ['after_disposal'], cond], ids)",
        "        if permission_actor is None:\n"
        "            unresolved.append('Missing current-source retention permission actor for '+str(ids))\n"
        "        else:\n"
        "            add_statement(out, ['retention_permission', permission_actor, retention_information(t), ['after_disposal'], cond], ids)")
    parser = parser.replace(
        "        add_statement(out, ['retention_prohibition', actor, retention_information(t), ['after_disposal']], ids)",
        "        if prohibition_actor is None:\n"
        "            unresolved.append('Missing current-source retention prohibition actor for '+str(ids))\n"
        "        else:\n"
        "            add_statement(out, ['retention_prohibition', prohibition_actor, retention_information(t), ['after_disposal']], ids)")
    parser = parser.replace("    es = []", "    if disposal_actor is None or (explicit_retention and permission_actor is None):\n"
        "        unresolved.append('Missing current-source actor needed for disposal and its exception for '+str(ids))\n"
        "        return\n    es = []")
    parser = parser.replace("['retention_exception', actor, retention_information(t), cond]",
                            "['retention_exception', permission_actor, retention_information(t), cond]")
    parser = parser.replace("['disposal_obligation', actor, action, trigger, exceptions]",
                            "['disposal_obligation', disposal_actor, action, trigger, exceptions]")
    new = merge_functions(program, [entry, parser])
    # Only the two actual functions above change; all other learned logic is reused.
    old_tree = {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(program).body}
    new_tree = {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(new).body}
    assert set(old_tree) == set(new_tree)
    assert all(new_tree[k] == v for k, v in old_tree.items() if k not in ('apply', 'parse_disposal'))
    assert not any(isinstance(n, ast.Name) and n.id == 'actor'
                   for n in ast.walk(ast.parse(parser)))
    validate(new)
    return new


def run():
    old_path = ROOT/'artifacts/legal_skill_evolution_open_effect_acquisition_20261113/SourceEffect/compiled.json'
    old = read(old_path)
    source_id = read(OUT/'protocol.json')['source']
    source = next(s for s in read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')
                  if s['key'] == source_id)
    pub = source['views'][0]['public']
    units, _ = execution_source_units(pub['source_text'], source_spans(material_public(pub)))
    original = execute(old['source_program'], {'source_text': pub['source_text'], 'source_spans': units})
    history = ROOT/'artifacts/legal_skill_evolution_open_effect_acquisition_20261113/development/SourceEffect'/(source_id.replace(':', '_')+'.json')
    assert original == read(history)['interpretation']['source_program_output']
    model = ROOT/'artifacts/legal_skill_evolution_refutation_learning_20261113/direct_actor_diagnostic/result.json'
    actual = read(model)['value']
    queries = [{'id': 'source_58_role', 'unit_ids': [58]}]
    observations = [
        {'query_id': 'source_58_role', 'effect': 'disposal_obligation', 'unit_id': 58,
         'phrase': actual['return_actor_phrase']},
        {'query_id': 'source_58_role', 'effect': 'retention_permission', 'unit_id': 58,
         'phrase': actual['maintain_copy_actor_phrase']}]
    bindings = bind(old['grammar'], queries, units, observations)
    program = revise(old['source_program'])
    output = execute(program, {'source_text': pub['source_text'], 'source_spans': units,
                               'effect_actor_bindings': bindings})
    empty = execute(program, {'source_text': pub['source_text'], 'source_spans': units,
                              'effect_actor_bindings': {}})
    effects = {'disposal_obligation', 'retention_permission', 'retention_prohibition'}
    assert not any(s['term'][0] in effects for s in empty['statements'])
    assert not empty['complete']
    bundle = {'spec': old['grammar'], 'program': program}
    record = source_record(bundle, source, {'source_output': output,
        'actual_preserved_neural_actor_observation_sha256': sha(model),
        'new_neural_requests': 0, 'old_compiler_reexecuted_not_fresh_end_to_end_generation': True})
    immutable_json(DEST/'bundle.json', bundle)
    immutable_json(DEST/'result.json', record)
    immutable_json(DEST/'receipt.json', {
        'source': source_id, 'new_model_requests': 0, 'old_bundle_sha256': sha(old_path),
        'old_source_output_exactly_reproduced': True, 'old_historical_result_sha256': sha(history),
        'neural_actor_result_sha256': sha(model), 'observations': observations, 'bindings': bindings,
        'missing_bindings_output': empty, 'old_response_not_rewritten': True,
        'only_apply_and_parse_disposal_AST_changed': True,
        'quantity_purpose_trigger_action_and_exception_logic_reused': True,
        'new_program_output_not_semantics_preserving_adaptation_of_wrong_old_actor': True,
        'source_scope_review_still_required': True, 'not_learning_contribution': True,
        'goal_complete': False,
        'implementation_sha256': sha(Path(__file__))})
    print({'core': sum(v['core_executed'] for v in record['views']),
           'native_correct': sum(bool(v['score'] and v['score']['correct']) for v in record['views']),
           'new_model_requests': 0, 'source_output': output})


if __name__ == '__main__':
    run()
