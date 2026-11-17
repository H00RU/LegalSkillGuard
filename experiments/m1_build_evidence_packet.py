"""Build a bounded, credential-free M1 publication from existing TRAIN records.

This builder needs the preserved local assets; the published replay entry needs
only the resulting packet and its enumerated dependency closure. No inference.
"""
import ast
import hashlib
import gzip
import importlib.metadata
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace

from experiments.two_method_annotate import inputs
from experiments.two_method_normalize_graph_reads import physical_response
from experiments.two_method_reference_chain_audit import BASE, ROOT, CORPUS, PREFLIGHT
from legal_skill_guard.paired_interfaces.formal_actors import InterfaceActor
from legal_skill_guard.paired_interfaces.production_decode import decode_response
from legal_skill_guard.paired_interfaces.reference_wire import reference_wire
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest

PACKET = ROOT / 'reports/two_method_followthrough_20261116/M1_evidence_20261117'


def read(p): return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    body = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)+'\n').encode()
    if p.exists() and p.read_bytes() != body:
        raise ValueError('Existing packet bytes differ: '+str(p))
    p.write_bytes(gzip.compress(body, mtime=0) if p.suffix == '.gz' else body)


def dependencies():
    pending = ['legal_skill_guard.paired_interfaces.production_decode',
        'legal_skill_guard.paired_interfaces.reference_wire',
        'legal_skill_guard.skill_evolution.grade_worker',
        'legal_skill_guard.paired_interfaces.consumer_worker',
        'legal_skill_guard.paired_interfaces.partial_consumer_worker',
        'legal_skill_guard.paired_interfaces.program_residual',
        'legal_skill_guard.paired_interfaces.source_context']
    seen = set()
    while pending:
        module = pending.pop()
        path = Path(module.replace('.', '/')+'.py')
        if not (ROOT/path).exists(): path = Path(module.replace('.', '/'))/'__init__.py'
        if not (ROOT/path).exists() or str(path) in seen: continue
        seen.add(str(path))
        base = module if path.name == '__init__.py' else module.rsplit('.', 1)[0]
        for node in ast.walk(ast.parse((ROOT/path).read_text())):
            if isinstance(node, ast.Import): names = [n.name for n in node.names]
            elif isinstance(node, ast.ImportFrom):
                prefix = '.'.join(base.split('.')[:len(base.split('.'))-node.level+1]) if node.level else ''
                name = '.'.join(s for s in (prefix, node.module) if s)
                names = [name]+[name+'.'+n.name for n in node.names]
            else: continue
            pending.extend(n for n in names if n.startswith(('legal_skill_guard.', 'experiments.')))
    return seen


