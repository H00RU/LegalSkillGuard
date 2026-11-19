"""Attach previously measured source-bound ContractNLI rules to revised B8 DEV."""

import json
from collections import Counter
from pathlib import Path
from statistics import mean

from experiments import convergence_revision5_cni_agreement_object as agreement
from experiments import convergence_revision5_cni_clause_witness as clause
from experiments import convergence_revision5_cni_definition_binding as definitions
from experiments import convergence_revision5_cni_designation_control as designation
from experiments import convergence_revision5_cni_disposition_literal as disposition
from experiments import convergence_revision5_cni_reverse_engineering as original
from experiments import convergence_revision5_cni_survival_scope as survival
from experiments import convergence_revision5_common_native_dev as common
from experiments.convergence_pilot_b0 import BASE, HANDOFF, ROOT, read, sha
from experiments.convergence_revision5_diversity_formal import ledger_status
from experiments.convergence_revision5_formal_native import CURRENT as INTEGRATED
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest

HOME = BASE / 'revision5_cni_compose_scope_20261119'
POINTER = HANDOFF / 'revision5_cni_compose_scope_current.json'
DATASET = 'ContractNLI'


def compile_extensions(source):
    views = {v['id']: v for v in source['views']}
    graph = {}
    marker = designation.direct(views[designation.TASK])
    if marker['answer'] is not None:
        graph[designation.TASK] = {'label': marker['answer'], 'witnesses': [marker['evidence']]}
    for name, witnesses in definitions.find_witnesses(definitions.views_for(source)).items():
        if witnesses:
            graph[definitions.TASKS[name]] = {'label': definitions.source_projection(name),
                                              'witnesses': [list(w.spans) for w in witnesses]}
    sign, sample = agreement.compile_scope(views[agreement.TASK])
    if sample and sign in ('explicit_bar', 'explicit_grant', 'defined_object_bar'):
        graph[agreement.TASK] = {'label': sample['answer'], 'witnesses': [sample['evidence_sentence_ids']]}
    returns = disposition.positive_citations(disposition.spans_for(views[disposition.TASK]))
    if returns:
        graph[disposition.TASK] = {'label': 'Entailment', 'witnesses': [sorted(x) for x in returns]}
    end = survival.bound_proofs(survival.normalize(views[survival.TASK]))
    if end:
        graph[survival.TASK] = {'label': survival.YES, 'witnesses': [list(w.spans) for w in end]}
    for name, paths in clause.source_proofs(views['nda-4']).items():
        if paths:
            graph[clause.paired.TASKS[name]] = {'evidence_continuations': paths}
    return graph


def apply_extensions(native, compiled):
    output = {}
    for task, before in native.items():
        current = {'answer': before['answer'], 'evidence_sentence_ids': before['evidence_sentence_ids']}
        rule = compiled.get(task)
        if rule and 'label' in rule:
            evidence = set(current['evidence_sentence_ids'])
            choices = rule['witnesses']
            if current['answer'] != rule['label'] or not any(set(ids) <= evidence for ids in choices):
                current = {'answer': rule['label'], 'evidence_sentence_ids': choices[0]}
        elif rule:
            reading = {'answer': current['answer'], 'evidence': current['evidence_sentence_ids']}
            full, _ = clause.complete(reading, rule['evidence_continuations'])
            current = {'answer': full['answer'], 'evidence_sentence_ids': full['evidence']}
        output[task] = current
    return output


def archived_dev(cohort, study):
    current = read(INTEGRATED)
    root = ROOT / current['artifact_root']
    end = verify(read(root / 'terminal.json'), 'terminal_sha256')
    if end['terminal_sha256'] != current['terminal_sha256'] or end['TEST_opened']:
        raise ValueError('Use the exact integrated archived B8 native cells')
    arms, prior_scores = {}, {}
    for arm, final in end['per_arm'].items():
        directory = root / 'dev' / 'B8' / arm
        seal = verify(read(directory / 'prediction_seal.json'), 'prediction_seal_sha256')
        score = verify(read(directory / 'scores.json'), 'cell_sha256')
        if (score['cell_sha256'] != final['cell_sha256']
                or score['prediction_seal_sha256'] != seal['prediction_seal_sha256']
                or seal['task_sha256'] != digest(read(directory / 'task.json'))):
            raise ValueError('The archived CNI predictions and native scores must have the exact B8 seal')
        arms[arm] = {}
        prior_scores[arm] = [r for r in score['source_scores'] if r['dataset'] == DATASET]
        for key, source in cohort.items():
            saved = read(directory / 'predictions' / (digest(key) + '.json'))
            if (digest(saved) != seal['predictions_sha256'][key]
                    or saved['library_sha256'] != score['libraries'][DATASET]
                    or saved['public_source_sha256'] != digest(source)):
                raise ValueError('A prediction lost its exact source and arm binding')
            arms[arm][key] = saved['result']['native']
    grade = study['grading_paths'][DATASET]
    path = ROOT / grade
    if 'dev' not in path.parts or sha(path) != study['grading_file_sha256'][grade]:
        raise ValueError('Score inside the fixed B8 DEV split')
    return arms, path, end['terminal_sha256'], prior_scores


