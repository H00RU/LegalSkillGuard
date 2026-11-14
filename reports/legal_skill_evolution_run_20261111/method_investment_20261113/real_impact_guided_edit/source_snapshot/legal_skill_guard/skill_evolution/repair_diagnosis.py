"""Locate actual supervised residuals before another acquisition update.

Complete reachable profiles establish what selecting the CURRENT candidates can
repair. They do not establish which English reading is correct or prove that
the full observation interface lacks a concept. No labels become source facts.
"""
from .objects import digest
from .relational_rules import context_identity, language_identity


def _views(feedback):
    if feedback['reason'] == 'execution_error':
        raise ValueError('An execution fault is not supervised legal disagreement')
    rows = feedback['views']
    ids = [r['view'] for r in rows]
    if not rows or len(ids) != len(set(ids)):
        raise ValueError('Distinct actual supervised views required')
    return rows


def _correct(row):
    return bool(row['core_executed'] and (row.get('score') or {}).get('correct', False))


def diagnose_repairs(library, records):
    """Separate candidate-unreachable targets from current shared-G choices.

    Each record binds an actual observation, its COMPLETE direct output profile
    and the executed fitted feedback. The lower bound permits an independent G
    per source, so it cannot overstate shared-program expressiveness.
    """
    if not records:
        raise ValueError('Actual acquired-source records required')
    language = language_identity(library['language']); contexts = set(); sources = []
    for record in records:
        observation, profile = record['observation'], record['profile']
        context = observation['context']['id']
        if context in contexts:
            raise ValueError('Do not count a source observation twice')
        contexts.add(context)
        if (profile['status'] != 'complete'
                or profile.get('enumeration_scope') != 'outputs_reachable_by_subsets_of_current_direct_rules'
                or profile.get('not_a_complete_relaxed_representation_diagnostic') is not True):
            raise ValueError('A complete current-rule profile is required; timeout is unresolved')
        if (profile['context_sha256'] != context_identity(observation['context'])
                or profile['language_sha256'] != language):
            raise ValueError('Stale reading or candidate language in repair diagnosis')
        if len(profile['evaluations']) != profile['finite_theory_count']:
            raise ValueError('Incomplete reachable-profile evaluation')
        current = _views(record['feedback']); ids = [v['view'] for v in current]
        evaluated = []
        for evaluation in profile['evaluations']:
            if not evaluation['partial_source_constraints_satisfied']:
                continue
            feedback = evaluation.get('native_feedback')
            if feedback is None or feedback['reason'] == 'execution_error':
                continue  # A type/provenance/execution rejection is never a legal answer.
            views = _views(feedback)
            if [v['view'] for v in views] != ids:
                raise ValueError('Profile and execution must use the same native targets')
            evaluated.append((evaluation, views, sum(not _correct(v) for v in views)))
        if not evaluated:
            raise ValueError('No hard-valid executed candidate; diagnose the execution language first')
        best = min(loss for _, _, loss in evaluated)
        actual_loss = sum(not _correct(v) for v in current)
        if actual_loss < best:
            raise ValueError('Current execution contradicts its purported complete profile')
        residuals = []
        for i, view in enumerate(current):
            if _correct(view):
                continue
            witnesses = [evaluation['witness_rule_ids'] for evaluation, views, _ in evaluated
                         if _correct(views[i])]
            residuals.append({'view': view['view'], 'actual_value': view['execution']['value'],
                'actual_core_executed': view['core_executed'],
                'correct_with_some_current_candidate_subset': bool(witnesses),
                'correcting_candidate_witnesses': witnesses,
                'repair_target': 'shared_G_selection_or_interaction' if witnesses else
                    'reading_candidate_language_or_consumer_refinement',
                'missing_source_concept_certified': False})
        sources.append({'source': context, 'observation_sha256': digest(observation['visible_inputs']),
            'profile_sha256': digest(profile), 'actual_native_loss': actual_loss,
            'best_current_source_specific_loss': best,
            'best_witness_rule_ids': [e['witness_rule_ids'] for e, _, loss in evaluated if loss == best],
            'residuals': residuals})
    actual = sum(s['actual_native_loss'] for s in sources)
    lower = sum(s['best_current_source_specific_loss'] for s in sources)
    return {'scope': 'complete_current_direct_rule_candidates', 'sources': sources,
        'current_shared_native_loss': actual, 'source_specific_candidate_loss_lower_bound': lower,
        'gap_to_source_specific_lower_bound': actual - lower,
        'next_operation': 'open_reading_language_or_consumer_refinement' if lower else
            'shared_composition_refinement' if actual else 'freeze_and_reuse',
        'representation_conflict_certificates': [], 'source_semantics_certified': False,
        'new_model_requests': 0, 'language_sha256': language}
