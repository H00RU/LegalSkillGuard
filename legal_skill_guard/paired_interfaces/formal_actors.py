"""Real frozen-model actors for the seven formal systems.

The interface actor selects before observing the current weak read. Neither
actor loads a reference graph, answer label or scoring file. Production
failures survive; a physical transport failure propagates and stops the driver.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

import jsonschema

from legal_skill_guard.paired_interfaces import airline_interfaces, asset_graph_pairs, asset_interfaces
from legal_skill_guard.paired_interfaces import asset_port_decoder_v2, graph_interface, rich_graph_pairs
from legal_skill_guard.paired_interfaces.control_answers import source_bundle
from legal_skill_guard.paired_interfaces.control_learning import direct_program
from legal_skill_guard.paired_interfaces.control_programs import ControlProgramRuntime, ProgramBudgetExhausted
from legal_skill_guard.paired_interfaces.formal_evaluation import verify
from legal_skill_guard.paired_interfaces.formal_budget import ComparisonBudgetExhausted
from legal_skill_guard.paired_interfaces.formal_learning import select
from legal_skill_guard.paired_interfaces.formal_tools import legal_tools
from legal_skill_guard.paired_interfaces.graph_evidence import normalize_graph_evidence
from legal_skill_guard.paired_interfaces.graph_prompt import schema_visible_plan
from legal_skill_guard.paired_interfaces.port_evidence import bind_port_evidence
from legal_skill_guard.paired_interfaces.scope_learning import strict_json
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.ledger import BudgetError
from legal_skill_guard.skill_evolution.native import restore_enum_transport
from legal_skill_guard.skill_evolution.objects import digest


INTERFACE_ARMS = ('M1_only', 'M2_fixed_interfaces', 'M1_full_trace_replay', 'M1_M2')
PROGRAM_ARMS = ('empty', 'ordinary_teacher_skills', 'budget_matched_SCOPE_adaptation')


def restore_airline_wire_order(plan_assets, original_candidates):
    """Restore the original compiler's schema order after JSON artifact loading.

    Canonical artifact JSON sorts object keys;the serving grammar observes
    property order. Nothing else in the schema,prompt or candidate may change.
    OE retains the order actually used by its already settled18 port reads.
    """
    assets = deepcopy(plan_assets)
    restored = [schema_visible_plan(plan) for plan in airline_interfaces.compile_plans(original_candidates)]
    saved = assets['unchanged_libraries']['RuleArena_Airline']
    if digest(restored) != digest(saved):
        raise ValueError('The original Airline compiler changed more than schema object order')
    assets['unchanged_libraries']['RuleArena_Airline'] = restored
    return assets


def verify_physical_response(executor, *, identity, source, purpose, content_sha256, usage, finish_reason):
    """Cached computations cannot promote an orphaned/changed physical read."""
    with executor.ledger.transaction() as db:
        row = db.execute('select status,source,purpose,result from calls where id=?', (identity,)).fetchone()
    if row is None or tuple(row[:3]) != ('completed', source, purpose):
        raise BudgetError('Cached read has no matching completed source/purpose physical request')
    original = json.loads(row[3])
    if (digest(original['content']) != content_sha256 or original['usage'] != usage
            or original['finish_reason'] != finish_reason):
        raise BudgetError('Cached read differs from its actual continuous-ledger response')


class ProgramActor:
    def __init__(self, executor, root, *, max_calls, physical_verifier=None):
        self.executor, self.root, self.max_calls = executor, Path(root), max_calls
        self.physical_verifier = physical_verifier or (lambda **kw: verify_physical_response(executor, **kw))

    def execute(self, program, source, purpose):
        bundle = source_bundle(source)
        tools, assets = legal_tools(source, bundle)
        runtime = ControlProgramRuntime(self.executor, self.root, max_calls=self.max_calls,
                                       shared_assets=assets, legal_tools=tools)
        try:
            execution = runtime.run(program, source, bundle, purpose=purpose)
        except (ValueError, KeyError, TypeError, jsonschema.ValidationError,
                ProgramBudgetExhausted, ComparisonBudgetExhausted) as error:
            path = runtime.execution_path(program, source, bundle, purpose=purpose)
            if not path.exists():
                raise  # A malformed library is an implementation gate,not a perception result.
            execution = json.loads(path.read_text())
            if execution.get('error') is None:
                raise ValueError('An execution exception lost its original failure evidence') from error
        declines = self._verify_traces(source, purpose, execution)
        return {'native': self._native(source, execution), 'execution': execution,
                'execution_input_path': str(runtime.execution_path(program, source, bundle, purpose=purpose).with_name('input.json')),
                'program_execution_completed': execution['core_executed'],
                'pre_generation_comparison_refusals': declines,
                'fallback_executed': False, 'model_parameters_updated': False}

    def _verify_traces(self, source, purpose, execution):
        declines = []
        for trace in execution['traces']:
            if trace.get('type', 'predicate') == 'predicate' and trace['status'] == 'dispatched':
                receipt = (self.executor.declined_request(trace['logical_call_id'])
                           if hasattr(self.executor, 'declined_request') else None)
                if receipt is None or receipt['source'] != source['key']:
                    raise BudgetError('An unreceived physical predicate response must be reconciled;do not score it as perception')
                declines.append(receipt)
        for trace in execution['traces']:
            if trace.get('type', 'predicate') == 'predicate' and trace['status'] != 'dispatched':
                self.physical_verifier(identity=trace['physical_call_id'], source=source['key'], purpose=purpose,
                    content_sha256=digest(trace['raw_content']), usage=trace['usage'], finish_reason=trace['finish_reason'])
        return declines

    @staticmethod
    def _native(source, execution):
        native = {}
        answers = execution['answer'] if execution['core_executed'] else None
        for view in source['views']:
            task = view['id']
            evidence = []
            for trace in execution['traces']:
                value = trace.get('native_evidence', {})
                if isinstance(value, dict) and task in value:
                    evidence = value[task]
            handled = isinstance(answers, dict) and task in answers
            native[task] = {'handled': handled, 'answer': answers[task] if handled else None,
                            'evidence_sentence_ids': evidence, 'fallback_executed': False,
                            'reason': None if handled else execution['error']}
        return native

    def verify_program_result(self, source, program, purpose, result):
        bundle = source_bundle(source); tools, assets = legal_tools(source, bundle)
        runtime = ControlProgramRuntime(self.executor, self.root, max_calls=self.max_calls,
                                       shared_assets=assets, legal_tools=tools)
        path = runtime.execution_path(program, source, bundle, purpose=purpose)
        if not path.exists() or digest(json.loads(path.read_text())) != digest(result['execution']):
            raise BudgetError('A saved prediction lost its actual program execution artifact')
        execution = result['execution']
        self._verify_traces(source, purpose, execution)
        if result['native'] != self._native(source, execution):
            raise BudgetError('Saved native predictions differ from their actual program execution')

    def verify_saved(self, source, library, purpose, result):
        verify(library, 'snapshot_sha256')
        program = library['program'] if library['arm'] == 'empty' else library['datasets'][source['dataset']]['program']
        limit = library.get('execution_max_neural_callbacks', self.max_calls)
        actor = (self if limit == self.max_calls else ProgramActor(self.executor, self.root,
                 max_calls=limit, physical_verifier=self.physical_verifier))
        actor.verify_program_result(source, program, purpose, result)

    def __call__(self, source, library, purpose):
        verify(library, 'snapshot_sha256')
        if library['arm'] not in PROGRAM_ARMS:
            raise ValueError('A program actor cannot borrow an interface arm library')
        entry = None if library['arm'] == 'empty' else library['datasets'][source['dataset']]
        program = library['program'] if entry is None else entry['program']
        mode = ('direct_empty' if entry is None else 'initialization' if library['batch'] == 0 else
                'fixed_seed_selected' if entry.get('fixed_monolithic_seed') else
                'native_seed_equivalent' if digest(program) == digest(direct_program()) else 'learned_program')
        limit = library.get('execution_max_neural_callbacks', self.max_calls)
        actor = (self if limit == self.max_calls else ProgramActor(self.executor, self.root,
                 max_calls=limit, physical_verifier=self.physical_verifier))
        result = actor.execute(program, source, purpose)
        return {**result, 'execution_mode': mode,
                'learned_main_path_executed': mode == 'learned_program' and result['program_execution_completed']}


from legal_skill_guard.paired_interfaces.evidence_projection import source_evidence


class InterfaceActor:
    def __init__(self, executor, root, *, plan_assets, source_inputs, pipeline_binding, physical_verifier=None,
                 relational_provider=None):
        self.executor, self.root = executor, Path(root)
        self.assets, self.source_inputs = deepcopy(plan_assets), source_inputs
        self.pipeline_binding = deepcopy(pipeline_binding)
        self.relational_provider = relational_provider
        self.physical_verifier = physical_verifier or (lambda **kw: verify_physical_response(executor, **kw))
        if not self.pipeline_binding:
            raise ValueError('Channel versions must bind the complete frozen production/alignment pipeline')

    def channel_version(self, plan):
        return digest({'raw_reader_version': plan['version'], 'executor': self.executor.config,
                       'literal_schema_order_sha256': hashlib.sha256(json.dumps(plan['schema'], ensure_ascii=False).encode()).hexdigest(),
                       'production_alignment_binding': self.pipeline_binding})

    def views(self, source):
        if self.relational_provider is not None:
            views = self.relational_provider.views(source)
            if (any(v['source'] != source['key'] for v in views)
                    or sorted(task for v in views for task in v['native_tasks']) != sorted(v['id'] for v in source['views'])):
                raise ValueError('Generated interfaces must preserve every native task/source binding')
            for view in views:
                for plan in view['plans']:
                    self.relational_provider.verify_plan(source,view,plan)
            return views
        task, mapping = self.source_inputs(source)
        views = []
        native = {view['id']: view for view in source['views']}
        for view in task['views']:
            tasks = sorted(name for name, opaque in mapping.items() if opaque == view['view_id'])
            public = {name: native[name]['public'] for name in tasks}
            data = {'source_units': view['source_units']}
            if source['dataset'] == 'OpenExempt':
                contexts = [asset_interfaces.context_from_public(native[name]['public']) for name in tasks]
                if not contexts or len({digest(c) for c in contexts}) != 1:
                    raise ValueError('A shared source view has inconsistent public law contexts')
                data['public_context'] = contexts[0]
                if contexts[0]['supported_by_frozen_legal_program']:
                    regime = contexts[0]['governing_regime']
                    plans = self.assets['OE_by_public_regime'][regime]
                    scope = asset_graph_pairs.scope(regime)
                else:
                    plans, scope = [], None
            else:
                plans = self.assets['unchanged_libraries'][source['dataset']]
                scope = {'schema': rich_graph_pairs.SCHEMA,
                         'context': source['dataset'] + ':' + digest(tasks)}
            views.append({'source': source['key'], 'dataset': source['dataset'],
                'view': view['view_id'], 'native_tasks': tasks, 'native_public': public,
                'source_units': view['source_units'], 'read_input': data, 'plans': plans,
                'scope': scope, 'pre_generation_domain_refusal': not bool(plans)})
        if sorted(task for view in views for task in view['native_tasks']) != sorted(native):
            raise ValueError('Opaque source partition lost or duplicated native tasks')
        return views

    def measure(self, source, view, plan, purpose):
        if plan not in view['plans'] or view['source'] != source['key']:
            raise ValueError('Actual read must use the source-bound fixed candidate')
        if self.relational_provider is not None:
            self.relational_provider.verify_plan(source,view,plan)
        messages = [{'role': 'system', 'content': plan['system']},
                    {'role': 'user', 'content': json.dumps(view['read_input'], ensure_ascii=False, sort_keys=True)}]
        logical = self.executor.ledger.run_id + ':interface:' + digest({
            'source': source['key'], 'view': view['view'], 'version': plan['version'],
            'messages': messages, 'schema': plan['schema'], 'purpose': purpose})
        target = self.root / 'interface_reads' / digest(logical)
        request_task = {'source': source['key'], 'view': view['view'], 'plan': plan['name'],
                'raw_read_version': plan['version'], 'channel_version': self.channel_version(plan),
                'source_public_sha256': digest(source), 'messages': messages,
                'output_schema': plan['schema'], 'purpose': purpose, 'logical_call_id': logical}
        immutable_json(target / 'task.json', request_task)
        if (target / 'decoded.json').exists():
            result = json.loads((target / 'decoded.json').read_text())
            if result['task_sha256'] != digest(request_task):
                raise ValueError('A saved interface read belongs to a different pipeline/source')
            self.physical_verifier(identity=result['physical_call_id'], source=source['key'], purpose=purpose,
                content_sha256=result['response_content_sha256'], usage=result['usage'],
                finish_reason=result['response_finish_reason'])
            return result
        response = self.executor.generate(logical, source=source['key'], purpose=purpose,
            messages=messages, thinking=False, schema=plan['schema'])
        from legal_skill_guard.paired_interfaces.production_decode import decode_response
        decoded = decode_response(source, view, plan, response)
        result = {'task_sha256': digest(request_task), 'source': source['key'], 'view': view['view'],
            'plan': plan['name'], 'raw_read_version': plan['version'], 'channel_version': self.channel_version(plan),
            'logical_call_id': logical, 'physical_call_id': response.get('reused_physical_call_id', logical),
            'reused_paid_response': bool(response.get('reused_physical_call_id') or response.get('cache_hit')),
            **decoded, 'usage': response['usage'],
            'response_content_sha256': digest(response['content']), 'response_finish_reason': response['finish_reason'],
            'source_reference_or_native_label_used': False, 'fallback_executed': False}
        self.physical_verifier(identity=result['physical_call_id'], source=source['key'], purpose=purpose,
            content_sha256=result['response_content_sha256'], usage=result['usage'],
            finish_reason=result['response_finish_reason'])
        immutable_json(target / 'decoded.json', result)
        return json.loads((target / 'decoded.json').read_text())

    def __call__(self, source, library, purpose):
        verify(library, 'snapshot_sha256')
        arm = library['arm']
        if arm not in INTERFACE_ARMS:
            raise ValueError('An interface actor cannot borrow a program arm library')
        native, decisions, reads = {}, [], []
        for view in self.views(source):
            if view['pre_generation_domain_refusal']:
                native.update({task: {'handled': False, 'answer': None, 'fallback_executed': False,
                    'reason': 'Explicit public regime outside frozen legal F domain'} for task in view['native_tasks']})
                decisions.append({'view': view['view'], 'pre_generation_domain_refusal': True,
                                  'not_a_model_abstention_or_physical_trial': True})
                continue
            by_plan = {plan['name']: plan for plan in view['plans']}
            for row in library['raw_reader_channel_versions']:
                if ((row['dataset'], row['schema'], row['context']) ==
                        (source['dataset'], view['scope']['schema'], view['scope']['context'])
                        and row['version'] != self.channel_version(by_plan[row['plan']])):
                    raise ValueError('The selected library calibrated a different actual reader/decoder version')
            consume = ((lambda world: asset_graph_pairs.consumer_signature(world, view['native_tasks']))
                       if source['dataset'] == 'OpenExempt' else
                       (lambda world: rich_graph_pairs.consumer_signature(world, source['dataset'], view['native_public'])))
            choice = select(library, dataset=source['dataset'], schema=view['scope']['schema'],
                            context=view['scope']['context'], arm=arm, consume=consume)
            decision = {'source': source['key'], 'view': view['view'], 'arm': arm,
                        'library_sha256': library['snapshot_sha256'], 'choice': choice,
                        'actual_current_read_or_reference_or_grade_used': False}
            # Seal selection before executing even an exactly cached weak read.
            immutable_json(self.root / 'interface_decisions' / (digest(decision) + '.json'), decision)
            read = self.measure(source, view, by_plan[choice['plan']], purpose)
            native.update(read['native']); decisions.append(decision); reads.append(read)
        return {'native': native, 'decisions': decisions, 'reads': reads,
                'fallback_executed': False, 'model_parameters_updated': False}

    def verify_saved(self, source, library, purpose, result):
        """Audit saved cell predictions without permitting a generation."""
        verify(library, 'snapshot_sha256')
        views = {v['view']: v for v in self.views(source)}
        measured = {read['view']: read for read in result['reads']}
        decisions = {d['view']: d for d in result['decisions']}
        if set(decisions) != set(views) or len(decisions) != len(result['decisions']):
            raise BudgetError('A saved interface prediction lost its pre-read choices')
        required = {name for name, v in views.items() if not v['pre_generation_domain_refusal']}
        if set(measured) != required or len(measured) != len(result['reads']):
            raise BudgetError('A saved interface prediction lost required actual reads')
        native = {}
        for name, view in views.items():
            if name not in required:
                if decisions[name].get('pre_generation_domain_refusal') is not True:
                    raise BudgetError('A saved public domain refusal lost its declaration')
                native.update({task: {'handled': False, 'answer': None, 'fallback_executed': False,
                    'reason': 'Explicit public regime outside frozen legal F domain'} for task in view['native_tasks']})
                continue
            read = measured[name]
            decision = decisions[name]
            decision_path = self.root / 'interface_decisions' / (digest(decision) + '.json')
            if (decision.get('source') != source['key'] or decision.get('arm') != library['arm']
                    or decision.get('library_sha256') != library['snapshot_sha256']
                    or decision['choice']['plan'] != read['plan'] or not decision_path.exists()
                    or json.loads(decision_path.read_text()) != decision):
                raise BudgetError('A saved interface read differs from its sealed prior choice')
            plan = next((p for p in view['plans'] if p['name'] == read['plan']), None)
            if plan is None or read['raw_read_version'] != plan['version'] or read['channel_version'] != self.channel_version(plan):
                raise BudgetError('A saved interface prediction belongs to a different actual pipeline')
            directory = self.root / 'interface_reads' / digest(read['logical_call_id'])
            task = json.loads((directory / 'task.json').read_text())
            if (read['task_sha256'] != digest(task) or task['source_public_sha256'] != digest(source)
                    or task['purpose'] != purpose or task['source'] != source['key']
                    or digest(json.loads((directory / 'decoded.json').read_text())) != digest(read)):
                raise BudgetError('A saved interface prediction lost its source-bound decode artifact')
            self.physical_verifier(identity=read['physical_call_id'], source=source['key'], purpose=purpose,
                content_sha256=read['response_content_sha256'], usage=read['usage'], finish_reason=read['response_finish_reason'])
            native.update(read['native'])
        if result['native'] != native:
            raise BudgetError('Saved interface native answers differ from actual decoded reads')
