"""A source rule may pass its own source parameters into a legal dependency."""
from dataclasses import replace
from types import SimpleNamespace
import unittest

from legal_skill_guard.skill_evolution.objects import Skill, Library, coupled_blocks, lift
from legal_skill_guard.skill_evolution.runtime import SkillRuntime
from legal_skill_guard.skill_evolution.teacher import prune_unobserved_premise_metadata


def fixture():
    producer = Skill('projection_fixture', 'Binding fixture, not a legal result',
        'def apply(inputs, premises):\n    return {"value": inputs["owner"] + ":" + inputs["group"]}\n',
        {n: {'type': 'string', 'mode': 'argument'} for n in ('owner', 'group')},
        {'value': {'type': 'string'}}, {}, (), (), (), ()).validate()
    consumer = Skill('caller_fixture', 'Source argument binding fixture',
        'def apply(inputs, premises):\n    return {"answer": inputs["value"]}\n',
        {'value': {'type': 'string', 'mode': 'skill', 'skill_id': producer.id, 'field': 'value',
            'arguments': {n: {'namespace': 'premises', 'port': n} for n in ('owner', 'group')}}},
        {'answer': {'type': 'string'}}, {n: {'type': 'string', 'mode': 'constant',
            'value': v, 'origin': {'source': 'fixture'}} for n, v in
            [('owner', 'receiver'), ('group', 'Representatives')]}, (), (), (), ()).validate()
    return producer, consumer


class DependencyPremiseTests(unittest.TestCase):
    def test_real_call_arguments_count_as_uses_and_form_a_local_coupled_record(self):
        producer, consumer = fixture()
        self.assertIn(('group', 'owner'), coupled_blocks(consumer))
        runtime = SkillRuntime(SimpleNamespace())
        result = runtime.run({'key': 'fixture'}, {'id': 'v', 'answer_schema': {'type': 'string'}},
            Library(skills={s.id: s for s in (producer, consumer)}), retrieved=[consumer.id], fallback=False)
        self.assertEqual(result['answer'], 'receiver:Representatives')
        use = next(e for e in result['events'] if e['kind'] == 'USE')
        self.assertEqual(use['argument_bindings']['group'], {'namespace': 'premises', 'port': 'group'})

    def test_lifted_source_fields_are_read_before_dependency_and_missing_never_defaults(self):
        producer, consumer = fixture()
        reader = {'id': 'r', 'question': 'Read the current source call record', 'source_locator': 'source',
            'fields': {n: {'type': 'string', 'question': n} for n in ('owner', 'group')},
            'bindings': {n: n for n in ('owner', 'group')}, 'schema': {'type': 'object'}}
        new = lift(consumer, ['owner', 'group'], reader)
        self.assertEqual(new.procedure, consumer.procedure)
        values = {'owner': 'other', 'group': 'Agents'}
        def read(*args, **kwargs):return dict(values), {'kind': 'READ_LOCAL', 'fields': {}}
        runtime = SkillRuntime(SimpleNamespace(read=read))
        args = ({'key': 'fixture'}, {'id': 'v', 'answer_schema': {'type': 'string'}},
                Library(skills={s.id: s for s in (producer, new)}))
        result = runtime.run(*args, retrieved=[new.id], fallback=False)
        self.assertEqual(result['answer'], 'other:Agents')
        self.assertEqual(result['events'][0]['kind'], 'READ_LOCAL')
        del values['group']
        result = runtime.run(*args, retrieved=[new.id], fallback=False)
        self.assertTrue(result['unresolved'])
        self.assertFalse(any(e['kind'] == 'USE' for e in result['events']))

    def test_wire_pruning_keeps_a_premise_consumed_only_by_a_dependency(self):
        value = {'procedure': 'def apply(inputs, premises):\n    return {"answer": inputs["value"]}\n',
            'inputs': [{'name': 'value', 'mode': 'skill', 'arguments': [
                {'parameter': 'group', 'namespace': 'premises', 'port': 'group'}]}],
            'premises': [{'name': 'group', 'value': 'Representatives'}],
            'reads': [], 'source_obligations': [], 'semantic_records': []}
        self.assertEqual(prune_unobserved_premise_metadata(value), (value, []))


if __name__ == '__main__':unittest.main()
