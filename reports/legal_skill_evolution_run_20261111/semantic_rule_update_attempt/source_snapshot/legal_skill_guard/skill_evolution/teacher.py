"""One strict wire representation for bounded source-grounded skill proposals."""
from dataclasses import asdict
from copy import deepcopy
import ast
import json

from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues
from .objects import Skill, digest, lift, coupled_blocks, premise_uses, dependency_arguments
from .claim_scope import clause_identifier
from .native import record_schema, public_strings
from .grounding import bind_transcribed_quotes
from .teacher_transport import pack, serialized, INSTRUCTION
from .literal_facts import literal_bindings

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
        'mode': {'type': 'string', 'enum': ['read', 'skill', 'argument']}, 'question': STRING,
        'skill_id': NULL_STRING, 'field': STRING,
        'arguments': array(record_schema({'parameter': STRING,
            'namespace': {'type': 'string', 'enum': ['inputs', 'premises']}, 'port': STRING}))})),
    'outputs': array(record_schema({'name': STRING, 'type': TYPE, 'description': STRING,
        'query_clauses': array(STRING), 'public_tasks': array(STRING)})),
    'premises': array(record_schema({'name': STRING, 'type': TYPE,
        'mode': {'type': 'string', 'enum': ['constant', 'read']}, 'value': VALUE,
        'question': STRING, 'origin': ORIGIN, 'read_id': NULL_STRING, 'field': NULL_STRING})),
    'reads': array(READER),
    'semantic_records': array(record_schema({'id': STRING, 'ports': array(STRING), 'neighbors': array(STRING)})),
    'source_obligations': array(record_schema({'id': STRING, 'statement': STRING,
        'role': {'type': 'string', 'enum': ['preliminary', 'terminal', 'constraint', 'unknown']},
        'port': STRING, 'origin': ORIGIN})),
    'source_provenance': array(ORIGIN), 'version': {'type': 'integer', 'minimum': 1}})
LIFT_READER = record_schema({'question': STRING, 'source_locator': STRING,
    'fields': array(record_schema({'name': STRING, 'question': STRING}))})
PROPOSAL_SCHEMA = record_schema({'lift_reader': {'type': 'null'},
    'blocks': array(record_schema({'rationale': STRING,
    'revisions': array(record_schema({'operation': {'type': 'string', 'enum': ['create', 'revise']},
                                    'skill': SKILL}))}))})
PROPOSAL_SCHEMA['properties']['blocks']['maxItems'] = 3
PROPOSAL_SCHEMA['properties']['blocks']['items']['properties']['revisions'].update(minItems=1, maxItems=3)
assert not strict_output_schema_issues(PROPOSAL_SCHEMA)


def proposal_schema(planned_lift, max_blocks):
    schema = deepcopy(PROPOSAL_SCHEMA)
    schema['properties']['blocks']['maxItems'] = max_blocks
    if planned_lift:
        reader = deepcopy(LIFT_READER)
        names = planned_lift['premises']
        reader['properties']['fields'].update(minItems=len(names), maxItems=len(names))
        reader['properties']['fields']['items']['properties']['name'] = {'type': 'string', 'enum': names}
        schema['properties']['lift_reader'] = reader
    if strict_output_schema_issues(schema):
        raise ValueError('Invalid strict proposal output schema')
    return schema


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
    used.update(b['port'] for p in result.get('inputs', []) if p['mode'] == 'skill'
                for b in p.get('arguments', []) if b['namespace'] == 'premises')
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
    for port in result['inputs'].values():
        if 'arguments' in port:
            bindings = port['arguments']
            if len({b['parameter'] for b in bindings}) != len(bindings):
                raise ValueError('Duplicate dependency argument parameter')
            port['arguments'] = {b['parameter']: {'namespace': b['namespace'], 'port': b['port']}
                                 for b in bindings}
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
    # A current READ declares a parameter, not a value supplied by the teacher.
    # Its actual value is checked against current-source spans at execution.
    # Empty lineage supplies no evidence; nonempty lineage remains checked.
    origins = [p['origin'] for p in skill.premises.values() if not (
        p['mode'] == 'read' and p.get('origin') == {'source_id': '', 'view_id': '', 'quote': ''})]
    for origin in list(skill.source_provenance) + origins + [
        p['origin'] for p in skill.source_obligations]:
        if origin['source_id'] not in sources:
            raise ValueError('Teacher provenance outside its already-seen TRAIN context')
        row = sources[origin['source_id']]
        view = next((v for v in row['views'] if v['id'] == origin['view_id']), None)
        if not view or not origin['quote'] or not any(origin['quote'] in s for s in public_strings(view['public'])):
            raise ValueError('Teacher provenance is not a literal supplied TRAIN-source quote')
    for port in skill.outputs.values():
        for clause in port.get('query_clauses', []):
            identity = clause_identifier(clause)
            if identity[0] == 'heading' and not source_heading_matches(identity[1], sources):
                raise ValueError('Named query clause is not an exact supplied source heading')


