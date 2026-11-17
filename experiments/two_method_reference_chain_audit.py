"""Bounded offline M1 audit: all177 references and original D/C paid outputs.

No executor/teacher client is created. Pure-reference outputs receive no grade.
Predictions are saved before mechanically opening D/C TRAIN native grading.
"""
from collections import Counter, defaultdict
import json
from pathlib import Path
from types import SimpleNamespace

from experiments.two_method_annotate import inputs
from experiments.two_method_graph_corpus import BASE, ROOT, read, sha
from experiments.two_method_normalize_graph_reads import physical_response
from legal_skill_guard.paired_interfaces.formal_actors import InterfaceActor
from legal_skill_guard.paired_interfaces.production_decode import decode_response
from legal_skill_guard.paired_interfaces.reference_wire import reference_wire
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest

REGISTRY = BASE / 'formal_reference_registry_v1/428168f0c9a92d5ebda0a435d2919647380adb262207466bcd3debae9a8a1fd6'
PREFLIGHT = BASE / 'formal_read_preflight_v1/6e22e5920c3df1aac061f9bd159788e44b30c9bd570fc9f740c4c0894a56058f'
CORPUS = BASE / 'observed_abstention_channel_v3/8ab84a2860a622bcecbd94b2b340fbc3d38b5e22c420f0c8dfa8eb9b104cd44d/snapshots/ca524c1fe10e6024e17a5a693eebcf43e64eede1a5dd5eb863417eb5224d5385/corpus.json'


