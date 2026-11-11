"""One strict wire representation for bounded source-grounded skill proposals."""
from dataclasses import asdict
from copy import deepcopy
import ast
import json

from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues
from .objects import Skill, digest, lift, coupled_blocks, premise_uses
from .native import record_schema, public_strings

STRING = {'type': 'string'}
NULL_STRING = {'type': ['string', 'null']}
TYPE = {'type': 'string', 'enum': ['boolean', 'integer', 'number', 'string', 'array', 'object']}
VALUE = {'anyOf': [{'type': 'boolean'}, {'type': 'number'}, STRING,
                  {'type': 'array', 'items': {'type': ['string', 'number', 'boolean']}}, {'type': 'null'}]}


def array(item):
    return {'type': 'array', 'items': item}


ORIGIN = record_schema({'source_id': STRING, 'view_id': STRING, 'quote': STRING})
READ_FIELD = record_schema({'name': STRING, 'type': TYPE, 'question': STRING})
READER = record_schema({'id': STRING, 'question': STRING, 'source_locator': STRING,
    'fields': array(READ_FIELD), 'bindings': array(record_schema({'premise': STRING, 'field': STRING}))})
SKILL = record_schema({'id': STRING, 'intent': STRING, 'procedure': STRING,
    'inputs': array(record_schema({'name': STRING, 'type': TYPE,
        'mode': {'type': 'string', 'enum': ['read', 'skill']}, 'question': STRING,
        'skill_id': NULL_STRING, 'field': STRING})),
    'outputs': array(record_schema({'name': STRING, 'type': TYPE, 'description': STRING})),
    'premises': array(record_schema({'name': STRING, 'type': TYPE,
        'mode': {'type': 'string', 'enum': ['constant', 'read']}, 'value': VALUE,
        'question': STRING, 'origin': ORIGIN, 'read_id': NULL_STRING, 'field': NULL_STRING})),
    'reads': array(READER),
    'semantic_records': array(record_schema({'id': STRING, 'ports': array(STRING), 'neighbors': array(STRING)})),
    'source_obligations': array(record_schema({'id': STRING, 'statement': STRING,
        'role': {'type': 'string', 'enum': ['preliminary', 'terminal', 'constraint', 'unknown']},
        'port': STRING, 'origin': ORIGIN})),
    'source_provenance': array(ORIGIN), 'version': {'type': 'integer', 'minimum': 1}})
PROPOSAL_SCHEMA = record_schema({'blocks': array(record_schema({'rationale': STRING,
    'revisions': array(record_schema({'operation': {'type': 'string', 'enum': ['create', 'revise', 'lift']},
                                    'skill': SKILL}))}))})
PROPOSAL_SCHEMA['properties']['blocks']['maxItems'] = 3
PROPOSAL_SCHEMA['properties']['blocks']['items']['properties']['revisions'].update(minItems=1, maxItems=3)
assert not strict_output_schema_issues(PROPOSAL_SCHEMA)


def named(values, key='name'):
    result = {}
    for value in values:
        name = value[key]
        if name in result:
            raise ValueError('Duplicate explicit port name')
        result[name] = {k: deepcopy(v) for k, v in value.items() if k != key}
    return result


def reader_from_wire(reader):
    fields = named(reader['fields'])
    bindings = {b['premise']: b['field'] for b in reader['bindings']}
    if len(bindings) != len(reader['bindings']):
        raise ValueError('Duplicate reader binding')
    return {'id': reader['id'], 'question': reader['question'],
        'source_locator': reader['source_locator'], 'fields': fields, 'bindings': bindings,
        'schema': record_schema({name: {'type': field['type']} for name, field in fields.items()})}


