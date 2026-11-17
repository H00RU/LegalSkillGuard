"""Complete-cohort DEV curves and one sealed TEST matrix.

Prediction actors receive public inputs and an arm's own frozen library only.
The grading callback is invoked after the whole cell's predictions are sealed.
DEV chooses among B1/B4/B8 within each dataset; B0 is a curve point. A changed
library, source cohort, prediction or freeze cannot silently reuse old scores.
"""
from collections import defaultdict
from copy import deepcopy
import json
from pathlib import Path

from legal_skill_guard.paired_interfaces.formal_design import ARMS, CURVES
from legal_skill_guard.paired_interfaces.pilot_metrics import summarize
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


def sealed(value, field):
    if field in value:
        raise ValueError('Seal field already exists')
    return {**deepcopy(value), field: digest(value)}


def verify(value, field):
    if value.get(field) != digest({k: v for k, v in value.items() if k != field}):
        raise ValueError('A frozen artifact changed: ' + field)
    return value


def check_library(library, arm, batch):
    verify(library, 'snapshot_sha256')
    if library.get('arm') != arm or library.get('batch') != batch:
        raise ValueError('The actor must use its own exact arm/checkpoint library')
    return library


class FormalEvaluation:
    def __init__(self, root, sources, *, binding, grade_provider):
        self.root, self.binding = Path(root), deepcopy(binding)
        self.sources = deepcopy(sources)
        self.grade_provider = grade_provider
        if set(sources) != {'dev', 'test'} or not binding:
            raise ValueError('Explicit DEV/TEST public manifests and study binding required')
        identities = [s['key'] for values in sources.values() for s in values]
        if len(identities) != len(set(identities)) or any(not values for values in sources.values()):
            raise ValueError('Public evaluation mothers must be nonempty and source-disjoint')
        for values in self.sources.values():
            for source in values:
                views = [view['id'] for view in source['views']]
                if not views or len(views) != len(set(views)):
                    raise ValueError('Every mother needs all distinct native tasks')

    def cell_path(self, partition, arm, batch):
        return self.root / partition / ('B' + str(batch)) / arm

    def evaluate(self, partition, arm, batch, libraries, actor, *, freeze=None):
        if arm not in ARMS or partition not in self.sources:
            raise ValueError('Use a prespecified system and evaluation partition')
        if self.binding.get('enforce_physical_actor_audit') and not callable(getattr(actor, 'verify_saved', None)):
            raise ValueError('A formal scientific actor must audit saved physical execution evidence')
        if partition == 'dev' and batch not in CURVES:
            raise ValueError('DEV is measured only at B0/B1/B4/B8')
        if partition == 'test':
            if batch != 8 or freeze is None:
                raise ValueError('TEST requires the original B8 selection freeze')
            self.verify_freeze(freeze)
        elif freeze is not None:
            raise ValueError('A TEST freeze is not a DEV library selector')
        cohort = self.sources[partition]
        datasets = {source['dataset'] for source in cohort}
        if set(libraries) != datasets:
            raise ValueError('Every fixed dataset needs exactly one library')
        for dataset, library in libraries.items():
            expected_batch = batch
            if partition == 'test':
                selection = freeze['choices'][arm][dataset]
                expected_batch = selection['checkpoint_batch']
                if library['snapshot_sha256'] != selection['library_sha256']:
                    raise ValueError('TEST library differs from the sealed DEV selection')
            check_library(library, arm, expected_batch)
        directory = self.cell_path(partition, arm, batch)
        task = {'partition': partition, 'arm': arm, 'batch': batch, 'study_binding': self.binding,
                'public_cohort_sha256': digest(cohort),
                'libraries': {d: lib['snapshot_sha256'] for d, lib in sorted(libraries.items())},
                'freeze_sha256': freeze['freeze_sha256'] if freeze is not None else None}
        immutable_json(directory / 'task.json', task)
        predictions = []
        for source in cohort:
            path = directory / 'predictions' / (digest(source['key']) + '.json')
            library = libraries[source['dataset']]
            if path.exists():
                prediction = json.loads(path.read_text())
            else:
                # No grader, source reference or target answer enters the actor.
                result = actor(deepcopy(source), deepcopy(library),
                               'skill_dev' if partition == 'dev' else 'skill_test')
                prediction = {'source': source['key'], 'dataset': source['dataset'],
                    'public_source_sha256': digest(source), 'library_sha256': library['snapshot_sha256'],
                    'result': result, 'fallback_executed': False}
                immutable_json(path, prediction)
            if (prediction['source'] != source['key'] or prediction['dataset'] != source['dataset']
                    or prediction['public_source_sha256'] != digest(source)
                    or prediction['library_sha256'] != library['snapshot_sha256']
                    or prediction['fallback_executed'] is not False):
                raise ValueError('A saved prediction lost its source/library/arm binding')
            native = prediction['result']['native']
            if set(native) != {view['id'] for view in source['views']}:
                raise ValueError('An actor must retain every native task,including unresolved outputs')
            for value in native.values():
                if (type(value.get('handled')) is not bool or value.get('fallback_executed', False)
                        or value['handled'] and 'answer' not in value):
                    raise ValueError('A native output needs explicit handling and actual answer provenance')
            if callable(getattr(actor, 'verify_saved', None)):
                actor.verify_saved(deepcopy(source), deepcopy(library),
                                   'skill_dev' if partition == 'dev' else 'skill_test', prediction['result'])
            predictions.append(prediction)
        seal = sealed({'task_sha256': digest(task),
            'predictions_sha256': {row['source']: digest(row) for row in predictions},
            'all_fixed_mothers_and_native_tasks_preserved': True,
            'all_predictions_saved_before_this_cell_grading': True}, 'prediction_seal_sha256')
        immutable_json(directory / 'prediction_seal.json', seal)
        # A resume verifies predictions before reusing scores; it never reopens
        # labels or regenerates an already recorded physical response.
        scores_path = directory / 'scores.json'
        if scores_path.exists():
            report = json.loads(scores_path.read_text())
            verify(report, 'cell_sha256')
            if report['prediction_seal_sha256'] != seal['prediction_seal_sha256']:
                raise ValueError('Saved scores do not bind these exact sealed predictions')
            return report
        rows = []
        by_source = {source['key']: source for source in cohort}
        for prediction in predictions:
            source = by_source[prediction['source']]
            annotation = self.grade_provider(partition, source['key'], deepcopy(seal))
            if set(annotation) != {view['id'] for view in source['views']}:
                raise ValueError('Native grading must retain every fixed task')
            for view in source['views']:
                output = prediction['result']['native'][view['id']]
                grade = (grade_view(source['dataset'], view, annotation[view['id']],
                                    output['answer'], output.get('evidence_sentence_ids', []))
                         if output['handled'] else {'grade': 0., 'unresolved_or_failed': True})
                rows.append({'source': source['key'], 'dataset': source['dataset'], 'view': view['id'],
                    'handled': output['handled'], 'answer': output.get('answer'),
                    'grade': grade['grade'], 'native_metrics': grade, 'fallback_executed': False})
        aggregates = {}
        for dataset in sorted(datasets):
            expected = {(s['key'], v['id']) for s in cohort if s['dataset'] == dataset for v in s['views']}
            aggregates[dataset] = summarize([row for row in rows if row['dataset'] == dataset], expected)
        report = sealed({**task, 'prediction_seal_sha256': seal['prediction_seal_sha256'],
            'source_scores': rows, 'datasets': aggregates,
            'native_metrics_kept_within_dataset': True, 'mixed_unit_overall_accuracy_reported': False}, 'cell_sha256')
        immutable_json(scores_path, report)
        return report

    def freeze(self, libraries, *, training_B8_seal):
        """Seal every dataset's choice once,after all28 DEV cells exist."""
        verify(training_B8_seal, 'training_seal_sha256')
        if (training_B8_seal.get('batch') != 8 or training_B8_seal.get('study_binding') != self.binding
                or not training_B8_seal.get('all_seven_libraries_frozen')):
            raise ValueError('Complete B8 training libraries must precede final DEV selection')
        datasets = {source['dataset'] for source in self.sources['dev']}
        if datasets != {source['dataset'] for source in self.sources['test']}:
            raise ValueError('Every formal dataset needs both DEV and TEST mothers')
        expected_libraries = {(arm, batch) for arm in ARMS for batch in CURVES}
        if set(libraries) != expected_libraries:
            raise ValueError('All seven systems/four curve libraries must be preserved')
        reports = {}
        for arm, batch in sorted(expected_libraries):
            library = check_library(libraries[arm, batch], arm, batch)
            report = json.loads((self.cell_path('dev', arm, batch) / 'scores.json').read_text())
            verify(report, 'cell_sha256')
            if (report['study_binding'] != self.binding or report['arm'] != arm or report['batch'] != batch
                    or report['partition'] != 'dev' or report['public_cohort_sha256'] != digest(self.sources['dev'])
                    or set(report['datasets']) != datasets
                    or set(report['libraries'].values()) != {library['snapshot_sha256']}):
                raise ValueError('DEV reports must bind the complete original cohort and exact arm library')
            reports[arm, batch] = report
        b8_hashes = {arm: libraries[arm, 8]['snapshot_sha256'] for arm in ARMS}
        if training_B8_seal.get('libraries') != b8_hashes:
            raise ValueError('The B8 training seal differs from the actual seven libraries')
        choices = defaultdict(dict)
        for arm in ARMS:
            for dataset in sorted(datasets):
                eligible = (0,) if arm == 'empty' else (1, 4, 8)
                batch = max(eligible, key=lambda b: (reports[arm, b]['datasets'][dataset]['mother_macro'], b))
                choices[arm][dataset] = {'checkpoint_batch': batch,
                    'library_sha256': libraries[arm, batch]['snapshot_sha256'],
                    'DEV_mother_macro': reports[arm, batch]['datasets'][dataset]['mother_macro']}
        result = sealed({'batch': 8, 'study_binding': self.binding, 'choices': dict(choices),
            'training_B8_seal': training_B8_seal,
            'DEV_cells': {arm + ':B' + str(batch): reports[arm, batch]['cell_sha256']
                          for arm, batch in sorted(reports)},
            'DEV_public_sha256': digest(self.sources['dev']), 'TEST_public_sha256': digest(self.sources['test']),
            'TEST_grading_opened_for_selection': False,
            'selection_rule': 'per-dataset DEV mother macro;learned arms B1/B4/B8;later ties;empty direct B0'}, 'freeze_sha256')
        immutable_json(self.root / 'selection_freeze.json', result)
        return result

    def verify_freeze(self, freeze):
        verify(freeze, 'freeze_sha256')
        path = self.root / 'selection_freeze.json'
        if (not path.exists() or json.loads(path.read_text()) != freeze or freeze['batch'] != 8
                or freeze['study_binding'] != self.binding
                or freeze['DEV_public_sha256'] != digest(self.sources['dev'])
                or freeze['TEST_public_sha256'] != digest(self.sources['test'])
                or freeze['TEST_grading_opened_for_selection'] is not False):
            raise ValueError('TEST requires the exact locally sealed original-study freeze')
        return freeze
