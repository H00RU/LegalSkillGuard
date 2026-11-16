import json
import unittest
from pathlib import Path
from dataclasses import replace
from channel import *

class Checks(unittest.TestCase):
    def rows(self,n=400,edit='identity',world=None,version='a:v1'):
        g=world or Graph(1,0,0)
        return [Pair(str(i),g,EDITS[edit](g),version) for i in range(n)]
    def test_ambiguity_joint_and_anchor(self):
        g=Graph(1,1,0)
        a=canonicalize_pair(self.rows(1,world=g)[0])
        self.assertEqual(a['candidate_joint_edits'],['identity','role_swap'])
        p=self.rows(1,edit='joint_swap_reattach')[0]
        self.assertEqual(canonicalize_pair(p)['candidate_joint_edits'],['joint_swap_reattach'])
        self.assertTrue(canonicalize_pair(replace(p,observed=replace(p.observed,anchor='wrong')))['unmatched'])
    def test_source_grouping(self):
        rows=self.rows(3)
        a=fit_channel(rows,'a:v1'); b=fit_channel(rows*100,'a:v1')
        np.testing.assert_allclose(a.A,b.A); np.testing.assert_allclose(a.b,b.b)
        self.assertEqual(len(a.sources),3)
    def test_guards(self):
        rows=self.rows(3)
        with self.assertRaises(ValueError): fit_channel(rows,'changed')
        with self.assertRaises(ValueError): fit_channel(rows,'a:v1',development_sources=['0'])
        with self.assertRaises(ValueError): fit_channel([replace(rows[0],split='test')],'a:v1')
        c=fit_channel(rows,'a:v1'); p=Program('claimant',lambda g:g.claimant)
        self.assertEqual(risk(c,p,{Graph(0,1,0):1},'a:v1')['status'],'unsupported')
        self.assertEqual(risk(c,p,{rows[0].reference:1},'v2')['status'],'unsupported')
        self.assertEqual(risk(c,replace(p,context='other'),{rows[0].reference:1},'a:v1')['status'],'unsupported')
    def test_unknown_and_finite_uncertainty(self):
        rows=self.rows(); g=rows[0].reference; p=Program('exception',lambda g:g.exception_event)
        c=fit_channel(rows,'a:v1')
        self.assertAlmostEqual(risk(c,p,{g:1},'a:v1')['interval'][1],1)
        c2=fit_channel(rows,'a:v1',unknown_mode='detectable_residual')
        interval=risk(c2,p,{g:1},'a:v1')['interval']
        self.assertGreater(interval[1],0); self.assertLess(interval[1],.3)
        unknown=[replace(r,observed=replace(r.observed,anchor='unmodeled')) for r in rows]
        cu=fit_channel(unknown,'a:v1',unknown_mode='detectable_residual')
        self.assertAlmostEqual(risk(cu,p,{g:1},'a:v1')['interval'][1],1)
    def test_ambiguous_rates_not_forced_zero(self):
        c=fit_channel(self.rows(world=Graph(1,1,0)),'a:v1',unknown_mode='detectable_residual')
        self.assertAlmostEqual(c.bounds([0,1,0,1])[1],1)
    def test_joint_patterns_and_replay(self):
        g=Graph(1,0,0); rows=self.rows(800)
        rows=[replace(p,observed=EDITS['joint_swap_reattach'](g)) if i%5==0 else p for i,p in enumerate(rows)]
        # XOR preserves the correlated simultaneous role/attachment change.
        p=Program('illustrative joint rule',lambda g:g.claimant ^ g.exception_event)
        replay=paired_trace_replay(rows,p,{g:1})
        self.assertEqual(replay['empirical_risk'],0)
        independent_error=2*.2*.8
        self.assertGreater(independent_error,0)
        c=fit_channel(rows,'a:v1',unknown_mode='detectable_residual')
        self.assertLess(risk(c,p,{g:1},'a:v1')['interval'][1],independent_error)
        # Empirical joint-edit plug-in and full replay are exactly equivalent here.
        losses=[float(p.evaluate(f(g))!=p.evaluate(g)) for f in EDITS.values()]
        self.assertEqual(float(np.dot([.8,0,0,.2],losses)),replay['empirical_risk'])
    def test_selection_and_small_sample_abstention(self):
        for n,expected in [(3,'unsupported'),(800,'selected')]:
            a=self.rows(n); b=self.rows(n,'reattach_exception',version='b:v1')
            cs={'a':fit_channel(a,'a:v1',unknown_mode='detectable_residual'),
                'b':fit_channel(b,'b:v1',unknown_mode='detectable_residual')}
            out=robust_select(cs,Program('exception excludes duty',lambda g:g.claimant and not g.exception_event),
                              {a[0].reference:1},{'a':'a:v1','b':'b:v1'},{'a':0,'b':0},'b',selection_mode='strict')
            self.assertEqual(out['status'],expected)
            self.assertEqual(out['plan'],'a' if n==800 else 'b')
            minimax=robust_select(cs,Program('exception excludes duty',lambda g:g.claimant and not g.exception_event),
                                  {a[0].reference:1},{'a':'a:v1','b':'b:v1'},{'a':0,'b':0},'b')
            self.assertEqual(minimax['status'],'selected')
            self.assertEqual(minimax['certified_separation'],n==800)
    def test_conditional_transfer_and_partial_rejection(self):
        rows=self.rows(128); c=fit_channel(rows,'a:v1',unknown_mode='detectable_residual')
        worlds={Graph(0,1,1):1}; p=Program('new event exception program',lambda g:g.claimant and not g.exception_event)
        self.assertEqual(risk(c,p,worlds,'a:v1')['status'],'unsupported')
        transfer=risk(c,p,worlds,'a:v1',allow_stationary_transfer=True)
        self.assertTrue(transfer['stationary_transfer_assumption'])
        self.assertEqual(paired_trace_replay(rows,p,worlds)['status'],'unsupported')
        with self.assertRaises(ValueError): fit_channel([{'reference':{'payment_year':None}}],'a:v1')
        actual=Path(__file__).parent.parent/'data_audit'/'empirical_partial_pairs.json'
        if actual.exists():
            with self.assertRaises(ValueError): fit_channel([json.loads(actual.read_text(encoding='utf-8-sig'))],'unknown')

