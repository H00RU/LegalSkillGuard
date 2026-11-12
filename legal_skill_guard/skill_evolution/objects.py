"""Versioned external objects; no trainable model or learned-weight loader."""
from __future__ import annotations

import ast
from copy import deepcopy
from dataclasses import asdict, dataclass, field, replace
import hashlib
import json
from pathlib import Path
from .coupling import local_record_blocks
from .claim_scope import clause_identifier


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def premise_uses(procedure):
    tree = ast.parse(procedure)
    definitions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    if len(tree.body) != 1 or len(definitions) != 1 or definitions[0].name != 'apply':
        raise ValueError('A skill is one apply(inputs, premises) helper')
    function = definitions[0]
    if (function.decorator_list or function.args.vararg or function.args.kwarg
        or function.args.kwonlyargs or function.args.defaults
        or [a.arg for a in function.args.args] != ['inputs', 'premises']):
        raise ValueError('Explicit current inputs and source-premise ports required')
    forbidden = (ast.Import, ast.ImportFrom, ast.Attribute, ast.Global, ast.Nonlocal,
                 ast.ClassDef, ast.Lambda, ast.AsyncFunctionDef, ast.With, ast.Try)
    if any(isinstance(node, forbidden) for node in ast.walk(tree)):
        raise ValueError('Unsupported effectful skill helper')
    allowed_calls = {'min', 'max', 'sum', 'len', 'abs', 'round', 'sorted', 'all', 'any',
                     'int', 'float', 'bool', 'str', 'list', 'dict', 'range', 'enumerate', 'zip'}
    if any(isinstance(node, ast.Call) and (not isinstance(node.func, ast.Name)
           or node.func.id not in allowed_calls) for node in ast.walk(tree)):
        raise ValueError('Skill helpers use public deterministic primitives only')
    uses = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == 'premises':
            if not isinstance(node.slice, ast.Constant) or not isinstance(node.slice.value, str):
                raise ValueError('Premise ports must have explicit, auditable use sites')
            uses.setdefault(node.slice.value, []).append([node.lineno, node.col_offset])
    return uses


@dataclass(frozen=True)
class Skill:
    id: str
    intent: str
    procedure: str
    inputs: dict
    outputs: dict
    premises: dict
    reads: tuple
    semantic_records: tuple
    source_obligations: tuple
    source_provenance: tuple
    version: int = 1

    def validate(self):
        if not self.id or not self.intent or type(self.version) is not int or self.version < 1:
            raise ValueError('A skill requires identity, intent and a positive version')
        uses = premise_uses(self.procedure)
        if set(uses) != set(self.premises):
            raise ValueError('Declared premises must match the complete actual use inventory')
        read_ids = {r['id'] for r in self.reads}
        if len(read_ids) != len(self.reads):
            raise ValueError('Duplicate local reader identity')
        for port in self.outputs.values():
            if 'query_clauses' in port:
                if not isinstance(port['query_clauses'], list):
                    raise ValueError('Query clause contract must be a list')
                for clause in port['query_clauses']:
                    clause_identifier(clause)
        for name, port in self.inputs.items():
            if port.get('type') not in ('boolean', 'integer', 'number', 'string', 'array', 'object'):
                raise ValueError('Explicit input type required')
            mode = port.get('mode')
            if mode not in ('read', 'skill', 'argument'):
                raise ValueError('Unknown input acquisition mode')
            bindings = port.get('arguments', {})
            if not isinstance(bindings, dict):
                raise ValueError('Dependency arguments must map parameter names to caller inputs')
            if mode == 'skill':
                if not port.get('skill_id') or not port.get('field'):
                    raise ValueError('Actual producer and output field required')
                for parameter, local in bindings.items():
                    if (not isinstance(parameter, str) or not isinstance(local, str)
                            or local not in self.inputs
                            or self.inputs[local].get('mode') not in ('read', 'argument')):
                        raise ValueError('Dependency argument must bind a caller read or argument input')
            elif bindings or port.get('skill_id') is not None:
                raise ValueError('Only skill inputs may declare dependency bindings')
            elif mode == 'read' and not port.get('question'):
                raise ValueError('Current factual input needs a question')
        for name, value in self.premises.items():
            if value.get('type') not in ('boolean', 'integer', 'number', 'string', 'array'):
                raise ValueError('Explicit premise type required')
            if value.get('mode') == 'constant':
                if 'value' not in value or not value.get('origin'):
                    raise ValueError('Old-source constants need their actual provenance')
            elif value.get('mode') == 'read':
                if value.get('read_id') not in read_ids or not value.get('field') or 'value' in value:
                    raise ValueError('Lifted premises have no silent old-value fallback')
            else:
                raise ValueError('Unknown premise acquisition mode')
        for record in self.semantic_records:
            if not set(record['ports']) <= set(self.premises) | set(self.inputs):
                raise ValueError('Coupling record names an undeclared premise or input port')
        return self

    @property
    def hash(self):
        return digest(asdict(self))

    @classmethod
    def from_dict(cls, value):
        names = set(cls.__dataclass_fields__)
        if set(value) != names:
            raise ValueError('Skill fields differ from the single current schema')
        value = deepcopy(value)
        for key in ('reads', 'semantic_records', 'source_obligations', 'source_provenance'):
            value[key] = tuple(value[key])
        return cls(**value).validate()