def source_heading_matches(name, sources):
    return [{'source_id': row['key'], 'view_id': view['id'], 'heading': name}
            for row in sources.values() for view in row['views']
            if name in [line.strip() for line in view['public'].get('source_text', '').splitlines()]]


def bind_source_headings(value, sources):
    """Encode only an already supplied literal section identity; infer nothing."""
    result, changes = deepcopy(value), []
    for port in result['outputs']:
        for i, clause in enumerate(port.get('query_clauses', [])):
            try:clause_identifier(clause)
            except ValueError:
                if not isinstance(clause, str) or not clause or '\n' in clause or '\r' in clause:
                    raise
                matches = source_heading_matches(clause, sources)
                if not matches:raise ValueError('Query clause is neither an explicit numeric ID nor an exact source heading')
                port['query_clauses'][i] = 'heading:' + clause
                changes.append({'port': port['name'], 'literal_heading': clause,
                    'canonical_identity': 'heading:' + clause, 'source_matches': matches,
                    'literal_scope_preserved': True})
    return result, changes


def wrap_explicit_function_body(procedure):
    """Add only the declared apply signature to an otherwise complete body.

    Reject partial/mixed function definitions. AST construction preserves string
    literals too; text indentation could change multiline literal contents.
    Existing helper validation still rejects effects and undeclared premises.
    """
    tree = ast.parse(procedure)
    if len(tree.body) == 1 and isinstance(tree.body[0], ast.FunctionDef):
        return procedure, None
    if any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) for n in ast.walk(tree)):
        raise ValueError('Ambiguous helper body contains a definition')
    if not any(isinstance(n, ast.Return) for n in ast.walk(tree)):
        raise ValueError('A complete helper body must contain its own return')
    function = ast.parse('def apply(inputs, premises):\n    pass\n').body[0]
    function.body = tree.body
    wrapped = ast.unparse(ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))) + '\n'
    restored_body = ast.Module(body=ast.parse(wrapped).body[0].body, type_ignores=[])
    if ast.dump(restored_body, include_attributes=False) != ast.dump(tree, include_attributes=False):
        raise ValueError('Function wrapper changed body semantics')
    return wrapped, {'kind': 'fixed_apply_signature_only', 'body_AST_unchanged': True,
                     'raw_procedure_sha256': digest(procedure)}


