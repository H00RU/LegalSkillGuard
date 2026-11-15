"""Repair a learned source parser's demonstrated possessive-scope bug.

The actual raw parser added own-party personnel to an affiliate-only phrase;
the preserved neural fragment was correct. No source ID, native label, new law
or extra read is used. Preserve every other learned function and raw response.
"""
import ast
from copy import deepcopy
import json

from experiments import legal_skill_evolution_source_operator_alignment as alignment
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.source_effect_update import function_update
from legal_skill_guard.skill_evolution.span_compiler import execute_json

current = alignment.current
OUT = current.ROOT / 'artifacts/legal_skill_evolution_C_owner_scope_repair_20261115'


def repaired_program(program):
    tree = ast.parse(program)
    found = [n for n in tree.body if n.name == 'legal_roles']
    assert len(found) == 1
    function = ast.get_source_segment(program, found[0])
    old = '''    actor_only ='''
    inserted = '''    scoped_personnel = []
    remainders = []
    last = 0
    pattern = r"\b(?:affiliates?|subsidiar(?:y|ies))['’]\\s+((?:officers?|directors?|employees?)(?:(?:\\s*,\\s*(?:(?:and|or)\\s+)?|\\s+(?:and|or)\\s+)(?:officers?|directors?|employees?))*)"
    for match in re.finditer(pattern, role_text):
        scoped_personnel.append(match.group(1))
        remainders.append(role_text[last:match.start(1)])
        last = match.end(1)
    remainders.append(role_text[last:])
    remainder = ' '.join(remainders)
    actor_only ='''
    # The Python source string must contain a literal regex word boundary.
    inserted = inserted.replace(chr(8), r'\b')
    assert function.count(old) == 1
    function = function.replace(old, inserted)
    old_owner = '''                parts.append([constructor, own_owner])
                if controlled:
                    parts.append([constructor, controlled_owner])'''
    new_owner = '''                scoped = any(word in phrase for word in words for phrase in scoped_personnel)
                if not scoped or any(word in remainder for word in words):
                    parts.append([constructor, own_owner])
                if controlled:
                    parts.append([constructor, controlled_owner])'''
    assert function.count(old_owner) == 1
    function = function.replace(old_owner, new_owner)
    return function_update(program, [function])


def run():
    before = alignment.ledger()
    assert not any(role == 'executor' and status == 'reserved' for role, status, _ in before)
    library = current.read(alignment.OUT / 'C/aligned_candidate.json')
    original = library['source_concept_program']
    library['source_concept_program'] = repaired_program(original)
    immutable_json(OUT / 'candidate.json', library)
    probes = [
        ('affiliate_only', "Recipient may disclose information to Recipient's affiliates' officers, directors and employees.", False, True),
        ('own_only', 'Recipient may disclose information to its officers, directors and employees.', True, False),
        ('both', "Recipient may disclose information to its employees and to affiliates' employees.", True, True),
    ]
    tree = ast.parse(library['source_concept_program'])
    tree.body = [n for n in tree.body if n.name != 'apply']
    tree.body += ast.parse("def apply(inputs,premises):\n    return {'roles':legal_roles(inputs['text'],[],[])}").body
    checked = []
    for name, text, own, affiliate in probes:
        result = execute_json(ast.unparse(tree), {'text': text}, {}, allow_helpers=True)
        def tags(value):
            if not isinstance(value, list) or not value:
                return []
            if value[0] == 'employees_of':
                return [value[1][0]]
            return [x for child in value[1:] for x in tags(child)]
        owners = tags(result['roles'][0])
        assert ('receiving_party' in owners) == own, (name, result)
        assert ('controlled_entities_of' in owners) == affiliate, (name, result)
        checked.append({'case': name, 'text': text, 'actual': result})
    immutable_json(OUT / 'owner_scope_regressions.json', {'rows': checked, 'new_model_calls': 0})
    rows = []
    protocol = current.read(current.OUT / 'protocol.json')
    for sid in protocol['sources']:
        raw = current.read(current.OUT / 'C/raw_observations' / (digest(sid) + '.json'))
        observation = current.convert(library, raw)
        immutable_json(OUT / 'observations' / (digest(sid) + '.json'), observation)
        all_rules = deepcopy(library)
        all_rules['selected_rule_ids'] = [r['id'] for r in library['language']['rules']]
        result = current.assess(all_rules, observation, sid)
        immutable_json(OUT / 'all_rules' / (digest(sid) + '.json'), result)
        rows.append(result)
    assert alignment.ledger() == before
    result = {'native_correct': sum(r['native_correct'] for r in rows), 'native_total': 96,
        'unresolved': sum(r['unresolved'] for r in rows),
        'hard_source_failures': [r['source'] for r in rows if not r['hard_source_pass']],
        'new_model_calls': 0, 'only_original_TRAIN': True, 'not_learning_credit': True,
        'original_neural_affiliate_fragment_was_correct': True, 'goal_complete': False}
    immutable_json(OUT / 'result.json', result)
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    run()
