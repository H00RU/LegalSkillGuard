"""Role-bound invocation contracts; fixtures confer no scientific evidence."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
import unittest

import jsonschema

from legal_skill_guard.skill_evolution.objects import Skill, Library, dependency_arguments
from legal_skill_guard.skill_evolution.runtime import FrozenReads, SkillRuntime
from legal_skill_guard.skill_evolution.teacher import SKILL, skill_from_wire
from legal_skill_guard.skill_evolution.patterns import compatible_dependency_versions
from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues


def graph():
    producer = Skill('predicate', 'fixture role-bound predicate',
        'def apply(inputs, premises):\n    return {"eligible": inputs["given"]}\n',
        {'person': {'type': 'string', 'mode': 'argument'},
         'given': {'type': 'boolean', 'mode': 'read', 'question': 'Is the bound person explicitly eligible?'}},
        {'eligible': {'type': 'boolean'}}, {}, (), (), (), ()).validate()
    inputs = {n: {'type': 'string', 'mode': 'read', 'question': n} for n in ('first', 'second')}
    for name, local in [('a', 'first'), ('b', 'second'), ('again', 'first')]:
        inputs[name] = {'type': 'boolean', 'mode': 'skill', 'skill_id': 'predicate',
                        'field': 'eligible', 'arguments': {'person': {'namespace': 'inputs', 'port': local}}}
    terminal = replace(producer, id='terminal', inputs=inputs,
        outputs={'answer': {'type': 'boolean'}}, procedure=(
            'def apply(inputs, premises):\n'
            '    return {"answer": inputs["a"] and not inputs["b"] and inputs["again"]}\n'))
    return Library(skills={s.id: s for s in (producer, terminal)})


class ArgumentTests(unittest.TestCase):
    def test_interface_break_is_not_semantic_joint_necessity(self):
        library = graph()
        p, c = library.skills['predicate'], library.skills['terminal']
        self.assertTrue(compatible_dependency_versions(p, p, c, c, 'eligible'))
        broken = replace(p, inputs={**p.inputs, 'year': {'type': 'integer', 'mode': 'argument'}})
        self.assertFalse(compatible_dependency_versions(p, broken, c, c, 'eligible'))
        # Changing who is bound remains a semantic edit when all four
        # combinations still have the same valid interface.
        inputs = deepcopy(c.inputs)
        inputs['a']['arguments']['person'] = {'namespace': 'inputs', 'port': 'second'}
        other = replace(c, inputs=inputs)
        self.assertTrue(compatible_dependency_versions(p, p, c, other, 'eligible'))

    def run_graph(self, library, values=None):
        calls = []
        def read(*args, **kw):
            calls.append(kw)
            if 'first' in kw['fields']:
                result = {'first': 'Alice', 'second': 'Bob'} if values is None else values
            else:
                result = {'given': kw['invocation_arguments']['person'] == 'Alice'}
            return result, {'kind': 'READ_LOCAL', 'fields': {}}
        runtime = SkillRuntime(SimpleNamespace(read=read))
        result = runtime.run({'key': 'fixture'}, {'id': 'v', 'answer_schema': {'type': 'boolean'}},
            library, retrieved=['terminal'], fallback=False)
        return result, calls

    def test_different_people_have_distinct_reads_and_same_binding_is_reused(self):
        result, calls = self.run_graph(graph())
        self.assertTrue(result['core_executed'])
        self.assertTrue(result['answer'])
        self.assertEqual(len(calls), 3)
        self.assertEqual([c['invocation_arguments'] for c in calls[1:]],
                         [{'person': 'Alice'}, {'person': 'Bob'}])
        uses = [e for e in result['events'] if e['kind'] == 'USE']
        self.assertEqual([e['value'] for e in uses], [True, False, True])
        self.assertEqual(uses[1]['argument_bindings'], {'person': {'namespace': 'inputs', 'port': 'second'}})
        applies = [e for e in result['events'] if e['kind'] == 'APPLY' and e['skill_id'] == 'predicate']
        self.assertEqual(len(applies), 2)
        self.assertEqual(applies[1]['invocation_arguments'], {'person': 'Bob'})

    def test_bad_or_missing_binding_is_rejected_before_any_read(self):
        for bindings in ({}, {'person': 'a'}, {'person': 'absent'}, {'extra': 'first'}):
            library = graph()
            inputs = deepcopy(library.skills['terminal'].inputs)
            inputs['a']['arguments'] = bindings
            library.skills['terminal'] = replace(library.skills['terminal'], inputs=inputs)
            result, calls = self.run_graph(library)
            self.assertTrue(result['unresolved'])
            self.assertEqual(calls, [])
        library = graph()
        inputs = deepcopy(library.skills['terminal'].inputs)
        inputs['first']['type'] = 'integer'
        library.skills['terminal'] = replace(library.skills['terminal'], inputs=inputs)
        result, calls = self.run_graph(library)
        self.assertTrue(result['unresolved'])
        self.assertEqual(calls, [])

    def test_unknown_or_mistyped_actual_role_never_uses_a_default(self):
        for values in ({'second': 'Bob'}, {'first': 12, 'second': 'Bob'}):
            result, calls = self.run_graph(graph(), values)
            self.assertTrue(result['unresolved'])
            self.assertEqual(len(calls), 1)
            self.assertFalse(any(e['kind'] == 'USE' for e in result['events']))

    def test_reader_receives_binding_without_losing_source_or_given_legal_context(self):
        reads = FrozenReads(None)
        captured = []
        def generate(source, view, **kw):
            captured.append(kw)
            names = kw['content']['fields']
            values = {n: ['Alice', 'Bob'] if n == 'people' else [True, False] for n in names}
            return {n: {'status': 'known', 'value': v, 'support_ids': [0]} for n, v in values.items()}, {
                'call_id': str(len(captured)), 'physical_call_id': str(len(captured)), 'usage': {}}
        reads.generate = generate
        source = {'key': 'fixture', 'dataset': 'fixture'}
        view = {'id': 'v', 'public': {'source_text': 'Full law defines the given predicate.',
                'facts': 'Given Alice satisfies the stated legal condition.'}}
        _, event = reads.read(source, view, question='Read bound facts',
            fields={n: {'type': 'array'} for n in ('people', 'given')},
            locator='full supplied source', purpose='fixture', alignment=('people', ['given']),
            invocation_arguments={'taxpayer': 'Bob', 'year': 2017})
        self.assertEqual(len(captured), 2)
        for kw in captured:
            self.assertEqual(kw['content']['invocation_arguments'], {'taxpayer': 'Bob', 'year': 2017})
            text = ' '.join(s['text'] for s in kw['content']['source_spans'])
            self.assertIn('Full law defines', text)
            self.assertIn('Given Alice satisfies', text)
        self.assertEqual(event['invocation_arguments']['taxpayer'], 'Bob')

    def test_wire_schema_and_parser_agree_on_explicit_binding(self):
        library = graph()
        origin = {'source_id': 'fixture', 'view_id': 'v', 'quote': 'Full law'}
        raw = {'id': 'terminal', 'intent': 'fixture', 'procedure': library.skills['terminal'].procedure,
            'inputs': [{'name': n, 'type': p['type'], 'mode': p['mode'], 'question': p.get('question', ''),
                       'skill_id': p.get('skill_id'), 'field': p.get('field', n),
                       'arguments': [{'parameter': k, **v} for k, v in p.get('arguments', {}).items()]}
                      for n, p in library.skills['terminal'].inputs.items()],
            'outputs': [{'name': 'answer', 'type': 'boolean', 'description': 'fixture', 'query_clauses': [], 'public_tasks': []}],
            'premises': [], 'reads': [], 'semantic_records': [], 'source_obligations': [],
            'source_provenance': [origin], 'version': 1}
        self.assertEqual(strict_output_schema_issues(SKILL), [])
        jsonschema.validate(raw, SKILL)
        skill = skill_from_wire(raw)
        self.assertEqual(dependency_arguments(skill, skill.inputs['a'], library.skills), {'person': {'namespace': 'inputs', 'port': 'first'}})
        raw['inputs'][2]['arguments'].append({'parameter': 'person', 'namespace': 'inputs', 'port': 'second'})
        with self.assertRaisesRegex(ValueError, 'Duplicate dependency argument'):
            skill_from_wire(raw)


if __name__ == '__main__':
    unittest.main()