def bind_declared_free_ports(procedure, inputs, premises):
    """Resolve only unambiguous declared ports, never locals or missing rules."""
    tree = ast.parse(procedure)
    function = tree.body[0]
    if not isinstance(function, ast.FunctionDef):
        raise ValueError('Bind ports only after the exact apply wrapper')
    if any(isinstance(n, (ast.FunctionDef, ast.Lambda, ast.ClassDef))
           for statement in function.body for n in ast.walk(statement)):
        return procedure, None  # No guessed lexical scopes.
    stored = {n.id for n in ast.walk(function) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
    called = {n.func.id for n in ast.walk(function) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    loaded = {n.id for n in ast.walk(function) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    free = loaded - stored - called - {'inputs', 'premises'}
    input_names, premise_names = {p['name'] for p in inputs}, {p['name'] for p in premises}
    if free & input_names & premise_names:
        raise ValueError('Implicit port is ambiguous across inputs and premises')
    bindings = {name: 'inputs' if name in input_names else 'premises'
                for name in sorted(free & (input_names | premise_names))}
    if not bindings:return procedure, None
    class Bind(ast.NodeTransformer):
        def visit_Name(self, node):
            if isinstance(node.ctx, ast.Load) and node.id in bindings:
                return ast.copy_location(ast.Subscript(value=ast.Name(id=bindings[node.id], ctx=ast.Load()),
                    slice=ast.Constant(value=node.id), ctx=ast.Load()), node)
            return node
    rewritten = ast.fix_missing_locations(Bind().visit(tree))
    return ast.unparse(rewritten) + '\n', {'kind': 'explicitly_declared_free_ports_only',
        'bindings': bindings, 'raw_procedure_sha256': digest(procedure),
        'conditions_operators_literals_and_existing_locals_preserved': True}


def compile_block(block, library, sources, arm):
    if not 1 <= len(block['revisions']) <= 3:
        raise ValueError('A candidate block has one to three revisions')
    revisions = []
    for proposed in block['revisions']:
        normalized, quote_bindings = bind_transcribed_quotes(proposed['skill'], sources)
        normalized, heading_bindings = bind_source_headings(normalized, sources)
        normalized['procedure'], body_wrapper = wrap_explicit_function_body(normalized['procedure'])
        normalized['procedure'], port_bindings = bind_declared_free_ports(normalized['procedure'],
            normalized['inputs'], normalized['premises'])
        normalized, removed = prune_unobserved_premise_metadata(normalized)
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
                              'source_heading_bindings': heading_bindings,
                              'retained_draft_installation': draft_installation,
                              'procedure_unchanged': new.procedure == proposed['skill']['procedure'],
                              'used_premise_values_unchanged': True}})
        if quote_bindings:
            revisions[-1]['representation_adaptation']['source_quote_transcription_bindings'] = quote_bindings
        if body_wrapper:
            revisions[-1]['representation_adaptation']['function_body_wrapper'] = body_wrapper
        if port_bindings:
            revisions[-1]['representation_adaptation']['explicit_port_bindings'] = port_bindings
    if len({r['skill_id'] for r in revisions}) != len(revisions):
        raise ValueError('Duplicate skill revisions in one block')
    proposed_skills = {**library.skills, **{r['skill_id']: Skill.from_dict(r['new']) for r in revisions}}
    for revision in revisions:
        skill = proposed_skills[revision['skill_id']]
        for port in skill.inputs.values():
            if port['mode'] == 'skill':
                dependency_arguments(skill, port, proposed_skills)
    return revisions


