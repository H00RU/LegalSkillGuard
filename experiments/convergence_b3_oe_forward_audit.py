"""Measure the next TRAIN outcomes of the first OpenExempt update decision."""

import json
from collections import Counter
from statistics import mean

from experiments.convergence_formal_b1_observe import load_roster
from experiments.convergence_formal_train_observe import pointer
from experiments.convergence_pilot_b0 import BASE, HANDOFF, ROOT, read, sha
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


BATCH = 4
DATASET = 'OpenExempt'
ORDINARY, M2 = 'common_teacher_skill_learning', 'method_two_only'


def run():
    stage = ROOT / read(pointer(BATCH))['artifact_root']
    binding = read(stage / 'binding.json')
    checkpoint = ROOT / binding['checkpoint_root']
    study = read(checkpoint / 'binding.json')
    if stage.name != digest(binding) or binding['batch'] != BATCH or digest(study) != binding['study_binding_sha256']:
        raise ValueError('Use the original next TRAIN observation binding')
    batches = load_roster(study)
    journal = TrainingJournal(checkpoint, study, batches)
    mothers = [source for source in batches[BATCH - 1] if source['dataset'] == DATASET]
    if len(mothers) != 4:
        raise ValueError('The fixed B4 OpenExempt cohort consists of four mothers')
    observed = {arm: journal._observations(arm, BATCH) for arm in (ORDINARY, M2)}
    programs = {arm: digest(journal.library(arm, BATCH - 1)['programs'][DATASET]) for arm in observed}
    decision = read(HANDOFF / 'B3_training_terminal_audit_20261118.json')['OpenExempt_native_program_hashes']
    if (any(programs[arm] != decision[arm + ':B3'] for arm in observed) or programs[ORDINARY] == programs[M2]
            or any(journal._completed_batch(arm, BATCH - 1) != binding['entering_history'][arm] for arm in observed)):
        raise ValueError('Both B4 arms must enter with their respective sealed B3 update decisions')
    grading_path = binding['native_grade_paths'][DATASET]
    if sha(ROOT / grading_path) != binding['native_grade_sha256'][grading_path]:
        raise ValueError('Use the original TRAIN grader')
    gold = read(ROOT / grading_path)

    rows = []
    for source in mothers:
        key = source['key']
        results = {}
        for arm, observation in observed.items():
            saved = read(journal.directory(arm, BATCH) / 'predictions' / (digest(key) + '.json'))
            if digest(saved) != observation['predictions'][key]:
                raise ValueError('Use the verified entering-library predictions')
            result = saved['result']
            native = result['native']
            grades = {}
            for task in source['views']:
                identity = task['id']
                output = native[identity]
                grades[identity] = (grade_view(DATASET, task, gold[key][identity], output['answer'],
                                    output['evidence_sentence_ids'])['grade'] if output['handled'] else 0)
            finishes = Counter(trace['finish_reason'] for readout in result['reads']
                               for trace in readout['execution']['traces'] if 'finish_reason' in trace)
            results[arm] = {'native': grades, 'physical_finish_reasons': dict(finishes)}
        rows.append({'source': key, 'source_sha256': digest(source), 'arm_results': results})

    summary = {}
    for view in ('EC', 'EV'):
        deltas = [r['arm_results'][M2]['native'][view] - r['arm_results'][ORDINARY]['native'][view] for r in rows]
        summary[view] = {'mean_delta': mean(deltas), 'positive': sum(x > 0 for x in deltas),
                         'negative': sum(x < 0 for x in deltas), 'ties': sum(x == 0 for x in deltas)}
    receipt = {'fixed_batch': BATCH, 'stage_binding': stage.name, 'entering_programs': programs,
               'paired_mothers': rows, 'arm_observation_sha256': {a: r['train_observation_sha256']
                                                                  for a, r in observed.items()},
               'M2_minus_ordinary': summary, 'shared_explanation_isolated': False, 'DEV_opened': False,
               'TEST_opened': False, 'new_model_calls': 0}
    out = BASE / 'B3_M2_next_TRAIN_audit' / digest(receipt) / 'terminal.json'
    immutable_json(out, receipt)
    immutable_json(HANDOFF / 'B3_M2_next_TRAIN_audit_20261118.json',
                   {'receipt': str(out.relative_to(ROOT)), **receipt})
    print(json.dumps(summary, sort_keys=True), flush=True)


if __name__ == '__main__':
    run()