def prune_unobserved_premise_metadata(value):
    """Remove evidence-only ports only when the program cannot observe them.

    Whole-map access, aliases, iteration, and len(premises) preclude this
    adaptation. Missing used ports, procedures and used legal values stay intact.
    """
    result = deepcopy(value)
    used = set(premise_uses(result['procedure']))
    dead = {p['name'] for p in result['premises']} - used
    if not dead:
        return result, []
    tree = ast.parse(result['procedure'])
    parents = {id(child): node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == 'premises' and isinstance(node.ctx, ast.Load):
            parent = parents[id(node)]
            if not (isinstance(parent, ast.Subscript) and parent.value is node
                    and isinstance(parent.slice, ast.Constant) and isinstance(parent.slice.value, str)):
                return result, []
    if any(o['port'] in dead for o in result['source_obligations']):
        return result, []  # Do not discard a declared semantic obligation.
    removed = [p for p in result['premises'] if p['name'] in dead]
    result['premises'] = [p for p in result['premises'] if p['name'] not in dead]
    readers = []
    for reader in result['reads']:
        old_fields = {b['field'] for b in reader['bindings'] if b['premise'] in dead}
        reader['bindings'] = [b for b in reader['bindings'] if b['premise'] not in dead]
        live_fields = {b['field'] for b in reader['bindings']}
        reader['fields'] = [f for f in reader['fields'] if f['name'] not in old_fields - live_fields]
        if reader['bindings']:
            readers.append(reader)
    result['reads'] = readers
    for record in result['semantic_records']:
        record['ports'] = [p for p in record['ports'] if p not in dead]
    assert result['procedure'] == value['procedure']
    return result, removed


def skill_from_wire(value):
    result = deepcopy(value)
    result['inputs'] = named(value['inputs'])
    result['outputs'] = named(value['outputs'])
    result['premises'] = named(value['premises'])
    result['reads'] = tuple(reader_from_wire(r) for r in value['reads'])
    for name, premise in result['premises'].items():
        if premise['mode'] == 'read':
            if premise.pop('value') is not None:
                raise ValueError('A current-source read cannot retain an old-value fallback')
        else:
            if premise.pop('read_id') is not None or premise.pop('field') is not None:
                raise ValueError('Constant premise cannot contain an unexecuted read binding')
    return Skill.from_dict(result)


def validate_grounding(skill, sources):
    for origin in list(skill.source_provenance) + [p['origin'] for p in skill.premises.values()] + [
        p['origin'] for p in skill.source_obligations]:
        if origin['source_id'] not in sources:
            raise ValueError('Teacher provenance outside its already-seen TRAIN context')
        row = sources[origin['source_id']]
        view = next((v for v in row['views'] if v['id'] == origin['view_id']), None)
        if not view or not origin['quote'] or not any(origin['quote'] in s for s in public_strings(view['public'])):
            raise ValueError('Teacher provenance is not a literal supplied TRAIN-source quote')
    if not skill.source_provenance:
        raise ValueError('A learned skill needs actual source provenance')
    for name, port in skill.inputs.items():
        if port['mode'] == 'read' and (not port['question'] or port['skill_id'] is not None or port['field'] != name):
            raise ValueError('Current factual input needs a question and no hidden dependency')
        if port['mode'] == 'skill' and (not port['skill_id'] or not port['field']):
            raise ValueError('Actual producer and output field required')


def compile_block(block, library, sources, arm):
    if not 1 <= len(block['revisions']) <= 3:
        raise ValueError('A candidate block has one to three revisions')
    revisions = []
    for proposed in block['revisions']:
        normalized, removed = prune_unobserved_premise_metadata(proposed['skill'])
        new = skill_from_wire(normalized)
        old = library.skills.get(new.id)
        operation = proposed['operation']
        draft_installation = None
        if old is None and operation == 'revise':
            # A retained failed proposal is evidence, not an installed skill.
            # Recover only a unique recorded predecessor of this exact ID and
            # version. This installs the proposed program as a creation; it
            # never creates a fictitious old-version CoRev comparison.
            ancestors = {}
            for edit in library.provisional_edits:
                for revision in edit.get('revisions') or []:
                    ancestor = Skill.from_dict(revision['new'])
                    if ancestor.id == new.id and ancestor.version == new.version - 1:
                        ancestors[ancestor.hash] = ancestor
            if len(ancestors) == 1:
                predecessor = next(iter(ancestors.values()))
                draft_installation = {'recorded_predecessor_hash': predecessor.hash,
                    'proposed_operation': operation, 'proposed_version': new.version,
                    'installed_operation': 'create', 'installed_version': 1,
                    'counts_as_existing_skill_revision': False}
                wire = asdict(new)
                wire['version'] = 1
                new = Skill.from_dict(wire)
                operation = 'create'
        if (old is None) != (operation == 'create'):
            raise ValueError('Create/revise identity differs from the actual library')
        if new.version != (old.version + 1 if old else 1):
            raise ValueError('Teacher skill version differs from its actual old version')
        validate_grounding(new, sources)
        if operation == 'lift':
            if arm not in ('Full', 'LiftOnly', 'Lift+GenericJoint', 'AllPorts+CoRev'):
                raise ValueError('This arm does not use the dedicated Lift operator')
            names = [n for n in old.premises if old.premises[n]['mode'] == 'constant'
                     and new.premises.get(n, {}).get('mode') == 'read']
            if len(names) > 1 and arm != 'AllPorts+CoRev' and tuple(sorted(names)) not in coupled_blocks(old):
                raise ValueError('Multi-premise Lift must be a declared local-record closure')
            readers = [r for r in new.reads if r['id'] not in {r['id'] for r in old.reads}]
            if len(readers) != 1:
                raise ValueError('Lift uses one explicit joint reader')
            expected = lift(old, names, readers[0], all_ports=arm == 'AllPorts+CoRev')
            # Questions are acquisition metadata, not source-value fallbacks.
            expected_premises = deepcopy(expected.premises)
            for name in names:
                expected_premises[name]['question'] = old.premises[name].get('question', '')
            if new.procedure != old.procedure or new.inputs != old.inputs or new.outputs != old.outputs:
                raise ValueError('Lift must preserve the existing reasoning procedure')
            if new.premises != expected_premises:
                raise ValueError('Lift changed undeclared premise content')
        if arm == 'AllPorts+CoRev' and operation == 'create' and new.premises:
            if any(p['mode'] == 'constant' for p in new.premises.values()):
                raise ValueError('AllPorts acquisition must parameterize all related source-premise ports')
        revisions.append({'skill_id': new.id, 'old_hash': old.hash if old else None,
                          'new_hash': new.hash, 'new': asdict(new), 'operation': operation,
                          'representation_adaptation': {'removed_unobserved_declarations': removed,
                              'retained_draft_installation': draft_installation,
                              'procedure_unchanged': new.procedure == proposed['skill']['procedure'],
                              'used_premise_values_unchanged': True}})
    if len({r['skill_id'] for r in revisions}) != len(revisions):
        raise ValueError('Duplicate skill revisions in one block')
    return revisions


COMMON_PROMPT = '''You acquire reusable external legal/rule reasoning skills from already-seen TRAIN only.
Both models are frozen. Produce at most THREE candidate blocks with at most THREE skills each.
Each skill is one small Python def apply(inputs, premises) returning a dict with exactly its declared output fields.
Use ordinary Python expressions/assignments/if/for and min,max,sum,len,abs,round,sorted,all,any,int,float,bool,str,list,dict,range,enumerate,zip.
No imports, attributes/method calls, network, files, globals, recursion or other calls. Do not generate a full-document IR.
Read inputs are current facts/question fields; source-premise constants carry literal provenance. Reader fields are primitive or flat arrays.
For citation fields ask for literal citation strings, not legacy output label IDs. Retained read failures are actual model outputs, not proof that the source lacks the rule.
For every input in mode read set field equal to name and skill_id null; in mode skill name the actual producer skill_id and its output field.
Semantic records name ports from the declared inputs and/or source premises; already-read ports are not counted as newly Lifted premises.
Read questions must describe the current-source concept rather than tell the reader an old value. The host separately binds supplied source-span IDs for read evidence.
Declare only premises actually used in the procedure. Do not add unused rule_quotes or other evidence-only ports; source_provenance carries literal evidence.
Use semantic_records only for local legal records with genuine coupling; a common final return does not couple everything.
For a dependent helper, input mode skill names its real producer and field. Do not split fields of one source record into artificial skills.
A terminal helper returns answer in the exact current native type/labels; dependencies may return intermediate records.
Scope-sensitive source obligations describe what the helper checks, with a supported source quote; unknown roles stay unknown.
You may create helpers, revise multiple existing helpers jointly, preserve a useful reasoning skeleton or fix a process error.
Only skills in library are installed. retained_edits are rejected or historical proposals, not current skills.
To reuse a retained uninstalled draft, submit operation create with version 1 and its complete proposed program.
Revise/lift only installed skills with their actual version plus one. Do not treat creation as an old/new co-revision event.
Candidate acceptance requires strict mean improvement on trigger parents and no decrease on every history parent.
History-only improvements cannot pass. Use update_objective to focus the limited candidate slots on trigger failures.
For operation lift preserve old procedure/inputs/outputs, replace a coupled constant block (up to 3 premises) with ONE joint current-source reader,
and keep every unrelated field intact. AllPorts may cover all related ports in one reader.
Do not copy a case answer into a lookup, branch on a source ID/person name or fabricate absent law. Native labels supervise selection, not missing semantic gold.
All blocks are evaluated on complete mixed-version tables. A singleton may fail yet a joint package improve; preserve such candidates.
Return fewer blocks or none if no grounded useful candidate exists. Version existing skills by exactly one; new skills start at one.
'''

ARM_PROMPTS = {
    'FreeEvolution': 'Freely propose strong joint process/read/contract edits. Use the supplied complete prior edits and tables; no dedicated Lift operator is required.',
    'LiftOnly': 'Prioritize coupled current-source premise lifting. Joint free repairs remain possible; no CoRev pattern learning is supplied.',
    'CoRevOnly': 'Use the supplied contextual co-revision patterns to generate companion edits. Free source reading is available; do not invoke the dedicated Lift operator.',
    'Full': 'Use coupled premise lifting and contextual co-revision patterns. Learned companion edit patterns must change candidate generation on the current source.',
    'Lift+GenericJoint': 'Use coupled lifting plus generic dependency scheduling and multi-location edit-pattern memory. You may learn dependencies and generate coordinated edits; do not restrict yourself to greedy single edits.',
    'AllPorts+CoRev': 'Parameterize ALL related source-premise ports at acquisition, one joint reader is allowed without a three-port cap. Use contextual co-revision patterns to generate companion edits.'}


def propose(teacher, *, arm, batch, library, source_records, feedback, learned_patterns,
            trigger, history, max_blocks=3):
    source_ids = [r['key'] for r in source_records]
    if set(trigger) & set(history) or set(trigger) | set(history) != set(source_ids):
        raise ValueError('Teacher objective must identify the complete disjoint replay cohort')
    def compact_table(table):
        if not table:return None
        failures, reads = [], {}
        for cell in table['mixed_version_table']:
            for view in (cell.get('trace') or {}).get('views', []):
                execution = view['execution']
                for failure in execution.get('failed_candidates', []):
                    failures.append({'source': cell['source'], 'view': view['view'], 'mask': cell['mask'], **failure})
                for event in execution.get('events', []):
                    if event.get('kind') == 'READ_LOCAL':
                        reads[event['call_id']] = {'source': cell['source'], 'view': view['view'],
                            'question': event['question'], 'locator': event['locator'],
                            'returned_fields': event['fields']}
        return {k: deepcopy(table[k]) for k in ('hash', 'trigger', 'history', 'classification', 'complete', 'minimal_blocks')} | {
            'mixed_version_table': [{k: c[k] for k in ('mask', 'source', 'native_parent_grade', 'measured')}
                                   for c in table['mixed_version_table']],
            'actual_execution_failures': failures, 'unique_actual_reads': reads}
    retained = [{**{k: e.get(k) for k in ('batch', 'candidate_index', 'revisions', 'error', 'read_diagnostics', 'selection_exclusion')},
                 'table': compact_table(e.get('table'))} for e in library.provisional_edits]
    memory = [{k: deepcopy(v) for k, v in p.items() if k not in ('evidence', 'exact_version_table')}
              | {'exact_version_table': compact_table(p['exact_version_table'])} for p in learned_patterns]
    user = json.dumps({'arm': arm, 'batch': batch, 'sources': source_records,
        'source_premise_block_candidates': {s.id: [list(b) for b in coupled_blocks(s)
            if all(s.premises[n]['mode'] == 'constant' for n in b)] for s in library.skills.values()},
        'update_objective': {'trigger_parents': list(trigger), 'history_parents': list(history),
            'trigger': 'strict improvement in mean selection_grade across these same parents',
            'history': 'every parent selection_grade must not decrease',
            'selection_grade': 'mean of all predeclared native and controlled views within each parent',
            'native_answer_contracts': {r['key']: {v['id']: v['answer_schema'] for v in r['views']}
                                      for r in source_records}},
        'native_TRAIN_feedback': feedback, 'library': {k: asdict(s) for k, s in library.skills.items()},
        'retained_edits': retained, 'learned_patterns': memory}, ensure_ascii=False)
    system = COMMON_PROMPT + '\n' + ARM_PROMPTS[arm] + f'\nRemaining shared candidate slots: {max_blocks}. Return at most that many blocks.'
    identity = teacher.ledger.run_id + ':teacher:' + digest({'system': system, 'user': user,
                                                           'schema': PROPOSAL_SCHEMA})
    return teacher.propose(identity, source_ids=source_ids, system_prompt=system,
                           user_prompt=user, output_schema=PROPOSAL_SCHEMA)