def build():
    corpus = read(CORPUS)['inventory']
    inventory = [r for r in corpus if r['read_settled']]
    # Selection uses dataset/source IDs only, not scores or successful outputs.
    selected = {min(r['source'] for r in inventory if r['dataset'] == d)
                for d in {r['dataset'] for r in inventory}}
    # Include the already identified input-gap case explicitly, with no relabeling.
    selected.add('MAUD:2ae909b923008fa9f293069a959276b3f7c3c61e355e75092dd1ea6d14eb4db8')
    public = {s['key']: s for s in read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
    lock = read(BASE/'pilot_lock.json')
    actor = InterfaceActor(SimpleNamespace(config=lock['executor']), PACKET/'unused',
        plan_assets=read(PREFLIGHT/'plan_assets.json'), source_inputs=inputs, pipeline_binding={'packet': 'v1'})
    views = {(s, v['view']): v for s in selected for v in actor.views(public[s])}
    # Mechanical D/C-only annotation extraction; heldout/reference-only keys do not enter.
    all_grades = read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
    grades = {key: all_grades[key] for key in selected}; del all_grades
    cases, calls, ledger_index = [], {}, []
    db = sqlite3.connect('file:'+str(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3')+'?mode=ro', uri=True)
    for item in inventory:
        if item['source'] not in selected: continue
        first_view = min(r['view'] for r in inventory if r['source'] == item['source'])
        is_context_gap = item['source'].startswith('MAUD:2ae909')
        if item['view'] != first_view and not is_context_gap: continue
        assert item['role'] in ('development', 'calibration')
        source, view = public[item['source']], views[item['source'], item['view']]
        actual = read(ROOT/item['read_path']); response, physical = physical_response(actual, item['source'])
        plan = (next(p for p in view['plans'] if p['name'] == item['plan'])
                if item['dataset'] == 'RuleArena_Airline' else
                next(p for p in lock['plans'][item['dataset']] if p['name'] == item['plan']))
        card = read(ROOT/item['audit_path'])
        wire = reference_wire(source['dataset'], plan, card, view['source_units'])
        result = {'real': decode_response(source, view, plan, response),
                  'reference': decode_response(source, view, plan, {'content':json.dumps(wire),'finish_reason':'stop'})}
        native_views = {v['id']: v for v in source['views']}
        expected = {name: {task: grade_view(source['dataset'], native_views[task], grades[source['key']][task],
                v['answer'], v['evidence_sentence_ids']) if v['handled'] else {'grade':0.0,'unresolved_or_failed':True}
                for task, v in r['native'].items()} for name, r in result.items()}
        cases.append({'identity': [item['source'],item['view'],item['plan']], 'role':item['role'],
            'source_public':source, 'actor_view':view, 'native_views':native_views, 'plan_asset':plan,
            'source_review':card, 'review_original_path':item['audit_path'],
            'review_sha256':sha(ROOT/item['audit_path']), 'response':response,
            'physical_provenance':physical, 'D_C_annotation':grades[source['key']],
            'expected_current':result, 'expected_grades':expected,
            'before_original_native_outputs':actual['native_consumer_outputs'],
            'before_original_decode_errors':actual['errors']})
        identity = actual['physical_call_id']; call = (ROOT/physical['response_path']).parent
        calls[identity] = {name:read(call/name) for name in ('request.json','wire_request.json','wire_response.json','result.json')}
        row = db.execute('select id,role,purpose,source,request_hash,status,reserved_at,result from calls where id=?',(identity,)).fetchone()
        assert row[5] == 'completed'
        ledger_index.append(dict(zip(('id','role','purpose','source','request_hash','status','reserved_at','result_sha256'),
                                     (*row[:7],hashlib.sha256(row[7].encode()).hexdigest()))))
    db.close()
    save(PACKET/'chain_cases.json.gz', cases); save(PACKET/'key_raw_calls.json.gz', calls)
    save(PACKET/'ledger_index.json', {'physical_rows':ledger_index,
        'continuous_ledger_path':'artifacts/rr_v2_preflight/research_ledger.sqlite3',
        'ledger_count_at_export':12425, 'reserved_at_export':0, 'new_calls':0})
    pilot = BASE/'pilot_evaluation_v1/3a847ef33221884de63f234bc6e2ce78f1e19f2265cefc58fa4463e079f8a650'
    for src, dest in [('all_candidate_native_scores.json','pilot_native_scores.json'),
                      ('report.json','pilot_report.json'),('selection_freeze.json','selection_freeze.json')]:
        save(PACKET/dest, read(pilot/src))
    reference = BASE/'revision_20261117/M1_reference_chain/d76c8ff0c02caf9b1e7d0f00c57ec21cacb526fed034a1e2d45a47a065f13eeb'
    partial = BASE/'partial_F_revision_20261117/1ef7db9bc2bf9436d44a1e6e768d8c95d0a3a087a84b613b3b1bcb02f714fa2c'
    save(PACKET/'existing_offline_results.json', {'reference_chain_summary':read(reference/'summary.json'),
        'original_output_parity':read(reference/'original_output_parity.json'),
        'partial_F_summary':read(partial/'summary.json'),
        'these_are_saved_checks_not_new_model_trials':True})
    files = dependencies() | {'experiments/m1_replay_evidence.py'}
    files.add('artifacts/two_method_followthrough_20261116/pilot_lock.json')
    files.update(m['asset'] for m in lock['modules'].values())
    # Preserve the exact hashed F library without publishing other cache trees.
    # Its full bytes are needed by the existing immutable library binding.
    library = 'artifacts/legal_skill_evolution_20261111/formal_v5/Full/B8.json'
    materialized = {library: {'gzip': str((PACKET/'frozen_F_library.json.gz').relative_to(ROOT)),
                              'sha256': sha(ROOT/library)}}
    (PACKET/'frozen_F_library.json.gz').write_bytes(gzip.compress((ROOT/library).read_bytes(), mtime=0))
    files.remove(library)
    kernel = read(ROOT/lock['modules']['SARA_v2_Binary']['asset'])[0]['kernel']
    files.update(str(Path(kernel['statute_directory'])/n) for n in kernel['statute_sha256'])
    files.add('history/rr_v2_20261106/data/cache/rr_v2/RuleArena/airline/gen_questions.py')
    # Evaluator imports these original public source modules; no dataset/cache cases.
    upstream = ROOT/'data/cache/openexempt/servantez-OpenExempt-ec6fa25'
    files.update(str(p.relative_to(ROOT)) for p in [upstream/'evaluator.py',*(upstream/'source').glob('*.py')])
    files.update(str(p.relative_to(ROOT)) for p in upstream.glob('*LICENSE*'))
    for package in ('jsonschema','numpy','scipy','regex','tiktoken','rapidfuzz','langchain-core','pydantic'):
        importlib.metadata.version(package)
    requirements = '\n'.join(p+'=='+importlib.metadata.version(p) for p in
        ('jsonschema','numpy','scipy','regex','tiktoken','rapidfuzz','langchain-core','pydantic'))+'\n'
    (PACKET/'requirements.txt').write_text(requirements)
    files.update(str(p.relative_to(ROOT)) for p in PACKET.iterdir() if p.is_file() and p.name != 'manifest.json')
    manifest = {'name':'M1-minimum-source-and-TRAIN-evidence-v1', 'source_roles':'TRAIN D/C only for replay',
        'key_sources':sorted(selected), 'key_response_count':len(cases),
        'selection_rule':'first source ID per dataset, plus previously identified MAUD input-gap case',
        'pilot_scores_include_previously_exposed_internal_evaluation':True,
        'no_DEV_TEST_inputs_or_labels':True, 'new_model_calls':0, 'Goal_complete':False,
        'credential_policy':'no config/env/key files or HTTP authorization headers; original model bodies retained',
        'materialized_assets':materialized,
        'files_sha256':{p:sha(ROOT/p) for p in sorted(files)}}
    save(PACKET/'manifest.json', manifest)
    print(json.dumps({'files':len(files)+1, 'bytes':sum((ROOT/p).stat().st_size for p in files),
                      'real_key_responses':len(cases), 'sources':len(selected)},ensure_ascii=False))


if __name__ == '__main__': build()
