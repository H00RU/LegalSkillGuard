"""Test actual saved TRAIN A requests for loss of dedicated question context.

No model, tokenizer, oracle, grading packet or production file is modified.
The candidate is evaluated in a separate module while the live seal stays frozen.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys
import types

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from legal_skill_guard.rr import pal_refinement
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.source_program import compile_source, observation_request

RUN = 'method_runtime_reference_v8_20261109'
stage = ROOT / 'artifacts/rr_method_runtime_20261107' / RUN
seal = json.loads((stage / 'seal.json').read_text())
public = {s['key']: s for s in json.loads((ROOT / 'data/packets/rr_v2/public_train.json').read_text())['sources']}
library = json.loads((stage / 'build/B1.frozen.json').read_text())['content']
original = (ROOT / 'reports/rr_method_runtime_20261107/reference_v25_before_pal_refinement.py').read_text()
old_module = types.ModuleType('legal_skill_guard.rr._pal_refinement_v24_saved')
exec(compile(original, '<preserved v24 source>', 'exec'), old_module.__dict__)
needle = "    units=set(closure)|{c.id for c in structure.ledger.clauses if structure.roles[c.id]['role']=='fact'}\n"
assert original.count(needle) == 1
replacement = needle + ("    # A pure legal patch still needs the original question's temporal/entity context.\n"
    "    # Charge its source unit; it remains read-only and cannot replace the query.\n"
    "    if not names and compiled['source']['public'].get('query'):\n"
    "        units|={c.id for c in structure.ledger.clauses if structure.roles[c.id]['role']=='query'}\n")
candidate_source = original.replace(needle, replacement)
candidate = types.ModuleType('legal_skill_guard.rr._pal_refinement_v25_offline')
exec(compile(candidate_source, '<offline candidate>', 'exec'), candidate.__dict__)
rows = []
target = None
for index, sid in enumerate(seal['sources']['train'], 1):
    key = digest(sid)
    journal = stage / 'build/journals' / key
    request_path = journal / 'request1.json'
    state_path = journal / 'state0.json'
    if not request_path.exists() or not state_path.exists():
        continue
    request = json.loads(request_path.read_text())
    prepared = request['prepared'] or {}
    if prepared.get('program_format') != 'pal_fragment_lines_v1':
        continue
    state = json.loads(json.loads(state_path.read_text())['state_json'])
    compiled = compile_source(public[sid], state['program'], library=library)
    names = prepared['names']
    facts, schema = observation_request(compiled, names)
    args = (prepared['selected'], prepared['context_closure'], names,
        json.loads(facts[1]['content']), schema['properties']['observations'], library)
    old = old_module.refinement_request(compiled, *args)
    new = candidate.refinement_request(compiled, *args)
    # Saved state is key-sorted, so reconstructed JSON object member order can
    # differ. Check the actual payload values and system text; do not claim
    # literal wire identity from reconstruction of a key-sorted state.
    assert old[0][0] == prepared['messages'][0]
    assert json.loads(old[0][1]['content']) == json.loads(prepared['messages'][1]['content']), index
    assert old[1] == prepared['schema'] == new[1]
    a = json.loads(old[0][1]['content'])
    b = json.loads(new[0][1]['content'])
    query_ids = {c.id for c in compiled['structure'].ledger.clauses
        if compiled['structure'].roles[c.id]['role'] == 'query'}
    added = set(new[2]) - set(old[2])
    expected_change = not names and bool(public[sid]['public'].get('query'))
    if expected_change:
        assert added == query_ids - set(old[2])
        before = deepcopy(a)
        after = deepcopy(b)
        before.pop('charged_context_units'); after.pop('charged_context_units')
        before['CURRENT_units'] = [v for v in before['CURRENT_units'] if v['role'] != 'query']
        after['CURRENT_units'] = [v for v in after['CURRENT_units'] if v['role'] != 'query']
        assert before == after
    else:
        assert old == new
    row = {'train_ordinal': index, 'source': sid, 'fact_tasks': len(names),
        'actual_saved_payload_values_and_system_exactly_reconstructed': True,
        'key_sorted_state_reconstruction_is_not_literal_wire_replay': True,
        'response_schema_unchanged': True, 'added_charged_query_units': sorted(added),
        'old_messages_sha256': digest(old[0]), 'candidate_messages_sha256': digest(new[0]),
        'all_nonquery_payload_fields_unchanged': True}
    rows.append(row)
    if index == 73:
        variant = deepcopy(public[sid])
        original_query = variant['public']['query']
        years = re.findall(r'\b20\d{2}\b', original_query)
        assert len(set(years)) == 1
        alternate_year = '2020' if years[0] != '2020' else '2021'
        variant['public']['query'] = original_query.replace(years[0], alternate_year)
        other = compile_source(variant, state['program'], library=library)
        old_other = old_module.refinement_request(other, *args)
        new_other = candidate.refinement_request(other, *args)
        assert old[0] == old_other[0]
        assert new[0] != new_other[0]
        target = {**row, 'original_public_query': original_query,
            'offline_only_alternate_query': variant['public']['query'],
            'old_request_cannot_distinguish_question_year': True,
            'candidate_preserves_original_question_verbatim_and_distinguishes_year': True,
            'synthetic_variant_is_regression_only_not_new_research_source': True,
            'missing_rule_semantics_not_filled': True,
            'real_model_validation_still_required': True}
assert target is not None
candidate_path = Path('/tmp/lsg_pal_refinement_v25_candidate.py')
candidate_path.write_text(candidate_source)
result = {'run_id': RUN, 'actual_saved_pal_followups_audited': len(rows),
    'changed_pure_legal_followups': sum(bool(r['added_charged_query_units']) for r in rows),
    'unchanged_other_followups': sum(not r['added_charged_query_units'] for r in rows),
    'target': target, 'source_rows': rows,
    'candidate_source_sha256': hashlib.sha256(candidate_source.encode()).hexdigest(),
    'production_scientific_files_changed': False, 'new_model_or_oracle_calls': 0,
    'grading_or_TEST_read': False, 'provides_missing_read_only_input_not_missing_rules': True}
output = ROOT / 'reports/rr_method_runtime_20261107/reference_legal_only_query_context_loss_v25_offline.json'
output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({k:v for k,v in result.items() if k not in {'source_rows','target'}}, ensure_ascii=False))
print(json.dumps(target, ensure_ascii=False))
