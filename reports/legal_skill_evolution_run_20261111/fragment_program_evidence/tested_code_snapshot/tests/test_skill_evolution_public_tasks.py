"""Task projection reuses the old EC/EV protection principle without new routing."""
from types import SimpleNamespace
import unittest

from legal_skill_guard.skill_evolution.objects import Skill, Library
from legal_skill_guard.skill_evolution.runtime import SkillRuntime


class PublicTaskTests(unittest.TestCase):
    def test_unrelated_public_task_never_invokes_the_terminal_or_its_reads(self):
        skill = Skill('fixture', 'Public task scope fixture',
            'def apply(inputs, premises):\n    return {"answer": inputs["value"]}\n',
            {'value': {'type': 'string', 'mode': 'read', 'question': 'fixture'}},
            {'answer': {'type': 'string', 'public_tasks': ['nda-5', 'nda-7']}},
            {}, (), (), (), ()).validate()
        def forbidden(*args, **kwargs):raise AssertionError('Public task protection must precede reads')
        result = SkillRuntime(SimpleNamespace(read=forbidden)).run({'key': 'fixture'},
            {'id': 'nda-20', 'answer_schema': {'type': 'string'}},
            Library(skills={skill.id: skill}), retrieved=[skill.id], fallback=False)
        self.assertTrue(result['unresolved'])
        self.assertEqual(result['failed_candidates'][0]['error'], 'StaticPublicTaskScopeMismatch')

    def test_matching_task_keeps_its_program_and_does_not_supply_a_legal_answer(self):
        skill = Skill('fixture', 'Source-independent task projection fixture',
            'def apply(inputs, premises):\n    return {"answer": "fixture answer"}\n',
            {}, {'answer': {'type': 'string', 'public_tasks': ['EC']}}, {}, (), (), (), ()).validate()
        result = SkillRuntime(SimpleNamespace()).run({'key': 'fixture'},
            {'id': 'EC', 'answer_schema': {'type': 'string'}},
            Library(skills={skill.id: skill}), retrieved=[skill.id], fallback=False)
        self.assertEqual(result['answer'], 'fixture answer')
        self.assertTrue(result['core_executed'])


if __name__ == '__main__':unittest.main()