def dependency_arguments(skill, port, skills):
    """Check the actual callee signature, without guessing roles or values."""
    producer = skills.get(port['skill_id'])
    if producer is None:
        raise ValueError('Missing skill dependency')
    if (port['field'] not in producer.outputs
            or producer.outputs[port['field']]['type'] != port['type']):
        raise ValueError('Dependency output type or field differs')
    required = {n: p for n, p in producer.inputs.items() if p['mode'] == 'argument'}
    bindings = port.get('arguments', {})
    if set(bindings) != set(required):
        raise ValueError('Dependency arguments must match all and only callee parameters')
    for name, local in bindings.items():
        if skill.inputs[local]['type'] != required[name]['type']:
            raise ValueError('Dependency argument type differs')
    return bindings


def lift(skill, names, reader, *, all_ports=False):
    """Replace one coupled block by current-source reads at every actual use."""
    skill.validate()
    names = tuple(sorted(set(names)))
    if not names or not set(names) <= set(skill.premises) or (len(names) > 3 and not all_ports):
        raise ValueError('Lift changes one bounded declared block; AllPorts is not truncated')
    if set(reader['bindings']) != set(names):
        raise ValueError('The joint reader must bind exactly the requested premise block')
    if not reader.get('question') or not reader.get('source_locator') or not reader.get('schema'):
        raise ValueError('Persist the actual reading question, source locator and schema')
    premises = deepcopy(skill.premises)
    for name in names:
        premises[name] = {'type': premises[name]['type'], 'mode': 'read',
            'read_id': reader['id'], 'field': reader['bindings'][name],
            'origin': premises[name]['origin']}
    result = replace(skill, premises=premises, reads=skill.reads + (deepcopy(reader),), version=skill.version + 1)
    result.validate()
    assert result.procedure == skill.procedure
    return result


def coupled_blocks(skill):
    """Same-record and at-most-two-hop closures, never the common RETURN."""
    skill.validate()
    records = {r['id']: r for r in skill.semantic_records}
    candidates = set()
    candidates.update(tuple(r['ports']) for r in local_record_blocks(skill.procedure,
        {n for n, p in skill.premises.items() if p['mode'] == 'constant'}))
    for key, record in records.items():
        frontier = {key}
        reached = set()
        for _ in range(3):
            reached |= frontier
            names = frozenset(p for r in reached for p in records[r]['ports'] if p in skill.premises)
            if 0 < len(names) <= 3:
                candidates.add(tuple(sorted(names)))
            frontier = {n for r in frontier for n in records[r].get('neighbors', []) if n in records} - reached
            if not frontier:
                break
    return sorted(candidates, key=lambda names: (len(names), names))


@dataclass
class Library:
    skills: dict[str, Skill] = field(default_factory=dict)
    revision_patterns: list = field(default_factory=list)
    provisional_edits: list = field(default_factory=list)
    execution_events: list = field(default_factory=list)

    @property
    def hash(self):
        # Runtime events do not mutate a functional library snapshot's identity.
        return digest({'skills': {k: v.hash for k, v in sorted(self.skills.items())},
                       'revision_patterns': self.revision_patterns})

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        value = {'schema': 'LSG-LegalSkill-20261111', 'hash': self.hash,
            'skills': {k: asdict(v) for k, v in sorted(self.skills.items())},
            'revision_patterns': self.revision_patterns, 'provisional_edits': self.provisional_edits,
            'execution_events': self.execution_events}
        temporary = path.with_suffix('.temporary.json')
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
        temporary.replace(path)

    @classmethod
    def load(cls, path):
        value = json.loads(Path(path).read_text())
        if value['schema'] != 'LSG-LegalSkill-20261111':
            raise ValueError('Not a current external legal-skill snapshot')
        result = cls(skills={k: Skill.from_dict(v) for k, v in value['skills'].items()},
            revision_patterns=value['revision_patterns'], provisional_edits=value['provisional_edits'],
            execution_events=value['execution_events'])
        if result.hash != value['hash']:
            raise ValueError('Library snapshot functional hash differs')
        return result


def apply_revision_package(library, revisions, expected_library_hash):
    """Exact old/new compare-and-swap, preserving the batch-initial snapshot."""
    if library.hash != expected_library_hash:
        raise ValueError('Candidate was evaluated against a different library')
    result = deepcopy(library)
    identities = [revision['skill_id'] for revision in revisions]
    if len(set(identities)) != len(identities):
        raise ValueError('Duplicate skill in one revision package')
    for revision in revisions:
        identity = revision['skill_id']
        old = result.skills.get(identity)
        if (old.hash if old else None) != revision['old_hash']:
            raise ValueError('Exact old skill version differs')
        new = Skill.from_dict(revision['new'])
        if new.id != identity or new.hash != revision['new_hash']:
            raise ValueError('Exact new skill identity or version differs')
        if new.version != (old.version + 1 if old else 1):
            raise ValueError('External skill versions advance exactly once')
        result.skills[identity] = new
    return result
