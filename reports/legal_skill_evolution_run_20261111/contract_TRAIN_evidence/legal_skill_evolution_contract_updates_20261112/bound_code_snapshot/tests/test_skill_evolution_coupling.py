"""Candidate formation follows local records, not common final outputs."""
import unittest
from legal_skill_guard.skill_evolution.coupling import local_record_blocks


class CouplingTests(unittest.TestCase):
    def test_local_record_tracks_unique_use_def_aliases_without_merging_final_output(self):
        program = ('def apply(inputs, premises):\n'
            '    amount = premises["amount"]\n'
            '    record = {"ceiling": amount, "covered": premises["scope"]}\n'
            '    return {"answer": [record, premises["unrelated"]]}\n')
        result = local_record_blocks(program, {'amount', 'scope', 'unrelated'})
        self.assertEqual([r['ports'] for r in result], [['amount', 'scope']])
        self.assertEqual(local_record_blocks('def apply(inputs, premises):\n'
            '    return {"x": premises["a"], "y": premises["b"]}\n', {'a', 'b'}), [])

    def test_ambiguous_alias_and_overlarge_record_do_not_invent_coupling(self):
        program = ('def apply(inputs, premises):\n    amount = premises["a"]\n'
            '    amount = inputs["x"]\n    record = {"amount": amount, "scope": premises["b"]}\n'
            '    return {"answer": record}\n')
        self.assertEqual(local_record_blocks(program, {'a', 'b'}), [])
        self.assertEqual(local_record_blocks('def apply(inputs, premises):\n'
            '    record = {"a": premises["a"], "b": premises["b"], "c": premises["c"], "d": premises["d"]}\n'
            '    return {"answer": record}\n', {'a', 'b', 'c', 'd'}), [])


if __name__ == '__main__':unittest.main()