def run():
    manifest = read(REGISTRY / 'manifest.json')
    roles = {r['source']: r['role'] for r in read(REGISTRY / 'roles.json')}
    public_path = ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
    public = {s['key']: s for s in read(public_path)}
    assert {key: digest(s) for key, s in public.items()} == manifest['source_public_sha256']
    sources = [str(Path(__file__).relative_to(ROOT)), 'experiments/two_method_annotate.py',
        'experiments/two_method_normalize_graph_reads.py',
        *['legal_skill_guard/skill_evolution/'+name+'.py' for name in ('native','objects','grade_worker','span_compiler','sara_statute_kernel','partial_native_proof')],
        *[str(p.relative_to(ROOT)) for p in sorted((ROOT/'legal_skill_guard/paired_interfaces').glob('*.py'))]]
    bindings = {name: sha(ROOT/name) for name in sources}
    original_inventory=read(CORPUS)['inventory']
    protocol = {'name': 'same-production-reference-chain-audit-v1', 'source_sha256': bindings,
        'registry_sha256': sha(REGISTRY/'manifest.json'), 'corpus_sha256': sha(CORPUS),
        'original_schema_reference_sha256': {r['audit_path']:sha(ROOT/r['audit_path'])
            for r in original_inventory if r['read_settled']},
        'TRAIN_public_sha256': sha(public_path), 'reference_views': 177,
        'reference_only_native_grades_allowed': False, 'new_model_requests': 0,
        'no_formal_training_or_DEV_TEST': True, 'reference_fixture_is_not_model_performance': True}
    out = BASE/'revision_20261117/M1_reference_chain'/digest(protocol)
    immutable_json(out/'protocol.json', protocol)
    for name,expected in bindings.items():
        target=out/'source_snapshot'/name;target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists():target.write_bytes((ROOT/name).read_bytes())
        assert sha(target)==expected
    actor = InterfaceActor(SimpleNamespace(config=manifest['executor']), out/'unused_actor',
        plan_assets=read(PREFLIGHT/'plan_assets.json'), source_inputs=inputs, pipeline_binding=bindings)
    views = {(s['key'], v['view']): v for s in public.values() for v in actor.views(s)}
    predictions, reference_index = [], {}
    for i, entry in enumerate(manifest['reviews']):
        assert sha(ROOT/entry['path']) == entry['sha256']
        card = read(ROOT/entry['path']); source = public[entry['source']]
        view = views[entry['source'], entry['view']]
        assert roles[entry['source']] == card['role'] != 'structure_evaluation'
        assert digest(view['source_units']) == card['source_units_sha256']
        for plan in view['plans']:
            row = {'source': entry['source'], 'view': entry['view'], 'dataset': source['dataset'],
                'role': card['role'], 'plan': plan['name'], 'kind': 'reference_wire_probe',
                'reference_sha256': entry['sha256'], 'model_performance': False}
            try:
                wire = reference_wire(source['dataset'], plan, card, view['source_units'])
                row['wire_sha256'] = digest(wire)
                row.update(decode_response(source, view, plan, {'content': json.dumps(wire), 'finish_reason': 'stop'}))
            except (ValueError, KeyError, TypeError) as error:
                row.update(fixture_error=type(error).__name__+': '+str(error), native={})
            immutable_json(out/'predictions'/(digest([row['kind'],entry['source'],entry['view'],plan['name']])+'.json'), row)
            predictions.append(row); reference_index[entry['source'], entry['view'],plan['name']] = row
        if (i+1)%30 == 0:
            print(json.dumps({'reference_views_finished': i+1}), flush=True)
    # Reuse precisely the original paid D/C response, original read ABI/schema.
    lock = read(BASE/'pilot_lock.json')
    plans = {(d,p['name']):p for d, ps in lock['plans'].items() for p in ps}
    for item in original_inventory:
        if not item['read_settled']:
            continue
        source, view = public[item['source']], views[item['source'],item['view']]
        actual = read(ROOT/item['read_path']); response, physical = physical_response(actual, item['source'])
        request = read((ROOT/item['read_path']).with_name('task.json'))
        assert request['source'] == item['source'] and request['opaque_source_view'] == item['view']
        plan = (next(p for p in view['plans'] if p['name']==item['plan'])
                if item['dataset']=='RuleArena_Airline' else plans[item['dataset'],item['plan']])
        assert digest(plan['schema']) == digest(request['output_schema'])
        # The old generic OE ABI needs its original reviewed graph. A new
        # program-port card is a different interface, not a same-ABI oracle.
        original_card=read(ROOT/item['audit_path'])
        original_ref={'source':item['source'],'view':item['view'],'dataset':item['dataset'],
            'role':item['role'],'plan':item['plan'],'kind':'original_schema_reference_probe',
            'same_original_request_schema_sha256':digest(request['output_schema']),
            'reference_sha256':sha(ROOT/item['audit_path']),'model_performance':False}
        try:
            wire=reference_wire(source['dataset'],plan,original_card,view['source_units'])
            original_ref.update(decode_response(source,view,plan,{'content':json.dumps(wire),'finish_reason':'stop'}))
        except (ValueError,KeyError,TypeError) as error:
            original_ref.update(fixture_error=type(error).__name__+': '+str(error),native={})
        immutable_json(out/'predictions'/(digest([original_ref['kind'],item['source'],item['view'],item['plan']])+'.json'),original_ref)
        predictions.append(original_ref)
        row = {k:item[k] for k in ('source','view','dataset','role','plan')}
        row.update(kind='original_paid_response_replay', **physical,
                   new_independent_trial=False, model_performance=True)
        row.update(decode_response(source,view,plan,response))
        reference = reference_index.get((item['source'],item['view'],item['plan']))
        row['reference_probe_available'] = reference is not None
        row['reference_native_handled_tasks'] = sum(v['handled'] for v in reference['native'].values()) if reference else None
        immutable_json(out/'predictions'/(digest([row['kind'],row['source'],row['view'],row['plan']])+'.json'), row)
        predictions.append(row)
    # Only after every prediction; expose only already authorized TRAIN D/C.
    immutable_json(out/'prediction_seal.json', {'prediction_count':len(predictions),
        'identities_sha256':digest([(p['kind'],p['source'],p['view'],p['plan']) for p in predictions]),
        'heldout_or_reference_only_grading_opened':False})
    eligible = {p['source'] for p in predictions if p['role'] in ('development','calibration')}
    all_train_grading = read(public_path.with_name('grading.json'))
    grading = {key:all_train_grading[key] for key in eligible}
    del all_train_grading
    old_predictions = BASE/'pilot_evaluation_v1/3a847ef33221884de63f234bc6e2ce78f1e19f2265cefc58fa4463e079f8a650/predictions'
    prior={}
    for path in old_predictions.glob('*.json'):
        p=read(path)
        if p['role'] in ('development','calibration'):
            prior[p['source'],p['opaque_view'],p['plan']]=p
    parity=[]
    for row in predictions:
        if row['kind']!='original_paid_response_replay':continue
        old=prior[row['source'],row['view'],row['plan']]
        parity.append({'source':row['source'],'view':row['view'],'plan':row['plan'],
            'handled_and_native_answers_unchanged':all((v['handled'],v.get('answer'))==
                (old['native'][k]['handled'],old['native'][k].get('answer')) for k,v in row['native'].items()),
            'original_physical_call_id_preserved':row['physical_call_id']==old['physical_call_id']})
    immutable_json(out/'original_output_parity.json',parity)
    scores, stats = [], defaultdict(Counter)
    for row in predictions:
        counts = stats[row['kind'],row['dataset']]
        counts['probes'] += 1; counts['fixture_errors'] += bool(row.get('fixture_error'))
        counts['decode_refusals'] += bool(row.get('production_errors'))
        for task, result in row['native'].items():
            counts['native_tasks'] += 1; counts['handled'] += result['handled']
            if not result['handled']:
                counts['reason: '+str(result.get('reason'))] += 1
            if row['source'] not in eligible:
                continue
            view = next(v for v in public[row['source']]['views'] if v['id']==task)
            grade = (grade_view(row['dataset'],view,grading[row['source']][task],result['answer'],
                result.get('evidence_sentence_ids',[])) if result['handled'] else {'grade':0.})
            scores.append({k:row[k] for k in ('kind','source','view','role','dataset','plan')} |
                {'native_task':task, 'handled':result['handled'], 'native_metrics':grade})
            counts['graded_D_C_tasks'] += 1
            counts['positive_D_C_grade'] += grade['grade'] > 0
    immutable_json(out/'D_C_native_scores.json',scores)
    score_index={(s['kind'],s['source'],s['view'],s['plan'],s['native_task']):s for s in scores}
    same_abi=Counter()
    by_identity={(r['kind'],r['source'],r['view'],r['plan']):r for r in predictions}
    for row in predictions:
        if row['kind']!='original_paid_response_replay':continue
        ref=by_identity['original_schema_reference_probe',row['source'],row['view'],row['plan']]
        for task,result in row['native'].items():
            reference=ref['native'].get(task)
            if reference is None or ref.get('production_errors'):
                category='reference_ABI_or_fixture_rejected'
            elif not reference['handled']:
                category='reference_scope_or_fixed_F_coverage_gap'
            else:
                ref_score=score_index[ref['kind'],row['source'],row['view'],row['plan'],task]['native_metrics']['grade']
                actual_score=score_index[row['kind'],row['source'],row['view'],row['plan'],task]['native_metrics']['grade']
                if ref_score<1:category='reference_executable_but_not_native_correct'
                elif not result['handled']:category='reference_correct_actual_reader_abstention'
                elif actual_score<1:category='reference_correct_actual_semantic_error'
                else:category='both_native_correct'
            same_abi[row['dataset']+':'+category]+=1
    summary = {'artifact_root':str(out.relative_to(ROOT)), 'reference_views':len(manifest['reviews']),
        'new_model_requests':0, 'new_independent_trials':0, 'all_predictions_saved_before_D_C_grading':True,
        'reference_only_grading_opened':False, 'DEV_TEST_opened':False,
        'original_paid_outputs_replayed':len(parity),
        'changed_original_native_outputs':sum(not p['handled_and_native_answers_unchanged'] for p in parity),
        'changed_physical_call_bindings':sum(not p['original_physical_call_id_preserved'] for p in parity),
        'same_original_ABI_native_task_plan_classification':dict(same_abi),
        'counts':[{'kind':k,'dataset':d,**dict(v)} for (k,d),v in sorted(stats.items())],
        'fixture_error_reasons':dict(Counter(p['fixture_error'] for p in predictions if p.get('fixture_error'))),
        'goal_complete':False}
    for name,value in bindings.items():
        assert sha(ROOT/name)==value, name
    for entry in manifest['reviews']:
        assert sha(ROOT/entry['path'])==entry['sha256']
    immutable_json(out/'summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False),flush=True)
    return out,summary


if __name__ == '__main__':
    run()