COMMON_PROMPT = '''You acquire reusable external legal/rule reasoning skills from already-seen TRAIN only.
Both models are frozen. Produce at most THREE candidate blocks with at most THREE skills each.
Each skill is one small Python def apply(inputs, premises) returning a dict with exactly its declared output fields.
Use ordinary Python expressions/assignments/if/for and min,max,sum,len,abs,round,sorted,all,any,int,float,bool,str,list,dict,range,enumerate,zip.
No imports, attributes/method calls, network, files, globals, recursion or other calls. Do not generate a full-document IR.
Read inputs are current facts/question fields, including explicitly GIVEN legal intermediate facts; source-premise constants carry literal provenance. Keep the complete source available to interpret given facts. Reader fields are primitive or flat arrays. Keep each field to one explicit semantic role. Separate an actor or recipient class from a protected information category, a purpose/context and an attached condition. Expand a named defined group using its explicit definition; do not put a full qualified sentence into an array consumed as individual class names. Do not infer permission merely by reversing a prohibition or a notification duty. Preserve the source qualifications in separately used fields or in the learned procedure; never treat a list of mentioned people as a permission rule.
Separate literal case facts, expressly GIVEN solved legal intermediates, literal rule parameters, and legal inferences.
Reading an expressly given intermediate is allowed; do not recompute it just to manufacture a dependency.
Put literal rule parameters in premise ports (constant with source evidence, or explicit current-source reads), not case-input ports.
Do not ask a local reader to decide an unprovided eligibility, statutory applicability or final legal answer: encode that rule in apply.
When a source rule actually invokes a distinct computed legal predicate, acquire/reuse its grounded producer and connect mode skill to its output.
Keep a naturally single-rule program single. Do not add gratuitous helper chains or intentionally defective old versions to create CoRev events.
For citation fields ask for literal citation strings, not legacy output label IDs. Retained read failures are actual model outputs, not proof that the source lacks the rule.
For every input in mode read set field equal to name, skill_id null, arguments []. A reusable helper may declare mode argument for an explicit caller-supplied entity, role or period: set field equal to name, skill_id null, arguments [], and describe its meaning in question. A root terminal may use the exact available names in literal_argument_context, including current_question, explicit employment roles and case_family_relations when actually provided. case_family_relations contains [owner, literal_kinship_word, relative] from an affirmative surface mention; it never supplies an inverted relation or negative fact. For example [X, father, Y] means X has father Y. Apply the source legal rule in the program, not in the literal binder. Missing arguments stay unresolved. For mode skill name the actual producer skill_id and output field; arguments binds ALL producer argument ports to explicit {namespace, port} sources: caller read/argument inputs, or constant/current-source premises. Source-rule call parameters such as the group named by a permission clause belong to premises, not factual READ inputs. The host reads these premises before invoking the dependent legal helper. Do not guess, default or bind missing roles. Do not ask a reader to derive an unprovided legal conclusion.
Semantic records name ports from the declared inputs and/or source premises; already-read ports are not counted as newly Lifted premises.
Read questions must describe the current-source concept rather than tell the reader an old value. The host separately binds supplied source-span IDs for read evidence. Constants require a literal origin. For a current-source premise read with no ancestral constant, origin may have source_id, view_id and quote all empty; this supplies no evidence or default, and its actual known value must have runtime current-source support. Nonempty lineage and source obligations remain literal and checked.
Declare only premises actually used in the procedure. Do not add unused rule_quotes or other evidence-only ports; source_provenance carries literal evidence.
Use semantic_records only for local legal records with genuine coupling; a common final return does not couple everything.
For a dependent helper, input mode skill names its real producer and field. Do not split fields of one source record into artificial skills.
A terminal helper returns answer in the exact current native type/labels; dependencies may return intermediate records.
Set answer.public_tasks to the supplied public view IDs this terminal actually handles, such as ["nda-5", "nda-7"] or ["EC"]. Other view types retain their ordinary direct fallback. This is public task projection shared by all arms, not a learned semantic router. Intermediate outputs use public_tasks []. Do not claim unrelated tasks to broaden coverage.
Declare each terminal answer's statutory query_clauses explicitly, for example ["3306(c)(2)"]. A genuinely named source section uses its exact standalone source heading prefixed by heading:, for example "heading:Non-Disclosure"; a descriptive paraphrase is not a section identity. This is a host-enforced applicability contract, not a claim of rule correctness. Use [] for intermediate outputs or a genuinely non-clause-specific terminal. Do not claim unrelated clauses merely to broaden retrieval. Case input reads with a supplied facts field must cite supporting facts/question spans; legal text remains available as context but cannot by itself establish a person's family relationship or other case fact.
Scope-sensitive source obligations describe what the helper checks, with a supported source quote; unknown roles stay unknown.
You may create helpers, revise multiple existing helpers jointly, preserve a useful reasoning skeleton or fix a process error.
Only skills in library are installed. retained_edits are rejected or historical proposals, not current skills.
To reuse a retained uninstalled draft, submit operation create with version 1 and its complete proposed program.
Revise only installed skills with their actual version plus one. Do not treat creation as an old/new co-revision event.
Candidate acceptance requires strict mean improvement on trigger parents and no decrease on every history parent.
History-only improvements cannot pass. Use update_objective to focus the limited candidate slots on trigger failures.
If scheduled_lift is present, supply lift_reader with a current-source question, locator and one question per named premise.
Do not repeat the skill, program, values, types or bindings. The host preserves the procedure and compiles this one candidate.
Its evaluation is mandatory; admission is not. A reader must return unknown for absent law, never an old-value default.
If no Lift is scheduled, lift_reader is null. Other create/revise blocks share the remaining candidate allowance.
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


def trigger_failure_views(feedback, trigger):
    """Expose existing per-view deficits, without adding supervision or gates."""
    result = []
    for row in feedback:
        if row['source'] not in trigger:
            continue
        for view in row['execution']['views']:
            if view['score']['grade'] == 1:
                continue
            execution = view['execution']
            result.append({'source': row['source'], 'view': view['view'],
                'controlled': view.get('controlled', False), 'grade': view['score']['grade'],
                'current_answer': execution['answer'],
                'terminal_skill': execution.get('terminal_skill'),
                'actual_failed_candidates': deepcopy(execution.get('failed_candidates', [])),
                'unresolved': execution.get('unresolved', False)})
    return result


def propose(teacher, *, arm, batch, library, source_records, feedback, learned_patterns,
            trigger, history, max_blocks=3, planned_lift=None, acquisition_contract=None):
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
                 **({'planned_lift': deepcopy(e['planned_lift']), 'lift_reader': deepcopy(e.get('lift_reader'))}
                    if e.get('planned_lift') else {}),
                 **({'raw_block': deepcopy(e['raw_block'])} if not e.get('revisions') and e.get('raw_block') else {}),
                 'table': compact_table(e.get('table'))} for e in library.provisional_edits]
    memory = [{k: deepcopy(v) for k, v in p.items() if k not in ('evidence', 'exact_version_table')}
              | {'exact_version_table': compact_table(p['exact_version_table'])} for p in learned_patterns]
    user = json.dumps({'arm': arm, 'batch': batch, 'sources': source_records,
        **({'acquisition_contract': acquisition_contract} if acquisition_contract is not None else {}),
        'literal_argument_context': {r['key']: {v['id']: literal_bindings(v) for v in r['views']}
                                     for r in source_records},
        'source_premise_block_candidates': {s.id: [list(b) for b in coupled_blocks(s)
            if all(s.premises[n]['mode'] == 'constant' for n in b)] for s in library.skills.values()},
        'update_objective': {'trigger_parents': list(trigger), 'history_parents': list(history),
            'trigger_failure_views': trigger_failure_views(feedback, trigger),
            'failure_focus': 'Prioritize edits affecting these below-full-grade or unresolved views. Correct views in the same parent do not by themselves offer trigger improvement. Parent-level admission and history preservation remain unchanged.',
            'trigger': 'strict improvement in mean selection_grade across these same parents',
            'history': 'every parent selection_grade must not decrease',
            'selection_grade': 'mean of all predeclared native and controlled views within each parent',
            'native_answer_contracts': {r['key']: {v['id']: v['answer_schema'] for v in r['views']}
                                      for r in source_records}},
        'scheduled_lift': planned_lift,
        'native_TRAIN_feedback': feedback, 'library': {k: asdict(s) for k, s in library.skills.items()},
        'retained_edits': retained, 'learned_patterns': memory}, ensure_ascii=False)
    system = COMMON_PROMPT + '\n' + ARM_PROMPTS[arm] + f'\nRemaining shared candidate slots: {max_blocks}. Return at most that many blocks.'
    user = serialized(pack(json.loads(user)))
    system += '\n' + INSTRUCTION
    schema = proposal_schema(planned_lift, max_blocks)
    identity = teacher.ledger.run_id + ':teacher:' + digest({'system': system, 'user': user,
                                                           'schema': schema})
    return teacher.propose(identity, source_ids=source_ids, system_prompt=system,
                           user_prompt=user, output_schema=schema)
