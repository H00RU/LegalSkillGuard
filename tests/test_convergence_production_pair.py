"""Generated pairs use the same production decoder, with no source-audit oracle."""
from copy import deepcopy
import hashlib
import inspect
import json
from textwrap import dedent
from types import SimpleNamespace
import unittest

from legal_skill_guard.paired_interfaces import residual as r
from legal_skill_guard.paired_interfaces.formal_actors import InterfaceActor
from legal_skill_guard.paired_interfaces.production_decode import decode_response
from legal_skill_guard.skill_evolution.objects import digest


def scope_consumer(u,c):
    if u['subject'] is None or u['exception_subject'] is None:return {'scope':None}
    return {'scope':u['subject']==u['exception_subject']}


class ProductionPairTests(unittest.TestCase):
    def fixture(self):
        code=dedent(inspect.getsource(scope_consumer));spec=r.FiniteModule.build('local_exception_scope',
            {'subject':['ordinary','negative',None],'exception_subject':['ordinary','negative',None]},[{}],scope_consumer,
            consumer_sha256=hashlib.sha256(code.encode()).hexdigest(),source_scope={
                'source_fields':['facts'],'local_unit':'one clause exception attachment'},program_source=code)
        asset=r.propose(spec,relational=True,max_new=2)['candidates'][0]
        source={'key':'fixture:one','dataset':'MAUD','views':[{'id':'native'}]}
        plan={'reader_kind':'consumer_relational','name':'generated_scope','relational_asset':asset,
            'relational_asset_sha256':digest(asset),'source_public_sha256':digest(source),
            'module_binding':spec.binding,'schema':r.reader_schema(asset),'system':r.reader_prompt(asset),
            'native_projection':{'native':'scope'}};plan['version']=digest(plan)
        view={'source':source['key'],'view':'v0','native_tasks':['native'],'native_public':{},
            'source_units':[],'plans':[plan],'consumer_sha256':spec.consumer_sha256,'consumer_context':{},
            'source_anchor':'clause:one','relational_public_source':{'facts':'The exception applies only to the ordinary covenant.'}}
        state={'subject':'ordinary','exception_subject':'ordinary'}
        raw={'status':'complete','observation':{'source_anchor':'clause:one','relations':r.encode(asset['features'],state)},
             'evidence':[{'field':'facts','quote':'The exception applies only to the ordinary covenant.'}]}
        return source,view,plan,raw

    def test_generated_pair_reaches_actual_native_execution_without_reference_card(self):
        source,view,plan,raw=self.fixture()
        got=decode_response(source,view,plan,{'content':json.dumps(raw),'finish_reason':'stop'})
        self.assertFalse(got['production_errors']);self.assertIs(got['native']['native']['answer'],True)
        self.assertTrue(got['decoder_receipt']['method_one_relational_pair_executed'])
        self.assertFalse(got['decoder_receipt']['source_semantics_verified_by_inference_oracle'])

    def test_stale_consumer_or_wrong_local_source_never_executes(self):
        source,view,plan,raw=self.fixture()
        stale=deepcopy(view);stale['consumer_sha256']='b'*64
        got=decode_response(source,stale,plan,{'content':json.dumps(raw),'finish_reason':'stop'})
        self.assertTrue(got['production_errors']);self.assertFalse(got['native']['native']['handled'])
        raw['observation']['source_anchor']='other-clause'
        got=decode_response(source,view,plan,{'content':json.dumps(raw),'finish_reason':'stop'})
        self.assertTrue(got['production_errors'])

    def test_nonstop_response_never_executes_synthesized_decoder(self):
        source,view,plan,raw=self.fixture()
        from unittest.mock import patch
        with patch('legal_skill_guard.paired_interfaces.residual.decode',side_effect=AssertionError('must not execute')):
            got=decode_response(source,view,plan,{'content':json.dumps(raw),'finish_reason':'length'})
        self.assertTrue(got['production_errors']);self.assertFalse(got['native']['native']['handled'])

    def test_existing_actor_accepts_versioned_generated_provider_and_keeps_all_tasks(self):
        source,view,plan,raw=self.fixture();calls=[]
        class Provider:
            def views(self,s):return [view]
            def verify_plan(self,s,v,p):calls.append((s['key'],p['version']))
        actor=InterfaceActor(SimpleNamespace(config={'model':'frozen-fixture'}),'/tmp/unused',
            plan_assets={},source_inputs=None,pipeline_binding={'fixture':'no model call'},relational_provider=Provider())
        self.assertEqual(actor.views(source),[view]);self.assertEqual(len(calls),1)


if __name__=='__main__':unittest.main()
