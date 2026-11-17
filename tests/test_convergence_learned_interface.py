from tempfile import TemporaryDirectory
import unittest

from legal_skill_guard.paired_interfaces.formal_training import RelationalInterfaceLibrary


def plan(name,choice):
    return {'name':name,'reader_kind':'consumer_relational_program','choices':{'local':choice},
        'is_correct_fixed_raw_control':choice==0}


class LearnedInterfaceTests(unittest.TestCase):
    def observation(self,source,choice,utility,faithful):
        return {'source':source,'view':'native','dataset':'Diversity','profile':[['local',choice]],
            'native_utility':utility,'source_fidelity':{'all_local_relations_source_faithful':faithful}}

    def test_score_compatible_unfaithful_read_cannot_win_or_learn_from_current_source(self):
        with TemporaryDirectory() as root:
            learner=RelationalInterfaceLibrary(root,actor=None,train_sources=['a','b'],initial_common_library_sha256='a'*64)
            learner.records=[self.observation('a',0,.5,True),self.observation('a',1,1,False),
                self.observation('b',0,0,True),self.observation('b',1,1,True)]
            view={'plans':[plan('fixed',0),plan('relation',1)]}
            chosen,receipt=learner.choose({'key':'b','dataset':'Diversity'},view)
            self.assertEqual(chosen['name'],'fixed');self.assertEqual(receipt['paired_learning_sources'],['a'])
            self.assertFalse(receipt['current_source_gold_or_current_read_used'])

    def test_unpaired_scores_do_not_create_selection_and_snapshot_restores_prefix(self):
        with TemporaryDirectory() as root:
            learner=RelationalInterfaceLibrary(root,actor=None,train_sources=['a','b'],initial_common_library_sha256='a'*64)
            learner.records=[self.observation('a',0,0,True),self.observation('b',1,1,True)]
            view={'plans':[plan('fixed',0),plan('relation',1)]}
            chosen,receipt=learner.choose({'key':'new','dataset':'Diversity'},view)
            self.assertEqual(chosen['name'],'fixed');self.assertFalse(receipt['unseen_mother_reuse'])
            with self.assertRaises(ValueError):learner.snapshot(batch=1,visible_prefix=['a'])
            snapshot=learner.snapshot(batch=1,visible_prefix=['a','b'])
            restored=RelationalInterfaceLibrary.restore(root,actor=None,train_sources=['a','b'],snapshot=snapshot)
            self.assertEqual(restored.records,learner.records)


if __name__=='__main__':unittest.main()
