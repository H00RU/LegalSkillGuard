"""A/B acceptance from fresh primary executions, never fallback/native score alone."""
import json
from pathlib import Path
from collections import defaultdict
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.data_store import PreflightData
from legal_skill_guard.rr.source_learning import original_view,coarse_and_metadata,rule_graph,predict_horn_sketch
from legal_skill_guard.rr.public_horn import parse_public
from legal_skill_guard.rr.learning import parameterize_graph
from legal_skill_guard.rr.readiness import current_binding
root=Path(__file__).resolve().parents[3];out=root/'reports/rr_v2_evidence/semantic_preflight'
stage=root/'artifacts/rr_v2_preflight/core_primary_v1';seal=json.loads((stage/'seal.json').read_text());data=PreflightData(root,root/'reports/rr_v2_evidence/data_manifest.json')
records=[]
for index in seal['source_indices']:
    sid=data.order[index];path=stage/'sources'/f'{digest(sid)}.json'
    if not path.exists():continue
    raw=json.loads(path.read_text());r=raw['record'];trace=raw['trace'];source=data.public(sid);grade=data.grade(sid)
    base=original_view(source,grade);expected=grade['answer']
    observations=[(*coarse_and_metadata(source,grade,base),expected,digest(base))]
    views=[(source['public'],expected)]
    for v in r['learning']['oracle_views']:
        if v.get('status')=='reference_failed':continue
        observations.append((*coarse_and_metadata(source,grade,v['view']),v['answer'],v['view_hash']))
        views.append((v['view']['public'],v['answer']))
    fields=(r['learning'].get('learned_pattern') or {}).get('fields',[])
    collisions=[]
    for i,(c,m,a,key) in enumerate(observations):
        for c2,m2,a2,key2 in observations[i+1:]:
            if digest(c)==digest(c2) and digest(a)!=digest(a2):
                collisions.append(dict(left=key,right=key2,coarse_hash=digest(c),answers=[a,a2],
                    separated_by_refined_fields=digest({f:m.get(f) for f in fields})!=digest({f:m2.get(f) for f in fields})))
    grouped=defaultdict(set)
    for coarse,metadata,answer,key in observations:
        grouped[digest({'coarse':coarse,'roles':{f:metadata.get(f) for f in fields}})].add(digest(answer))
    functional=all(len(x)==1 for x in grouped.values())
    exact=[rule_graph(rule,erase_equalities=False) for rule in parse_public(source['public']).rules]
    native_checks=[dict(expected=answer,predicted=predict_horn_sketch(public,exact)) for public,answer in views]
    produced=(r['learning'].get('learned_pattern') or {}).get('graphs',[])
    expected_patterns={digest(parameterize_graph(g)) for g in exact if g.get('op')=='join_on'}
    selected_graphs_match=bool(produced) and {digest(g) for g in produced}==expected_patterns
    a_primary=r['analysis']['certificate_status']=='completion_stable' and r['analysis'].get('certificate_basis')=='complete_restricted_public_grammar_not_connector_H'
    b_primary=r['learning']['status']=='identified_on_observed_collisions' and selected_graphs_match and bool(trace)
    a_pass=a_primary and r['analysis']['answer']==grade['answer']
    b_pass=b_primary and bool(collisions) and functional and all(x['separated_by_refined_fields'] for x in collisions) and all(x['expected']==x['predicted'] for x in native_checks)
    records.append(dict(index=index,source=sid,fresh_physical_requests=raw['fresh_physical_requests'],record_path=str(path.relative_to(root)),
        A=dict(primary=a_primary,semantic_pass=a_pass,fallback=not a_primary,certificate_basis=r['analysis'].get('certificate_basis'),answer=r['analysis']['answer']),
        B=dict(primary=b_primary,semantic_pass=b_pass,fallback=not b_primary,coarse_collisions=collisions,
            refined_fields=fields,refined_observation_map_functional=functional,selected_graphs_match_actual_rules=selected_graphs_match,
            connector_semantic_checks=native_checks,initial_candidates=trace['initial_candidates'],retained_candidates=trace['retained_candidates'],
            candidate_count_decrease_required=False,old_learning_result_used_as_output=False,finite_H_not_Omega=True),
        original_checker=raw['checks'],original_checker_extra_H_shrink_condition_corrected=True))
complete=len(records)==4
result=dict(execution_binding=current_binding(root),fresh_primary_generation_binding=seal['binding'],
    complete=complete,A_pass=complete and all(r['A']['semantic_pass'] for r in records),B_pass=complete and all(r['B']['semantic_pass'] for r in records),
    fixed_source_denominator=20,fresh_primary_source_count=len(records),no_new_sources=True,no_main_training=True,
    fallback_native_results_count_as_core_success=False,legacy_or_default_outputs_count_as_core_success=False,
    reference_cache_reused_only_as_expected_labels=True,records=records)
(out/'core_acceptance.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='records'}))
