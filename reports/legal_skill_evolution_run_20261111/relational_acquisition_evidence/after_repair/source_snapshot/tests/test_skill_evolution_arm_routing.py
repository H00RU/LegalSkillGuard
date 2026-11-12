"""Method wiring, using synthetic grades only; no claim of empirical benefit."""
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tests.test_skill_evolution_teacher_batch import fixture_study, ledger
from legal_skill_guard.skill_evolution.proposal_batch import prepare_context
from legal_skill_guard.skill_evolution import patterns

ARMS=('FreeEvolution','LiftOnly','CoRevOnly','Full','Lift+GenericJoint','AllPorts+CoRev')
COREVISION_ARMS={'CoRevOnly','Full','Lift+GenericJoint','AllPorts+CoRev'}


class ArmRoutingTests(unittest.TestCase):
    def test_every_corevision_arm_offers_the_same_pattern_candidate_path(self):
        with TemporaryDirectory() as temporary:
            folder=Path(temporary);study=fixture_study(folder,ledger(folder/'fixture.sqlite'))
            for arm in ARMS:
                with self.subTest(arm=arm), patch('legal_skill_guard.skill_evolution.proposal_batch.patterns.candidates',
                        return_value=[{'pattern_id':'fixture_only'}]) as proposer:
                    context=prepare_context(study,arm,2)
                    self.assertEqual(context['queue'],[{'pattern_id':'fixture_only'}] if arm in COREVISION_ARMS else [])
                    self.assertEqual(proposer.call_count,1 if arm in COREVISION_ARMS else 0)
                    if proposer.called:self.assertEqual(proposer.call_args.kwargs['generic'],arm=='Lift+GenericJoint')

    def test_accepted_updates_route_through_pattern_learning_in_every_corevision_arm(self):
        with TemporaryDirectory() as temporary:
            folder=Path(temporary);study=fixture_study(folder,ledger(folder/'fixture.sqlite'))
            baseline=study.parent
            def parent(key,library,**kwargs):
                row=baseline(key,library)
                if 'fixture_skill' in library.skills:row.update(selection_grade=1.0,native_grade=1.0)
                return row
            study.parent=parent
            origin={'source_id':'parent_16','view_id':'native','quote':'Fixture material only.'}
            skill={'id':'fixture_skill','intent':'Fixture only',
                'procedure':'def apply(inputs, premises):\n    return {"answer": "Entailment"}\n',
                'inputs':[],'outputs':[{'name':'answer','type':'string','description':'Fixture label'}],
                'premises':[],'reads':[],'semantic_records':[],'source_obligations':[],
                'source_provenance':[origin],'version':1}
            response={'value':{'blocks':[{'rationale':'Fixture only','revisions':[{'operation':'create','skill':skill}]}]},
                      'request_sha256':'fixture_no_model_call'}
            original=patterns.learn
            for arm in ARMS:
                with self.subTest(arm=arm), patch('legal_skill_guard.skill_evolution.study.propose_context',return_value=response), \
                        patch('legal_skill_guard.skill_evolution.study.patterns.learn',wraps=original) as learner, \
                        redirect_stdout(StringIO()):
                    receipt=study.update(arm,2)
                    self.assertEqual(receipt['selected_mask'],1)
                    self.assertEqual(learner.call_count,1 if arm in COREVISION_ARMS else 0)
                    if learner.called:self.assertEqual(learner.call_args.kwargs['generic'],arm=='Lift+GenericJoint')
                    self.assertEqual(receipt['learned_pattern_ids'],[])
                    self.assertEqual(receipt['pattern_count'],0)

if __name__=='__main__':unittest.main()
