"""Native execution for the five revision-4 training arms."""

import json
from pathlib import Path

from legal_skill_guard.paired_interfaces.formal_evaluation import ConvergenceEvaluation, sealed, verify
from legal_skill_guard.paired_interfaces.formal_training import RelationalInterfaceLibrary
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.ledger import BudgetError
from legal_skill_guard.skill_evolution.objects import digest

M1_ARMS = frozenset({'method_one_only', 'both'})


def initial_libraries(program, study_binding):
    """All arms share the unadapted program and an empty learned state at B0."""
    return {
        arm: sealed({
            'arm': arm, 'batch': 0, 'study_binding': study_binding,
            'programs': dict.fromkeys(ConvergenceEvaluation.datasets, program),
            'interface_library': None, 'method_specific_pilot_state_loaded': False,
        }, 'snapshot_sha256')
        for arm in ConvergenceEvaluation.arms
    }


def common_cells(source):
    if source['dataset'] == 'ContractNLI':
        source = {**source, 'evidence_presentation': 'explicit_zero_based_spans'}
    if source['dataset'] == 'OpenExempt':
        return [{**source, 'views': [view]} for view in source['views']]
    return [source]


class ConvergenceActor:
    """Reuse actual program readers or a TRAIN-selected certified interface."""

    def __init__(self, root, *, program_actor, interface_actor, providers, train_sources, study_binding):
        self.root = Path(root)
        self.program_actor = program_actor
        self.interface_actor = interface_actor
        self.providers = providers
        self.train_sources = frozenset(train_sources)
        self.study_binding = study_binding

    def _select(self, source, library):
        verify(library, 'snapshot_sha256')
        arm = library['arm']
        snapshot = library['interface_library']
        if (arm not in ConvergenceEvaluation.arms or library['study_binding'] != self.study_binding
                or set(library['programs']) != ConvergenceEvaluation.datasets
                or (snapshot is not None and (arm not in M1_ARMS or library['batch'] == 0))):
            raise ValueError('The arm must retain its own revision-4 training history')
        provider = self.providers.get(source['dataset'])
        state = {'source': source['key'], 'source_public_sha256': digest(source),
                 'library_sha256': library['snapshot_sha256'], 'current_source_truth_or_read_used': False}
        if snapshot is None or provider is None:
            return {**state, 'route': 'common_program'}, []
        learner = RelationalInterfaceLibrary.restore(self.root, actor=self.interface_actor,
            train_sources=self.train_sources, snapshot=snapshot)
        if snapshot['batch'] != library['batch']:
            raise ValueError('Cross-batch interface library mismatch')
        views = provider.views(source)
        decisions = []
        tasks = []
        for view in views:
            tasks.extend(view['native_tasks'])
            plan, receipt = learner.choose(source, view)
            provider.verify_plan(source, view, plan)
            decisions.append((view, plan, receipt))
        if sorted(tasks) != sorted(view['id'] for view in source['views']):
            raise ValueError('An interface route must preserve the full native task partition')
        if not any(not plan['is_correct_fixed_raw_control'] for _, plan, _ in decisions):
            return {**state, 'route': 'common_program',
                    'no_synthesized_template_selected': True}, []
        state.update(route='synthesized_interface',
                     choices=[{'view': view['view'], 'version': plan['version'], **receipt}
                              for view, plan, receipt in decisions])
        return state, decisions

    def __call__(self, source, library, purpose):
        selection, decisions = self._select(source, library)
        immutable_json(self.root / 'convergence_decisions' / (digest([selection, purpose]) + '.json'), selection)
        if decisions:
            reads = [self.interface_actor.measure(source, view, plan, purpose) for view, plan, _ in decisions]
        else:
            program = library['programs'][source['dataset']]
            reads = [self.program_actor.execute(program, scoped, purpose) for scoped in common_cells(source)]
        native = {task: output for read in reads for task, output in read['native'].items()}
        return {'selection': selection, 'reads': reads, 'native': native, 'fallback_executed': False}

    def verify_saved(self, source, library, purpose, result):
        selection, decisions = self._select(source, library)
        path = self.root / 'convergence_decisions' / (digest([selection, purpose]) + '.json')
        if selection != result['selection'] or not path.exists() or json.loads(path.read_text()) != selection:
            raise BudgetError('A saved prediction lost the immutable selection made before the read')
        reads = result['reads']
        if decisions:
            for (view, plan, _), read in zip(decisions, reads, strict=True):
                self._verify_read(source, view, plan, purpose, read)
        else:
            program = library['programs'][source['dataset']]
            for scoped, read in zip(common_cells(source), reads, strict=True):
                self.program_actor.verify_program_result(scoped, program, purpose, read)
        native = {task: output for read in reads for task, output in read['native'].items()}
        if result['native'] != native or set(native) != {view['id'] for view in source['views']}:
            raise BudgetError('Native outputs do not match the saved, complete physical reads')

    def _verify_read(self, source, view, plan, purpose, read):
        actor = self.interface_actor
        directory = actor.root / 'interface_reads' / digest(read['logical_call_id'])
        task = json.loads((directory / 'task.json').read_text())
        if (read['view'] != view['view'] or read['raw_read_version'] != plan['version']
                or read['channel_version'] != actor.channel_version(plan)
                or read['task_sha256'] != digest(task) or task['source_public_sha256'] != digest(source)
                or task['source'] != source['key'] or task['purpose'] != purpose
                or digest(json.loads((directory / 'decoded.json').read_text())) != digest(read)):
            raise BudgetError('A saved relational response does not bind the same candidate and source')
        actor.physical_verifier(identity=read['physical_call_id'], source=source['key'], purpose=purpose,
            content_sha256=read['response_content_sha256'], usage=read['usage'],
            finish_reason=read['response_finish_reason'])
