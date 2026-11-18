"""Eight-batch TRAIN receipts used by the five-arm convergence evaluation."""

import json
from pathlib import Path

from legal_skill_guard.paired_interfaces.formal_evaluation import ConvergenceEvaluation, check_library, sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


class TrainingJournal:
    """Bind each TRAIN prediction to the entering snapshot and each update to the visible prefix."""

    def __init__(self, root, binding, batches):
        self.root, self.binding, self.batches = Path(root), binding, batches
        if (len(batches) != 8 or any(len(batch) != 16 for batch in batches)
                or len({source['key'] for batch in batches for source in batch}) != 128
                or any(source['project_split'] != 'train' for batch in batches for source in batch)
                or binding.get('TRAIN_ordered_batches_sha256') != digest(batches)):
            raise ValueError('Use all eight exact ordered training batches')

    def directory(self, arm, batch):
        if arm not in ConvergenceEvaluation.arms or type(batch) is not int or not 0 <= batch <= 8:
            raise ValueError('A training receipt needs a known arm and batch')
        return self.root / 'train' / arm / ('B' + str(batch))

    def library(self, arm, batch):
        path = self.directory(arm, batch) / 'library.json'
        result = check_library(json.loads(path.read_text()), arm, batch)
        if result.get('study_binding') != self.binding:
            raise ValueError('A snapshot belongs to a different ordered study')
        return result

    def initialize(self, libraries):
        if set(libraries) != set(ConvergenceEvaluation.arms):
            raise ValueError('Initialize all five arms before dispatching training')
        configs = []
        for arm, library in libraries.items():
            check_library(library, arm, 0)
            if (library['study_binding'] != self.binding or library['interface_library'] is not None
                    or library['method_specific_pilot_state_loaded'] is not False
                    or set(library['programs']) != ConvergenceEvaluation.datasets):
                raise ValueError('Formal arms share only the pre-pilot common initial library')
            configs.append(digest(library['programs']))
        if len(set(configs)) != 1:
            raise ValueError('All formal arms must start from the same program library')
        for arm, library in libraries.items():
            immutable_json(self.directory(arm, 0) / 'library.json', library)

    def observe(self, arm, batch, actor):
        """Run only the next batch, verifying saved physical evidence on resume."""
        directory = self.directory(arm, batch)
        if batch == 0 or not callable(getattr(actor, 'verify_saved', None)):
            raise ValueError('TRAIN observations require an audited physical actor and a positive batch')
        before = self.library(arm, batch - 1)
        if batch > 1:
            self._completed_batch(arm, batch - 1)
        prediction_hashes = {}
        for source in self.batches[batch - 1]:
            path = directory / 'predictions' / (digest(source['key']) + '.json')
            metadata = {'arm': arm, 'batch': batch, 'source': source['key'], 'source_sha256': digest(source),
                        'input_library_sha256': before['snapshot_sha256']}
            if path.exists():
                record = json.loads(path.read_text())
                if {k: record.get(k) for k in metadata} != metadata:
                    raise ValueError('A saved TRAIN observation lost its source or prior-library binding')
            else:
                result = actor(source, before, 'skill_actor')
                record = {**metadata, 'result': result}
                immutable_json(path, record)
            result = record['result']
            if (set(result['native']) != {view['id'] for view in source['views']}
                    or result.get('fallback_executed') is not False):
                raise ValueError('TRAIN failed to retain the declared native scope or used an unbound fallback')
            actor.verify_saved(source, before, 'skill_actor', result)
            prediction_hashes[source['key']] = digest(record)
        receipt = sealed({'arm': arm, 'batch': batch, 'study_binding': self.binding,
                          'input_library_sha256': before['snapshot_sha256'],
                          'ordered_sources': [source['key'] for source in self.batches[batch - 1]],
                          'physical_predictions_verified': True, 'predictions': prediction_hashes},
                         'train_observation_sha256')
        immutable_json(directory / 'observations.json', receipt)
        return receipt

    def commit_update(self, arm, batch, library, evidence, *, verify_update):
        """Accept a measured update or a documented retain decision for the visible prefix."""
        directory = self.directory(arm, batch)
        if batch == 0:
            raise ValueError('B0 is initialized without fitting')
        observations = self._observations(arm, batch)
        before = self.library(arm, batch - 1)
        check_library(library, arm, batch)
        prefix = tuple(source['key'] for cohort in self.batches[:batch] for source in cohort)
        if (library.get('study_binding') != self.binding or set(library['programs']) != ConvergenceEvaluation.datasets
                or evidence.get('visible_prefix_sha256') != digest(list(prefix))
                or verify_update(before, library, evidence, prefix) is not True):
            raise ValueError('A TRAIN update must verify its actual decision and exact visible prefix')
        immutable_json(directory / 'update_evidence.json', evidence)
        immutable_json(directory / 'library.json', library)
        receipt = self._completion(arm, batch, observations, library, evidence)
        immutable_json(directory / 'completed.json', receipt)
        return receipt

    def _observations(self, arm, batch):
        directory = self.directory(arm, batch)
        value = verify(json.loads((directory / 'observations.json').read_text()), 'train_observation_sha256')
        before = self.library(arm, batch - 1)
        sources = [source['key'] for source in self.batches[batch - 1]]
        if (value.get('study_binding') != self.binding or value.get('arm') != arm or value.get('batch') != batch
                or value.get('input_library_sha256') != before['snapshot_sha256']
                or value.get('ordered_sources') != sources or set(value['predictions']) != set(sources)
                or value.get('physical_predictions_verified') is not True):
            raise ValueError('A training observation lost its complete batch binding')
        for sid in sources:
            path = directory / 'predictions' / (digest(sid) + '.json')
            if digest(json.loads(path.read_text())) != value['predictions'][sid]:
                raise ValueError('A saved TRAIN observation differs from its verified prediction receipt')
        return value

    def _completion(self, arm, batch, observations, library, evidence):
        return sealed({'arm': arm, 'batch': batch, 'study_binding': self.binding,
                       'observations_sha256': observations['train_observation_sha256'],
                       'update_evidence_sha256': digest(evidence), 'library_sha256': library['snapshot_sha256']},
                      'completed_batch_sha256')

    def _completed_batch(self, arm, batch):
        directory = self.directory(arm, batch)
        saved = verify(json.loads((directory / 'completed.json').read_text()), 'completed_batch_sha256')
        expected = self._completion(arm, batch, self._observations(arm, batch), self.library(arm, batch),
                                    json.loads((directory / 'update_evidence.json').read_text()))
        if saved != expected:
            raise ValueError('Completed TRAIN decision no longer binds its verified evidence and library')
        return saved

    def seal_B8(self):
        """Require all forty measured batch receipts before the evaluation freeze."""
        histories, libraries = {}, {}
        for arm in ConvergenceEvaluation.arms:
            records = [self._completed_batch(arm, batch) for batch in range(1, 9)]
            histories[arm] = [record['completed_batch_sha256'] for record in records]
            libraries[arm] = records[-1]['library_sha256']
        receipt = sealed({'batch': 8, 'study_binding': self.binding, 'all_five_libraries_frozen': True,
                          'libraries': libraries, 'complete_train_histories': histories,
                          'unique_TRAIN_mothers_per_arm': 128, 'heldout_loaded_for_training': False},
                         'training_seal_sha256')
        immutable_json(self.root / 'training_B8.json', receipt)
        return receipt
