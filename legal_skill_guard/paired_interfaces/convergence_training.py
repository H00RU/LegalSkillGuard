"""Versioned TRAIN calibration for consumer-derived interface pairs."""

from collections import Counter
from dataclasses import asdict
import math

from legal_skill_guard.paired_interfaces.convergence_actors import common_cells
from legal_skill_guard.paired_interfaces.residual import source_fidelity
from legal_skill_guard.paired_interfaces.shared_semantics_validation import validate_patch
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


def training_batches(roster, public_sources, quotas):
    """Resolve the original eight batches without order or task drift."""
    public = {row['key']: row for row in public_sources}
    if len(public) != len(public_sources) or Counter(row['dataset'] for row in public_sources) != quotas:
        raise ValueError('The complete TRAIN population and native library quotas are required')
    batches = roster['fixed_training_batches']
    if len(batches) != 8 or any(len(batch) != 16 for batch in batches):
        raise ValueError('The experiment requires eight locked 16-source training batches')
    seen, output = set(), []
    for batch in batches:
        current = []
        for entry in batch:
            key = entry['source']
            if (key in seen or key not in public or entry['project_split'] != 'train'
                    or public[key]['project_split'] != 'train' or public[key]['dataset'] != entry['dataset']
                    or digest(public[key]) != entry['public_content_sha256']
                    or [view['id'] for view in public[key]['views']] != entry['native_views']):
                raise ValueError('A fixed TRAIN source, order entry or native task binding changed')
            current.append(public[key])
            seen.add(key)
        output.append(current)
    if seen != set(public):
        raise ValueError('Every fixed TRAIN mother must enter the prefix exactly once')
    return output


def calibrate_source(library, source, view, *, unit_reviews, grade_provider, visible_prefix):
    """Measure the complete paired pool, then bind native grades and source audits."""
    if source['key'] not in visible_prefix or not set(visible_prefix) <= library.train_sources:
        raise ValueError('Calibration is restricted to the visible TRAIN prefix')
    if not view['plans'] or len({plan['version'] for plan in view['plans']}) != len(view['plans']):
        raise ValueError('Choose a nonempty, distinct certified candidate pool')
    if any(set(plan['relational_program']['units']) != unit_reviews.keys() for plan in view['plans']):
        raise ValueError('Every current candidate needs the same independently audited local units')
    measured = [(plan, library.actor.measure(source, view, plan, 'skill_actor')) for plan in view['plans']]
    annotation = grade_provider(source['key'])
    tasks = {task['id']: task for task in source['views'] if task['id'] in view['native_tasks']}
    if set(tasks) != set(view['native_tasks']) or not tasks or not tasks.keys() <= annotation.keys():
        raise ValueError('Native advice cannot stand in for complete original TRAIN grading')
    evidence_sha256 = digest({
        name: {'provenance': row['provenance'], 'admissible_states': row['admissible_states'],
               'native_evidence_ids': row.get('native_evidence_ids')}
        for name, row in unit_reviews.items()
    })
    observations = []
    for plan, read in measured:
        if set(read['native']) != set(tasks):
            raise ValueError('A paired response lost a declared native task')
        grades = []
        for task, native in tasks.items():
            output = read['native'][task]
            if not output['handled']:
                grades.append(0.0)
                continue
            result = grade_view(source['dataset'], native, annotation[task], output['answer'],
                                output.get('evidence_sentence_ids', []))
            if result['grade'] is None:
                raise ValueError('The native scorer did not produce a selection utility')
            grades.append(result['grade'])
        locals_ = (read.get('decoder_receipt') or {}).get('local_receipts', {})
        checks = {}
        for name, unit in plan['relational_program']['units'].items():
            review = unit_reviews[name]
            values = locals_.get(name, {}).get('source_read', {}).get('values')
            if values is None:
                checks[name] = {'status': 'unread', 'source_fidelity_verified': False}
                continue
            checks[name] = source_fidelity(review['module'], unit['asset'], values,
                                          admissible_states=review['admissible_states'], provenance=review['provenance'])
            native_evidence = review.get('native_evidence_ids', {})
            if any(not set(ids) <= set(read['native'][task].get('evidence_sentence_ids', []))
                   for task, ids in native_evidence.items()):
                checks[name].update(status='evidence_scope_mismatch', source_fidelity_verified=False)
        observations.append(library.observe(
            source, view, plan, read, native_utility=sum(grades) / len(grades),
            source_fidelity={'all_local_relations_source_faithful': all(row['source_fidelity_verified']
                                                                     for row in checks.values()),
                             'native_labels_used_to_complete_unknowns': False,
                             'reference_evidence_sha256': evidence_sha256, 'per_local_unit': checks},
            visible_prefix=visible_prefix,
        ))
    return observations