def score(cohort, old, new, grade, archived=()):
    by_task = {task: [] for task in next(iter(old.values()))}
    by_metric = {'accuracy': ([], []), 'evidence_f1': ([], [])}
    old_grades = {(r['source'], r['view']): r['native_metrics'] for r in archived}
    for key, source in cohort.items():
        for view in source['views']:
            task = view['id']
            label = grade[key][task]
            metrics = [grade_view(DATASET, view, label, bank[key][task]['answer'],
                                  bank[key][task]['evidence_sentence_ids']) for bank in (old, new)]
            if old_grades and old_grades[key, task] != metrics[0]:
                raise ValueError('The baseline must reproduce the exact sealed original CNI grades')
            by_task[task].append(metrics)
            for metric, field in (('accuracy', 'grade'), ('evidence_f1', 'evidence_f1')):
                for seq, r in zip(by_metric[metric], metrics, strict=True):
                    seq.append({'source': key, 'view': task, 'grade': r[field]})
    summary = {}
    for metric, (a, b) in by_metric.items():
        summary[metric] = {'old': mean(r['grade'] for r in a), 'revised': mean(r['grade'] for r in b),
                           'better': sum(y['grade'] > x['grade'] for x, y in zip(a, b, strict=True)),
                           'worse': sum(y['grade'] < x['grade'] for x, y in zip(a, b, strict=True)),
                           'paired': paired_source_effect(a, b)}
    summary['per_hypothesis'] = {
        task: {'correct': [int(sum(pair[i]['grade'] for pair in pairs)) for i in range(2)],
               'evidence_f1': [mean(pair[i]['evidence_f1'] for pair in pairs) for i in range(2)]}
        for task, pairs in by_task.items()}
    return summary


def run():
    ledger = ledger_status()
    if ledger.get('reserved'):
        raise ValueError('Evaluate archived predictions with a settled ledger')
    raw_cohort, _, study, _ = common.archive()
    dev = {s['key']: s for s in raw_cohort if s['dataset'] == DATASET}
    dev_arms, dev_grade, dev_parent, baseline = archived_dev(dev, study)
    train, original_arms, train_grade, train_stages = original.collect(*original.archive_context(), 'train')
    baseline_train = {}
    for arm, samples in original_arms.items():
        baseline_train[arm] = {}
        for key, result in samples.items():
            archived_outputs = common.apply_compiled(train[key], result['native'], common.contract_rules(train[key]))
            baseline_train[arm][key] = {task: row['common'] for task, row in archived_outputs.items()}
    files = (Path(__file__), *(Path(m.__file__) for m in
        (agreement, clause, definitions, designation, disposition, survival, common, original)))
    spec = {'stage': 'revised_B8_CNI_scope_extension', 'parent_B8_terminal_sha256': dev_parent,
            'original_TRAIN_stages_sha256': train_stages,
            'TRAIN_grade_sha256': sha(train_grade), 'DEV_grade_sha256': sha(dev_grade),
            'source_sha256': {str(p.relative_to(ROOT)): sha(p) for p in files},
            'unchanged_B8_views_per_arm': 112, 'expected_contract_TRAIN_DEV_mothers': [24, 16]}
    out = HOME / digest(spec)
    immutable_json(out / 'binding.json', spec)
    if (out / 'terminal.json').is_file():
        print(out, flush=True)
        return
    reports, prediction_hashes = {}, {}
    for part, sources, conditions, grade_path in (
            ('train', train, baseline_train, train_grade), ('dev', dev, dev_arms, dev_grade)):
        scopes = {key: compile_extensions(source) for key, source in sources.items()}
        variants = {arm: {key: apply_extensions(native, scopes[key]) for key, native in data.items()}
                    for arm, data in conditions.items()}
        prediction_hashes[part] = immutable_json(out / f'{part}_predictions.json', variants)
        annotations = read(grade_path)
        reports[part] = {'scoped_mothers_by_task': dict(Counter(task for s in scopes.values() for task in s)),
                         'arms': {arm: score(sources, conditions[arm], variant, annotations,
                                             baseline[arm] if part == 'dev' else ())
                                  for arm, variant in variants.items()}}
    if ledger_status() != ledger:
        raise ValueError('The local composition may not change the ledger')
    record = sealed({'status': 'settled_revised_B8_CNI_scope_composition', 'binding_sha256': digest(spec),
                     'reports': reports, 'predictions_sha256': prediction_hashes,
                     'new_model_calls': 0, 'ledger': ledger, 'TEST_opened': False}, 'terminal_sha256')
    immutable_json(out / 'terminal.json', record)
    pending = POINTER.with_suffix('.pending')
    pending.write_text(json.dumps({'status': record['status'], 'terminal_sha256': record['terminal_sha256'],
                                   'artifact_root': str(out.relative_to(ROOT))}) + '\n')
    pending.replace(POINTER)
    print(out, flush=True)


if __name__ == '__main__':
    run()
