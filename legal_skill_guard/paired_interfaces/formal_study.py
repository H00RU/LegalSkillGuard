"""One original eight-batch/seven-system train,DEV and frozen-TEST sequence.

Components use real actors/transports in the experiment entry. This coordinator
never obtains references,changes candidates,repairs from DEV/TEST or marks the
research Goal complete. Main-matrix completion still leaves the predeclared
independent contribution controls and final delivery to be audited.
"""
import json
from pathlib import Path

from legal_skill_guard.paired_interfaces.control_learning import direct_program
from legal_skill_guard.paired_interfaces.formal_budget import primary_comparison_cap
from legal_skill_guard.paired_interfaces.formal_controls import ORDINARY, SCOPE
from legal_skill_guard.paired_interfaces.formal_design import ARMS, CURVES
from legal_skill_guard.paired_interfaces.formal_evaluation import check_library, sealed, verify
from legal_skill_guard.paired_interfaces.formal_training import MissingSourceReviews
from legal_skill_guard.rr.checkpoint import immutable_json


class FormalStudy:
    def __init__(self, root, *, binding, interface_trainer, control_factory,
                 evaluator, evaluation_actor_factory, source_binding_check, diagnostics=None):
        self.root, self.binding = Path(root), binding
        self.interfaces, self.control_factory = interface_trainer, control_factory
        self.evaluator, self.evaluation_actor_factory = evaluator, evaluation_actor_factory
        self.source_binding_check = source_binding_check
        self.diagnostics = diagnostics

    def train(self):
        self.source_binding_check()
        readiness = self.interfaces.registry.readiness(8)
        immutable_json(self.root / 'training_readiness.json', readiness)
        if not readiness['ready']:
            raise MissingSourceReviews('The complete formal TRAIN corpus requires source-only reviews before any study dispatch')
        libraries, prefix_seals, latest_controls = {}, {}, {}
        for batch in range(9):
            self.source_binding_check()
            current = self.interfaces.batch(batch)
            primary_path = self.interfaces.root / ('B' + str(batch)) / 'shared_verified_raw_evidence.json'
            primary = json.loads(primary_path.read_text())
            if primary['study_binding'] != self.binding:
                raise ValueError('Primary prefix evidence belongs to another study')
            cap = primary_comparison_cap(self.interfaces.actor.executor.ledger, primary['pairs'],
                                        context_tokens=self.interfaces.actor.executor.config['context_tokens']) if batch else None
            for arm in (SCOPE, ORDINARY):
                # SCOPE releases the fixed B4 verified variants before the
                # ordinary repair;all arms retain access to the shared data.
                trainer = self.control_factory(arm, batch, cap)
                current[arm] = trainer.batch(batch); latest_controls[arm] = trainer
            current['empty'] = sealed({'arm': 'empty', 'batch': batch, 'program': direct_program(),
                'execution_max_neural_callbacks': 1, 'initialization_only': True,
                'study_binding': self.binding}, 'snapshot_sha256')
            if set(current) != set(ARMS):
                raise ValueError('Every batch must freeze all seven original systems')
            for arm in ARMS:
                check_library(current[arm], arm, batch)
                libraries[arm, batch] = current[arm]
                immutable_json(self.root / 'libraries' / ('B' + str(batch)) / (arm + '.json'), current[arm])
            seal = sealed({'batch': batch, 'study_binding': self.binding,
                'libraries': {arm: current[arm]['snapshot_sha256'] for arm in ARMS},
                'primary_raw_evidence_path': str(primary_path),
                'primary_comparison_cap': cap, 'all_seven_libraries_frozen': True,
                'DEV_TEST_feedback_used_for_training': False}, 'batch_seal_sha256')
            immutable_json(self.root / 'batch_seals' / ('B' + str(batch) + '.json'), seal)
            prefix_seals[str(batch)] = seal['batch_seal_sha256']
        controls = {arm: trainer.completion_evidence() for arm, trainer in latest_controls.items()}
        for arm, evidence in controls.items():
            ids = evidence['actual_fixed_optimizer_teacher_calls']
            expected = {str(batch): libraries[arm, batch]['snapshot_sha256'] for batch in range(9)}
            if (evidence['arm'] != arm or len(ids) != 4 * len(self.interfaces.orders)
                    or len(ids) != len(set(ids)) or evidence['candidates_per_dataset'] != 3
                    or evidence['libraries_B0_through_B8'] != expected):
                raise ValueError('Fixed optimizer calls,candidate counts and all nine libraries must be evidenced')
        training = sealed({'batch': 8, 'study_binding': self.binding,
            'libraries': {arm: libraries[arm, 8]['snapshot_sha256'] for arm in ARMS},
            'all_seven_libraries_frozen': True, 'completed_original_prefix_seals': prefix_seals,
            'actual_control_completion_evidence': controls,
            'main_candidate_pool_or_original_sources_expanded': False,
            'DEV_TEST_native_labels_used_for_updates': False}, 'training_seal_sha256')
        immutable_json(self.root / 'training_B8_seal.json', training)
        self.source_binding_check()
        return libraries, training

    def evaluate(self, libraries, training):
        self.source_binding_check(); verify(training, 'training_seal_sha256')
        expected = {(arm, batch) for arm in ARMS for batch in range(9)}
        if set(libraries) != expected or training['study_binding'] != self.binding:
            raise ValueError('Complete original nine-prefix/seven-system libraries must precede evaluation')
        dev_cells = []
        for batch in CURVES:
            for arm in ARMS:
                self.source_binding_check()
                selected = {s['dataset']: libraries[arm, batch] for s in self.evaluator.sources['dev']}
                actor = self.evaluation_actor_factory(arm, 'dev', None)
                dev_cells.append(self.evaluator.evaluate('dev', arm, batch, selected, actor))
        freeze = self.evaluator.freeze({key: value for key, value in libraries.items() if key[1] in CURVES},
                                       training_B8_seal=training)
        test_cells = []
        for arm in ARMS:
            self.source_binding_check()
            selected = {dataset: libraries[arm, choice['checkpoint_batch']]
                        for dataset, choice in freeze['choices'][arm].items()}
            actor = self.evaluation_actor_factory(arm, 'test', freeze)
            test_cells.append(self.evaluator.evaluate('test', arm, 8, selected, actor, freeze=freeze))
        terminal = {'status': 'one_fixed_main_matrix_evaluated', 'study_binding': self.binding,
            'training_seal_sha256': training['training_seal_sha256'], 'selection_freeze_sha256': freeze['freeze_sha256'],
            'DEV_cells': [row['cell_sha256'] for row in dev_cells],
            'TEST_cells': [row['cell_sha256'] for row in test_cells],
            'predeclared_M1_ablations_and_M2_transfer_controls_completed': False,
            'independent_contributions_or_complete_goal_established': False}
        immutable_json(self.root / 'main_matrix_terminal.json', terminal)
        return terminal

    def run(self):
        libraries, training = self.train()
        if self.diagnostics is not None:
            self.diagnostics.prepare(libraries, training)  # Before any DEV/TEST labels.
        main = self.evaluate(libraries, training)
        if self.diagnostics is None:
            return main
        freeze = json.loads((self.evaluator.root / 'selection_freeze.json').read_text())
        diagnostics = self.diagnostics.run(freeze)
        return {'main_matrix': main, 'fixed_contribution_diagnostics': diagnostics,
                'complete_goal_claimed': False}