def measure_program_prefix(actor, program, sources, *, grade_provider, visible_prefix):
    """Run and verify one program across the whole declared native cohort."""
    visible = set(visible_prefix)
    keys = [source['key'] for source in sources]
    if (not keys or len(keys) != len(set(keys)) or not set(keys) <= visible
            or any(source['project_split'] != 'train' for source in sources)):
        raise ValueError('Program fitting may only score complete visible TRAIN mothers')
    predictions = {}
    for source in sources:
        native = {}
        physical = []
        for cell in common_cells(source):
            result = actor.execute(program, cell, 'skill_actor')
            actor.verify_program_result(cell, program, 'skill_actor', result)
            if native.keys() & result['native'].keys():
                raise ValueError('A common input route duplicated a native task')
            native.update(result['native'])
            physical.extend(trace['physical_call_id'] for trace in result['execution']['traces']
                            if 'finish_reason' in trace and 'physical_call_id' in trace)
        if set(native) != {view['id'] for view in source['views']}:
            raise ValueError('The prepared program lost a required native task')
        predictions[source['key']] = (native, physical)
    rows = []
    for source in sources:
        key = source['key']
        native, physical = predictions[key]
        grade = grade_provider(key)
        if set(grade) != set(native):
            raise ValueError('A candidate must retain the same declared native grading tasks')
        scored = {}
        for view in source['views']:
            task = view['id']
            output = native[task]
            outcome = grade_view(source['dataset'], view, grade[task], output['answer'],
                                 output.get('evidence_sentence_ids', [])) if output['handled'] else {'grade': 0.0}
            if outcome['grade'] is None:
                raise ValueError('The native training score is unavailable')
            scored[task] = outcome['grade']
        rows.append({'source': key, 'dataset': source['dataset'], 'public_sha256': digest(source),
                     'native_task_utilities': scored, 'native_utility': math.fsum(scored.values()) / len(scored),
                     'actual_prediction_sha256': digest(native), 'physical_call_ids': physical})
    return {'program_sha256': digest(program), 'ordered_train_prefix_sha256': digest(keys),
            'source_rows': rows, 'all_native_tasks_kept': True}


def native_update_pairs(incumbent, candidate):
    if incumbent['ordered_train_prefix_sha256'] != candidate['ordered_train_prefix_sha256']:
        raise ValueError('The measured candidate and incumbent use different original TRAIN mothers')
    results = []
    for prior, updated in zip(incumbent['source_rows'], candidate['source_rows'], strict=True):
        if (prior['source'] != updated['source'] or prior['public_sha256'] != updated['public_sha256']
                or prior['native_task_utilities'].keys() != updated['native_task_utilities'].keys()):
            raise ValueError('The paired program measurement changed the source or tasks')
        results.append({'source': prior['source'], 'baseline_utility': prior['native_utility'],
                        'patch_utility': updated['native_utility'],
                        'incumbent_evidence_sha256': digest(prior), 'patch_evidence_sha256': digest(updated)})
    return results


def select_program_update(incumbent, candidates, theory, *, visible_prefix,
                          verify_native_pair, verify_projection):
    """Compare ordinary and relation-aware retention on one exact measured pool."""
    if not candidates:
        raise ValueError('A measured update pool must contain at least one candidate')
    visible = set(visible_prefix)
    existing = digest(incumbent)
    receipts = []
    signatures = set()
    for candidate in candidates:
        patch = digest(candidate['program'])
        if patch == existing or patch in signatures:
            raise ValueError('The measured pool must bind distinct candidate programs')
        signatures.add(patch)
        comparisons = candidate['native_comparisons']
        sources = [row['source'] for row in comparisons]
        if not sources or len(sources) != len(set(sources)) or not set(sources) <= visible:
            raise ValueError('Every candidate must score a unique set of visible TRAIN mothers')
        actual = {}
        for row in comparisons:
            before, after = row['baseline_utility'], row['patch_utility']
            if (any(type(value) not in (int, float) or not 0 <= value <= 1 for value in (before, after))
                    or verify_native_pair(patch, row) is not True):
                raise ValueError('Every common native score needs a measured and verified pair')
            actual[row['source']] = before
        groups = candidate['group_reads']
        if groups and theory is None:
            raise ValueError('A projection read needs independently audited semantics')
        group_identity = sorted(digest({
            'cases': [asdict(case) for case in sorted(group['cases'], key=lambda item: item.source_id)],
            'literal_assertion_fields': sorted(group.get('literal_assertion_fields', ())),
        }) for group in groups)
        receipt = {
            'program_sha256': patch,
            'score_gain': math.fsum(row['patch_utility'] - row['baseline_utility'] for row in comparisons) / len(sources),
            'bound_native_controls': actual, 'group_identity': group_identity,
        }
        if groups:
            receipt['relation_validation'] = validate_patch(
                theory, patch, groups, comparisons, visible_train=visible,
                verify_projection=verify_projection, verify_native_pair=verify_native_pair)
        receipts.append(receipt)
    first = receipts[0]
    if any(row['bound_native_controls'] != first['bound_native_controls']
           or row['group_identity'] != first['group_identity'] for row in receipts):
        raise ValueError('Both learners require the same measured native and relation cohorts')
    order = sorted(receipts, key=lambda row: (-row['score_gain'], row['program_sha256']))
    native = next((row['program_sha256'] for row in order if row['score_gain'] > 0), existing)
    if first['group_identity']:
        shared = next((row['program_sha256'] for row in order
                       if row['relation_validation']['status'] == 'eligible_train_update'), existing)
    else:
        shared = native
    return {'incumbent_sha256': existing, 'ordinary_choice_sha256': native, 'shared_choice_sha256': shared,
            'relation_applicable': bool(first['group_identity']), 'candidate_receipts': order,
            'identical_observation_pools': True, 'independent_test_effect_established': False}
