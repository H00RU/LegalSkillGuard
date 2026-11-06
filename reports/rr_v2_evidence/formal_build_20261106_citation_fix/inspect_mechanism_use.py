"""Inspect paid TRAIN records only; no generation, oracle, prediction or tuning.

Evidence reporting is unbound. The running scientific implementation stays frozen.
Prompt exposure, independently relearning a pattern and executing its structure
are deliberately different observations; none proves a causal transfer benefit.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import json

from legal_skill_guard.rr.coverage import SourceLedger, digest
from legal_skill_guard.rr.engine import source_text, wire_messages
from legal_skill_guard.rr.learning import SkillLibrary, parameterize_graph

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT/'artifacts/rr_v2_formal_build_20261106'
RUN = BASE/'run_citation_fix'
OUT = ROOT/'reports/rr_v2_evidence/formal_build_20261106_citation_fix'


def read(path):
    return json.loads(Path(path).read_text())


def inspect(summary):
    """Use the already-audited committed prefix, never a later partial source."""
    cfg = read(ROOT/'configs/rr_v2_preflight.json')
    order = read(ROOT/cfg['source_manifest'])['formal_train_order'][:summary['complete_sources']]
    public = {s['key']:s for s in read(ROOT/'data/packets/rr_v2/public_train.json')['sources']}
    library = SkillLibrary(stage='formal_train')
    rows, learned, prompt_failures = [], {}, []
    traces = read(OUT/'mechanism_reexecution.json') if (OUT/'mechanism_reexecution.json').exists() else {}
    trace_by_source = {t['source']:t['checks'] for t in traces.get('traces', [])} if all(
        traces.get(k)==summary[k] for k in ('binding','processing_binding','processing_revision')) else {}
    for index, sid in enumerate(order):
        record = read(RUN/'sources'/(digest(sid)+'.json'))
        source = public[sid]
        prior = [p['pattern'] for p in library.patterns]
        prior_graphs = {digest(g) for p in prior for g in p['graphs']}
        calls, actions = [], []
        for call in record['calls']:
            step = call['step']
            cid = record['run_id']+':'+sid+':'+str(step)
            directory = RUN/'calls'/digest(cid)
            request = read(directory/'request.json')
            payload = request['payload']
            messages = payload['messages']
            schema = payload['response_format']['json_schema']['schema']
            program_schema = schema['properties']['program']
            variants = program_schema['anyOf'] if 'anyOf' in program_schema else [program_schema]
            wire_kinds = sorted({kind for v in variants for kind in v['properties']['kind']['enum']})
            suffix = '\nCurrent learned role constraints: '
            supplied = json.loads(messages[0]['content'].rsplit(suffix, 1)[1])
            if supplied != prior:
                prompt_failures.append(cid)
            initial_full = messages[1]['content'] == wire_messages(source)[1]['content'] if step == 0 else None
            analysis = call['analysis']
            proposal = analysis.get('proposal', {})
            program = proposal.get('program', {})
            candidates = program.get('body', {}).get('candidates', []) if program.get('kind') == 'connector' else []
            def matches(graph):
                try:
                    return digest(parameterize_graph(graph)) in prior_graphs
                except (ValueError, TypeError, KeyError):
                    return False
            matching = sum(matches(g) for g in candidates)
            states = analysis.get('execution_states', [])
            executed_matching = matching if matching and len(states) == len(candidates) else 0
            calls.append({'step':step, 'request_hash':call['request_hash'],
                'input_tokens':request['tokenization']['count'],
                'wire_program_kinds':wire_kinds,
                'wire_interfaces_max_items':schema['properties']['interfaces'].get('maxItems'),
                'initial_full_public_input_exact':initial_full,
                'SARA_exact_query_in_wire':json.dumps(source['public']['query'], ensure_ascii=False) in messages[1]['content'] if source['dataset'] == 'SARA_v2_Binary' else None,
                'supplied_pattern_count':len(supplied), 'supplied_patterns_match_prior_library':supplied == prior,
                'program_kind':program.get('kind'), 'program_status':analysis['program_status'],
                'interface_proposals':len(proposal.get('interfaces', [])),
                'prior_graph_matching_interface_proposals':sum(matches(i['graph']) for i in proposal.get('interfaces', [])),
                'prior_graph_matching_program_candidates':matching,
                'prior_graph_structure_executed_candidates':executed_matching,
                'execution_state_records':len(states),
                'fixed_public_grammar_used':str(analysis.get('certificate_basis', '')).endswith('_not_H') or
                    analysis.get('certificate_basis') == 'complete_restricted_public_grammar_not_connector_H',
                'completion_assessment_status':analysis.get('completion_assessment', {}).get('status'),
                'unknown_scope_units':len(analysis['completion_assessment']['unknown_scope']) if 'completion_assessment' in analysis else None,
                'complete_observation_units':len(analysis['completion_assessment']['complete_observations']) if 'completion_assessment' in analysis else None})
            if step:
                action = record['translation_actions'][step-1]
                previous = record['calls'][step-1]['analysis']
                # Compare source text, not regenerated diagnostics/binding JSON:
                # archived key ordering is not the original wire byte ordering.
                source_ledger = SourceLedger.from_text(source_text(source))
                selected = set(action['context_closure'])
                numbered = '\n'.join(f'[{c.id}] {source_ledger.text[c.start:c.end]}'
                    for c in source_ledger.clauses if c.id in selected)
                expected_source = 'Public benchmark: '+source['dataset']+'\n'+numbered
                wire = read(directory/'wire_request.json')
                cost = action.get('request_cost', {})
                actions.append({'step':step, 'residual_before':len(previous['residual_units']),
                    'selected_units':len(action['selected']), 'context_units':len(action['context_closure']),
                    'selection_basis':action['selection_basis'],
                    'batch_plan_status':(action.get('batch_plan') or {}).get('status'),
                    'joint_separation_complete':action['joint_separation_complete'],
                    'selected_source_text_matches_wire':messages[1]['content'].startswith(expected_source),
                    'input_tokens':cost.get('input_tokens'),
                    'token_cost_matches_wire':cost.get('input_tokens') == request['tokenization']['count'],
                    'body_hash_matches_wire':cost.get('wire_body_sha256') == wire['body_sha256']})
        learning = record['learning']
        pattern = learning.get('learned_pattern')
        pattern_hash = None
        independent_reconfirmation = False
        if pattern:
            before = {p['pattern_hash'] for p in library.patterns}
            pattern_hash = library.add(pattern, source=sid)
            independent_reconfirmation = pattern_hash in before
            learned[pattern_hash] = next(p for p in library.patterns if p['pattern_hash'] == pattern_hash)
        checks = trace_by_source.get(sid)
        rows.append({'index':index, 'source':sid, 'dataset':source['dataset'],
            'public_source_units':len(SourceLedger.from_text(source_text(source)).clauses),
            'calls':calls, 'A_actions':actions,
            'A_final_certificate':record['analysis']['certificate_status'],
            'A_final_basis':record['analysis'].get('certificate_basis'),
            'A_final_unknown_scope_units':calls[-1]['unknown_scope_units'],
            'A_native_fallback':record['analysis'].get('fallback_used', False),
            'TRAIN_reference_match':record['score']['task_correct'],
            'B_learning_status':learning['status'],
            'B_candidate_input_status':learning.get('connector_synthesis_status'),
            'B_model_typed_candidates_generated':learning.get('connector_candidates_generated'),
            'B_builtin_Horn_candidate_path':source['dataset'] == 'ProofWriter_OWA_depth5',
            'B_pattern_hash':pattern_hash,
            'B_independent_reconfirmation_of_prior_pattern':independent_reconfirmation,
            'B_collisions':len(learning.get('refinement', {}).get('collisions', [])),
            'B_learning_semantic_checks_reexecuted':sum(c['semantic_observations'] for c in checks) if checks is not None else None,
            'B_learning_semantic_matches_reexecuted':sum(c['semantic_observations_matching'] for c in checks) if checks is not None else None})
    all_calls = [c for r in rows for c in r['calls']]
    all_actions = [a for r in rows for a in r['A_actions']]
    by_dataset = []
    for dataset in dict.fromkeys(r['dataset'] for r in rows):
        group = [r for r in rows if r['dataset'] == dataset]
        by_dataset.append({'dataset':dataset, 'sources':len(group),
            'sources_shown_prior_patterns':sum(any(c['supplied_pattern_count'] for c in r['calls']) for r in group),
            'sources_with_model_typed_candidates':sum((r['B_model_typed_candidates_generated'] or 0) > 0 for r in group),
            'sources_on_builtin_Horn_candidate_path':sum(r['B_builtin_Horn_candidate_path'] for r in group),
            'sources_with_learned_pattern':sum(r['B_pattern_hash'] is not None for r in group),
            'sources_with_prior_graph_structure_executed':sum(any(c['prior_graph_structure_executed_candidates'] for c in r['calls']) for r in group),
            'sources_with_connector_program':sum(any(c['program_kind'] == 'connector' for c in r['calls']) for r in group)})
    return {'binding':summary['binding'], 'processing_binding':summary['processing_binding'],
        'processing_revision':summary['processing_revision'],
        'sources':len(rows), 'scope':'existing_current_TRAIN_records_only',
        'new_model_calls':0, 'new_oracle_views':0, 'new_prediction_or_evaluation_runs':0,
        'acceptance_gates_added':False,
        'input_evidence':{'initial_full_public_inputs_exact':sum(c['initial_full_public_input_exact'] is True for c in all_calls),
            'initial_inputs_checked':sum(c['step'] == 0 for c in all_calls),
            'wire_calls_checked':len(all_calls),
            'wire_calls_allow_connector_program':sum('connector' in c['wire_program_kinds'] for c in all_calls),
            'wire_calls_interface_max_items_8':sum(c['wire_interfaces_max_items'] == 8 for c in all_calls),
            'max_observed_input_tokens':max((c['input_tokens'] for c in all_calls), default=0),
            'prompt_library_mismatches':prompt_failures},
        'A_observed':{'actions':len(all_actions),
            'sources_with_unknown_scope_residuals':sum((r['A_final_unknown_scope_units'] or 0) > 0 for r in rows),
            'sources_without_completion_assessment':sum(r['A_final_unknown_scope_units'] is None for r in rows),
            'selection_bases':dict(Counter(a['selection_basis'] for a in all_actions)),
            'batch_plan_statuses':dict(Counter(str(a['batch_plan_status']) for a in all_actions)),
            'joint_separation_complete_actions':sum(a['joint_separation_complete'] for a in all_actions),
            'selected_wire_mismatches':sum(not a['selected_source_text_matches_wire'] for a in all_actions),
            'token_or_body_mismatches':sum(not a['token_cost_matches_wire'] or not a['body_hash_matches_wire'] for a in all_actions),
            'stable_certificate_bases':dict(Counter(r['A_final_basis'] for r in rows if r['A_final_certificate'] == 'completion_stable'))},
        'B_patterns':list(learned.values()), 'B_by_dataset':by_dataset,
        'interpretation':{'builtin_components':'Horn grammar/compiler, connector DSL operators and typed execution semantics are predefined, not learned legal rules.',
            'learned_quantity':'Observed collisions can support selecting metadata obligations and retaining parameterized connector structure; count only the recorded evidence.',
            'reuse_boundary':'Showing a prior pattern in a real prompt, independently rediscovering it, and executing matching graph structure are separate evidence. A structural match alone does not prove causal transfer.',
            'train_route':'FormalRun.train calls ingest_source and source learning. The library-dependent apply_interfaces policy is in route_prediction, which is not invoked by train; evaluation remains closed.',
            'A_boundary':'Conservative residual repair is actual A control flow but not evidence of a nontrivial separating batch. Fixed-grammar stability is not learned legal-skill success.',
            'offline_boundary':'Previous artificial residual/number/entity checks remain offline implementation evidence; they are not new real-model or later-source transfer results.'},
        'source_details':rows}