def demo():
    rows=Checks().rows(800); g=rows[0].reference
    p=Program('illustrative duty with event-scoped exception',lambda g:g.claimant and not g.exception_event)
    channels={mode:fit_channel(rows,'a:v1',unknown_mode=mode) for mode in ['unrestricted','detectable_residual']}
    bad=Checks().rows(800,'reattach_exception',version='b:v1')
    selection=robust_select({'a':channels['detectable_residual'],
                           'b':fit_channel(bad,'b:v1',unknown_mode='detectable_residual')},
                           p,{g:1},{'a':'a:v1','b':'b:v1'},{'a':0,'b':0},'b')
    sensitivity=[]
    for n in [24,128,256]:
        sample=Checks().rows(n)
        c=fit_channel(sample,'a:v1',unknown_mode='detectable_residual')
        interval=risk(c,p,{g:1},'a:v1')['interval']
        sensitivity.append({'independent_synthetic_sources':n,'interval':interval,
                            'width':interval[1]-interval[0],
                            'replicated_views_width':risk(fit_channel(sample*3,'a:v1',unknown_mode='detectable_residual'),p,{g:1},'a:v1')['interval'][1]})
    transfer_worlds={Graph(0,1,1):1}
    return {'evidence_kind':'synthetic finite empirical sample software checks',
            'model_calls':0,'server_calls':0,'target_graphs_or_labels_for_selection':0,
            'not_evidence_of':['real model improvement','legal benchmark performance','novelty','real-data calibration'],
            'risk_modes':{m:risk(c,p,{g:1},'a:v1') for m,c in channels.items()},
            'full_paired_trace_replay':paired_trace_replay(rows,p,{g:1}),
            'conditional_selection_demo':selection,
            'source_count_sensitivity_synthetic_only':sensitivity,
            'unobserved_reference_transfer':{
                'strict_support':risk(channels['detectable_residual'],p,transfer_worlds,'a:v1'),
                'explicit_stationarity':risk(channels['detectable_residual'],p,transfer_worlds,'a:v1',True),
                'paired_replay':paired_trace_replay(rows,p,transfer_worlds),
                'interpretation':'Conditional identification calculation only; assumes same edit mixture and detectable residual behavior on unobserved reference; no observed transfer accuracy.'},
            'replay_equivalence':'On same supported worlds, empirical joint-edit replay equals full paired trace replay; no demonstrated transfer advantage.',
            'diagnostics':channels['detectable_residual'].diagnostics}

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Checks)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    output=demo(); output['checks']={'run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors)}
    Path(__file__).with_name('results.json').write_text(json.dumps(output,indent=2),encoding='utf-8')
    raise SystemExit(not result.wasSuccessful())
