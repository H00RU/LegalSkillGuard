"""Check a concrete source-guided repair plan against ordinary code slicing.

Uses only the existing d936 TRAIN acquisition, source review and actual G.
This is an offline falsifier for a proposed learner, not a successful repair.
"""
import ast
import hashlib
import json
from pathlib import Path
import sqlite3

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import source_spans
from legal_skill_guard.skill_evolution.scoped_grammar import material_public, subterms
from legal_skill_guard.skill_evolution.span_compiler import execute_json, execution_source_spans


def closure(seeds, edges):
    found = set(seeds)
    while True:
        added = set().union(*(edges.get(n,set()) for n in found)) - found
        if not added:
            return sorted(found)
        found.update(added)


def functions(code):
    nodes = {n.name:n for n in ast.parse(code).body if isinstance(n,ast.FunctionDef)}
    calls = {name:{n.func.id for n in ast.walk(fn) if isinstance(n,ast.Call)
                   and isinstance(n.func,ast.Name) and n.func.id in nodes}
             for name,fn in nodes.items()}
    callers = {name:{parent for parent,targets in calls.items() if name in targets}
               for name in nodes}
    return nodes,calls,callers


def has_head(term, head):
    return any(isinstance(t,list) and t and t[0] == head
               for t in [term,*(t for _,t in subterms(term))])


def has_truncated(value):
    if isinstance(value,dict):
        return value.get('trace_truncated',False) or any(has_truncated(v) for v in value.values())
    if isinstance(value,list):
        return any(has_truncated(v) for v in value)
    return False


def main(root):
    read=lambda p:json.loads(p.read_text())
    db=sqlite3.connect(root/'artifacts/rr_v2_preflight/research_ledger.sqlite3')
    before=list(db.execute('select * from calls order by id'))
    assert not any(r[6]=='reserved' for r in before)
    run=root/'artifacts/legal_skill_evolution_scoped_acquisition_v5_20261113'
    assert (run/'NoFactor/completed.json').exists()
    proposal=read(run/'phase2/ScopedGrammar/adapted_proposal.json')
    spec=proposal['grammar'];code=proposal['source_program'];seed=spec['seeds'][9]
    source=next(x for x in read(root/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')
                if x['key']==seed['source'])
    spans=source_spans(material_public(source['views'][0]['public']))
    saved=read(run/'phase2/ScopedGrammar/results'/(seed['source'].replace(':','_')+'.json'))
    target=next(n for n in saved['interpretation']['nodes'] if n['term'][0]=='permission')
    # This property was already acquired in the full seed and reviewed against
    # actual source37-39. It is not derived from the native target answers.
    required_head='confidentiality_bound'
    assert has_head(json.loads(seed['term_json']),required_head)
    assert not has_head(target['term'],required_head)
    declaration=next(c for c in spec['constructors'] if c['name']==required_head)
    obs={'source':source['key'],'anchor_span_ids':target['support_ids'],
         'required_support_span_ids':seed['source_span_ids'],
         'required_head':required_head,'meaning':declaration['meaning'],
         'origin':'Original acquired seed9 and the existing d936 source_semantic_review; no new source labels.'}
    trace=execute_json(code,{'source_text':source['views'][0]['public']['source_text'],
        'source_spans':execution_source_spans(spans)}, {},allow_helpers=True,trace=True)
    assert trace['result']==saved['interpretation']['source_program_output']
    condition=target['term'][3]
    byid={c['id']:c for c in trace['calls']}
    producers=[c for c in trace['calls'] if c.get('returned')==condition
               and not has_truncated(c['arguments']) and not has_truncated(c['returned'])]
    assert len(producers)==1
    actual=producers[0];lineage=[actual]
    while lineage[-1]['parent'] is not None:
        lineage.append(byid[lineage[-1]['parent']])
    dynamic_edits=sorted({c['function'] for c in lineage})
    nodes,calls,callers=functions(code)
    # An ordinary slicer gets the same already-acquired semantic observation.
    # It may locate that constructor literal and its callers without our trace.
    literal_producers={name for name,fn in nodes.items()
        if any(isinstance(n,ast.Constant) and n.value==required_head for n in ast.walk(fn))}
    static_edits=closure(literal_producers,callers)
    def payload(edits):
        deps=closure(edits,calls)
        return {'editable_functions':edits,'dependency_code':'\n\n'.join(
            ast.get_source_segment(code,nodes[n]) for n in deps),
            'source_observation':obs,'source_spans':[spans[i] for i in seed['source_span_ids']],
            'acquired_semantics':spec['constructors']}
    dynamic,ordinary=payload(dynamic_edits),payload(static_edits)
    assert dynamic==ordinary
    after=list(db.execute('select * from calls order by id'));assert before==after
    result={'new_physical_requests':0,'native_labels_loaded':False,
        'observation':obs,'actual_complete_producer_call':actual,
        'actual_call_lineage':[{k:c[k] for k in ('id','parent','function')} for c in lineage],
        'trace_globally_truncated':trace['trace_truncated'],
        'local_producer_evidence_complete':True,
        'raw_source_output_replay_identical':True,
        'dynamic_editable_functions':dynamic_edits,'ordinary_editable_functions':static_edits,
        'dependency_functions':closure(dynamic_edits,calls),
        'learned_program_functions':len(nodes),'repair_payloads_identical':True,
        'payload_characters_each':len(json.dumps(dynamic,ensure_ascii=False)),
        'no_new_semantics_acquired':True,'no_repaired_G_or_new_reuse_claimed':True,
        'conclusion':'On this actual source omission, the proposed trace/source-local repair input is identical to an ordinary literal/call-graph slice supplied the same source observation. This does not establish a general equivalence, but gives no basis for extra model calls on this proposed difference.',
        'decision':'Do not launch another local-versus-full G repair pilot on d936 or count it as a contribution. Preserve the source constraint and actual trace as reusable data.',
        'goal_complete':False,'ledger_rows_unchanged':len(before),
        'ledger_sha256':hashlib.sha256(json.dumps(before,ensure_ascii=False,separators=(',',':')).encode()).hexdigest(),
        'source_snapshot':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in [
            'legal_skill_guard/skill_evolution/span_compiler.py',
            str(Path(__file__).resolve().relative_to(root))]}}
    out=root/'reports/legal_skill_evolution_run_20261111/source_compiler_followup'
    immutable_json(out/'local_plan_audit.json',result)
    immutable_json(out/'actual_d936_trace.json',trace)
    print(json.dumps({k:v for k,v in result.items() if k not in (
        'actual_complete_producer_call','observation','source_snapshot')},ensure_ascii=False))


if __name__=='__main__':
    main(Path(__file__).resolve().parents[1])
