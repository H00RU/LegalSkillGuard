"""Versioned TRAIN calibration for consumer-derived interface pairs."""

from collections import Counter

from legal_skill_guard.paired_interfaces.residual import source_fidelity
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
