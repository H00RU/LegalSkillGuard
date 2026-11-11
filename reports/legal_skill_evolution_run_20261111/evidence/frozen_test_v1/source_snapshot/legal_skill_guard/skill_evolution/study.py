"""Fixed native studies: immutable first attempts, bounded updates and resume."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from statistics import mean
import time
import jsonschema

from legal_skill_guard.rr.checkpoint import immutable_json
from .objects import Library, Skill, digest, apply_revision_package
from .ledger import EvolutionLedger
from .clients import FrozenExecutor, FrozenTeacher, GenerationHold
from legal_skill_guard.rr.client import WireError
from legal_skill_guard.rr.ledger import BudgetError
from .controlled import add_controlled
from .native import grade_view
from .runtime import FrozenReads, SkillRuntime, retrieve
from .revisions import ReplayBudget, VersionTable, observe_transfer, trigger_revision_reachability
from .teacher import compile_block
from .proposal_batch import prepare_context, propose_context
from . import patterns

PILOT_ARMS = ('Full', 'FreeEvolution', 'AllPorts+CoRev', 'Lift+GenericJoint')


def load_json(path):
    return json.loads(Path(path).read_text())


class Study:
    def __init__(self, root, profile, *, stage='pilot'):
        self.root, self.profile, self.stage = Path(root), profile, stage
        self.folder = self.root / profile['artifacts']
        manifest = load_json(self.root / 'reports/legal_skill_evolution_plan_20261111/candidate_source_manifest.json')
        self.source_ids = {p: [r['key'] for rows in manifest['datasets'].values() for r in rows[p]]
                           for p in ('train', 'dev', 'test')}
        prepared = self.root / 'artifacts/legal_skill_evolution_20261111/prepared/train'
        records, self.grading = load_json(prepared / 'public.json'), load_json(prepared / 'grading.json')
        if stage == 'pilot':
            records, self.grading = add_controlled(records, self.grading, load_json(self.root /
                'reports/legal_skill_evolution_plan_20261111/CONTROLLED_LAYER_EVIDENCE.json'))
        elif stage != 'formal':
            raise ValueError('Unknown native study stage')
        self.records = {r['key']: r for r in records}
        pilot = load_json(self.root / 'reports/legal_skill_evolution_plan_20261111/pilot_source_manifest.json')
        if stage == 'pilot':
            self.order = [r['key'] for r in pilot['source_sequence']]
            self.batches = [self.order[i:i + 5] for i in range(0, 20, 5)]
            self.arms = PILOT_ARMS
        else:
            self.batches = [[r['source_key'] for r in b['sources']] for b in manifest['source_sequence']]
            self.order = [key for batch in self.batches for key in batch]
            self.arms = tuple(profile['arms'])
            if len(self.batches) != 8 or any(len(b) != 16 for b in self.batches):
                raise ValueError('The fixed formal order must contain 8 batches of 16 parents')
            if len(self.order) != 128 or set(self.order) != set(self.source_ids['train']):
                raise ValueError('The formal order must cover every fixed TRAIN parent exactly once')
            dev = self.root / 'artifacts/legal_skill_evolution_20261111/prepared/dev'
            self.dev_records = {r['key']: r for r in load_json(dev / 'public.json')}
            self.dev_grading = load_json(dev / 'grading.json')
            if set(self.dev_records) != set(self.source_ids['dev']):raise ValueError('DEV parents differ from the fixed manifest')
        if not set(self.order) <= set(self.source_ids['train']):
            raise ValueError('Pilot is not entirely in the pre-fixed TRAIN manifest')
        self.ledger = EvolutionLedger(self.root / 'artifacts/rr_v2_preflight/research_ledger.sqlite3',
            run_id=profile['run_id'], sources=self.source_ids, binding=profile['generation_binding'],
            teacher_concurrency=profile.get('teacher_proposal_workers', 1))
        self.executor = FrozenExecutor(self.ledger, self.folder, profile['executor'])
        self.executor.exact_replay_roots = []
        for relative in profile.get('exact_replay_profiles', []):
            prior = load_json(self.root / relative)
            if digest(prior['executor']) != digest(profile['executor']):
                raise ValueError('Raw-output reuse requires the identical complete frozen executor profile')
            self.executor.exact_replay_roots.append(self.root / prior['artifacts'])
        self.reads = FrozenReads(self.executor)
        self.runtime = SkillRuntime(self.reads)
        self.teacher = FrozenTeacher(self.ledger, self.folder, profile['teacher'])

    def library_path(self, arm, batch):
        return self.folder / arm / ('B' + str(batch) + '.json')

    def initialize(self):
        for arm in self.arms:
            path = self.library_path(arm, 0)
            if path.exists():
                if Library.load(path).skills:
                    raise ValueError('All formal/pilot arms start from their own empty library')
            else:
                Library().save(path)

    def parent(self, identity, library, *, retrieval_sets=None, purpose='skill_actor'):
        if purpose not in ('skill_actor', 'skill_replay', 'skill_dev'):raise ValueError('Unsupported unfrozen evaluation purpose')
        source = (self.dev_records if purpose == 'skill_dev' else self.records)[identity]
        grading = self.dev_grading if purpose == 'skill_dev' else self.grading
        results = []
        for view in source['views']:
            retrieval = retrieval_sets.get(view['id']) if retrieval_sets else None
            view_path = self.folder / 'view_results' / (digest({'source': identity,
                'view': view, 'library_hash': library.hash, 'retrieved': retrieval, 'purpose': purpose}) + '.json')
            if view_path.exists():
                results.append(load_json(view_path))
                continue
            try:
                execution = self.runtime.run(source, view, library, purpose=purpose,
                    retrieved=retrieval)
                score = grade_view(source['dataset'], view, grading[identity][view['id']],
                                   execution['answer'], execution['evidence_sentence_ids'])
            except (ValueError, WireError, jsonschema.ValidationError) as error:
                # A genuinely pending dispatch must be reconciled, never
                # treated as a terminal generation failure or silently retried.
                with self.ledger.transaction() as db:
                    if db.execute("select 1 from calls where status='reserved'").fetchone():raise
                execution = {'answer': None, 'events': [], 'fallback': False,
                    'core_executed': False, 'error': type(error).__name__ + ': ' + str(error)}
                score = {'valid': False, 'correct': False, 'grade': 0.0, 'metric': 'failed_native_attempt'}
            result = {'view': view['id'], 'controlled': view.get('controlled_diagnostic', False),
                      'execution': execution, 'score': score}
            immutable_json(view_path, result)
            results.append(result)
        native = [r for r in results if not r['controlled']]
        def aggregate(rows):
            values = [r['score']['grade'] for r in rows]
            return None if any(v is None for v in values) else mean(values)
        return {'source': identity, 'dataset': source['dataset'], 'library_hash': library.hash,
            'views': results, 'native_grade': aggregate(native),
            'selection_grade': aggregate(results),
            'selection_protocol': self.profile.get('selection_grade', 'native_views_mean_within_parent'),
            'native_core_correct': sum(r['score']['correct'] and r['execution']['core_executed'] for r in native),
            'native_fallback_views': sum(r['execution']['fallback'] for r in native)}

    def initial_batch(self, arm, batch):
        keys = self.batches[batch - 1]
        library = Library.load(self.library_path(arm, batch - 1))
        path = self.folder / arm / ('initial_B' + str(batch) + '.json')
        binding = {'batch': batch, 'arm': arm, 'source_ids': keys, 'library_hash': library.hash}
        if path.exists():
            saved = load_json(path)
            if saved['binding'] != binding:raise ValueError('Frozen first-attempt batch identity changed')
            return saved
        result = []
        for key in keys:
            source_path = self.folder / arm / ('initial_B' + str(batch)) / (digest(key) + '.json')
            if source_path.exists():
                prior = load_json(source_path)
                if prior['source'] != key or prior['library_hash'] != library.hash:
                    raise ValueError('Saved first-attempt source belongs to another frozen library')
                result.append(prior)
                continue
            result.append(self.parent(key, library))
            immutable_json(source_path, result[-1])
            print(json.dumps({'stage': self.stage + '_first_attempt', 'arm': arm, 'batch': batch,
                'source': key, 'native_grade': result[-1]['native_grade'],
                'core_correct': result[-1]['native_core_correct']}, ensure_ascii=False), flush=True)
        value = {'binding': binding, 'results': result}
        immutable_json(path, value)
        return value

    def feedback(self, identities, current):
        return [{'source': key, 'annotations': self.grading[key],
                 'execution': current[key]} for key in identities]

    def update(self, arm, batch):
        path = self.folder / arm / ('update_B' + str(batch) + '.json')
        if path.exists():
            saved = load_json(path)
            if Library.load(self.library_path(arm, batch)).hash != saved['new_library_hash']:
                raise ValueError('Committed update receipt and library differ')
            return saved
        context = prepare_context(self, arm, batch)
        old, current = context['old'], context['current']
        trigger, history, cohort = context['trigger'], context['history'], context['cohort']
        queue, teacher_path = context['queue'], context['teacher_path']
        generic = arm == 'Lift+GenericJoint'
        response = propose_context(self, context)
        proposal = response['value']
        immutable_json(teacher_path, response)
        for block in proposal['blocks'][:3 - len(queue)]:
            queue.append({'raw_block': block})
        prior_logical = self.profile.get('prior_logical_replay_executions', {}).get(arm + ':' + str(batch), 0)
        budget, tables = ReplayBudget(logical_executions=prior_logical), []
        new_parent_executions = 0
        best = None
        for index, candidate in enumerate(queue):
            try:
                revisions = candidate.get('revisions') or compile_block(candidate['raw_block'], old,
                    {k: self.records[k] for keys in self.batches[:batch] for k in keys}, arm)
                budget.admit_block(len(revisions), len(cohort))
                full = apply_revision_package(old, revisions, old.hash)
                retrieval = {key: {v['id']: list(dict.fromkeys(retrieve(full, self.records[key], v) +
                    retrieve(old, self.records[key], v))) for v in self.records[key]['views']} for key in cohort}
                table = VersionTable(tuple(r['new_hash'] for r in revisions), tuple(trigger), tuple(history))
                tokens = {}
                candidate_path = self.folder / arm / ('B' + str(batch) + '_candidates') / (str(index) + '.json')
                existing = load_json(candidate_path) if candidate_path.exists() else None
                if existing and digest(existing.get('revisions')) != digest(revisions):
                    raise ValueError('Saved candidate differs from the exact old/new revisions')
                if existing and existing.get('selection_exclusion'):
                    tables.append(existing)
                    continue
                if not existing:
                    proof = trigger_revision_reachability(old, full, retrieval, trigger,
                                                         [r['skill_id'] for r in revisions])
                    if not proof['any_changed_reachable']:
                        receipt = {**candidate, 'revisions': revisions, 'table': table.export(),
                            'selected_mask': None, 'read_tokens': {},
                            'selection_exclusion': {'reason': 'provably_no_trigger_effect', 'proof': proof,
                                'unmeasured_version_outcomes': 'unknown',
                                'joint_mechanism_validation': False}}
                        tables.append(receipt)
                        immutable_json(candidate_path, receipt)
                        continue
                if existing and 'table' in existing:
                    for cell in existing['table']['mixed_version_table']:
                        table.observe(cell['mask'], cell['source'], cell['native_parent_grade'], cell['trace'])
                    tokens = {int(m): n for m, n in existing['read_tokens'].items()}
                else:
                    for mask in range(1 << len(revisions)):
                        library = apply_revision_package(old,
                            [r for i, r in enumerate(revisions) if mask & (1 << i)], old.hash)
                        tokens[mask] = 0
                        for key in cohort:
                            new_parent_executions += 1
                            result = self.parent(key, library, retrieval_sets=retrieval[key])
                            table.observe(mask, key, result['selection_grade'], result)
                            tokens[mask] += sum(e.get('usage', {}).get('total_tokens', 0)
                                for view in result['views'] for e in view['execution']['events'] if e.get('kind') == 'READ_LOCAL')
                chosen = table.choose({m: tokens[m] - tokens[0] for m in tokens})
                receipt = {**candidate, 'revisions': revisions, 'table': table.export(), 'selected_mask': chosen,
                           'read_tokens': tokens}
                if chosen is not None:
                    gain = mean(table.cells[chosen, k] - table.cells[0, k] for k in trigger)
                    rank = (gain, -chosen.bit_count(), -(tokens[chosen] - tokens[0]), -index)
                    if best is None or rank > best['rank']:
                        best = {'rank': rank, 'revisions': revisions, 'mask': chosen, 'table': table, 'index': index}
                if candidate.get('pattern_id'):
                    receipt['transplant_classification'] = table.classify()
                tables.append(receipt)
            except Exception as error:
                if isinstance(error, (GenerationHold, BudgetError)):
                    raise
                with self.ledger.transaction() as db:
                    if db.execute("select 1 from calls where status='reserved'").fetchone():raise
                tables.append({**candidate, 'error': type(error).__name__ + ': ' + str(error),
                               'independent_grade': None, 'unmeasured_assignments': 'unknown'})
            immutable_json(self.folder / arm / ('B' + str(batch) + '_candidates') /
                           (str(index) + '.json'), tables[-1])
        new = deepcopy(old)
        learned = []
        if best:
            new = apply_revision_package(old, [r for i, r in enumerate(best['revisions'])
                if best['mask'] & (1 << i)], old.hash)
            if arm in ('Full', 'CoRevOnly', 'AllPorts+CoRev', 'Lift+GenericJoint'):
                learned = patterns.learn(new, old, best['revisions'], best['table'], best['mask'], generic=generic)
        for receipt in tables:
            if receipt.get('pattern_id') and 'table' in receipt:
                memory = next(p for p in new.revision_patterns if p['id'] == receipt['pattern_id'])
                exported = receipt['table']
                table = VersionTable(tuple(exported['revision_hashes']), tuple(exported['trigger']), tuple(exported['history']))
                for cell in exported['mixed_version_table']:
                    table.observe(cell['mask'], cell['source'], cell['native_parent_grade'], cell['trace'])
                observe_transfer(memory, receipt['verified_context'], table)
        new.provisional_edits.extend({'batch': batch, 'candidate_index': i,
            'raw_block': t.get('raw_block'),
            'revisions': t.get('revisions'), 'table': t.get('table'), 'error': t.get('error'),
            'selection_exclusion': t.get('selection_exclusion')}
            for i, t in enumerate(tables))
        new.save(self.library_path(arm, batch))
        value = {'batch': batch, 'arm': arm, 'old_library_hash': old.hash, 'new_library_hash': new.hash,
            'teacher_request_sha256': response['request_sha256'], 'candidate_blocks': len(queue),
            'logical_candidate_parent_executions': prior_logical + new_parent_executions,
            'reserved_logical_candidate_parent_allowance': budget.logical_executions,
            'prior_logical_candidate_parent_executions': prior_logical,
            'logical_candidate_parent_executions_this_validation': new_parent_executions,
            'selected_candidate': best['index'] if best else None, 'selected_mask': best['mask'] if best else None,
            'learned_pattern_ids': learned, 'skill_count': len(new.skills), 'pattern_count': len(new.revision_patterns)}
        immutable_json(path, value)
        print(json.dumps({'stage': self.stage + '_update', **value}, ensure_ascii=False), flush=True)
        return value

    def run(self):
        self.initialize()
        for batch in range(1, 5):
            for arm in self.arms:self.initial_batch(arm, batch)
            for arm in self.arms:self.update(arm, batch)
