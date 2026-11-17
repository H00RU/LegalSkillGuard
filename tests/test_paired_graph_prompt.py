import json
import unittest

from legal_skill_guard.paired_interfaces.graph_interface import plans
from legal_skill_guard.paired_interfaces.graph_prompt import schema_visible_plan


class SchemaTransportTests(unittest.TestCase):
    def test_all_fixed_candidates_advertise_the_actual_output_schema(self):
        originals = plans()
        updated = [schema_visible_plan(p) for p in originals]
        self.assertEqual(len(updated), 3)
        for before, after in zip(originals, updated):
            self.assertIn(json.dumps(before['schema'], ensure_ascii=False, separators=(',', ':')), after['system'])
            self.assertEqual(before['schema'], after['schema'])
            self.assertEqual(before['operation'], after['operation'])
            self.assertEqual(before['version'], after['candidate_semantic_version'])
            self.assertNotEqual(before['version'], after['version'])
            self.assertNotIn('transport_revision', before)


if __name__ == '__main__':
    unittest.main()
