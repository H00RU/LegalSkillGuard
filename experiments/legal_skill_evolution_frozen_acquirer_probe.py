"""Four fixed original-TRAIN mothers with already acquired frozen programs.

Separates independent C/Free acquisition from execution on shared learned assets.
No new teacher or update fitting. Reuses exact actual reading histories first;
all unscored variants are saved before native labels are opened for scoring.
"""
import argparse
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path
import sqlite3

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.open_acquisition import observe
from legal_skill_guard.skill_evolution.query_refinement import select_query
from experiments.legal_skill_evolution_query_refinement_train import objective
from experiments.legal_skill_evolution_diagnosed_update_train import source_material
from experiments.legal_skill_evolution_open_acquisition_train import evaluate_source

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT / 'artifacts/legal_skill_evolution_query_refinement_20261114'
RUN = 'legal_skill_evolution_frozen_acquirer_probe_20261114'
OUT = ROOT / 'artifacts' / RUN
PUBLIC = ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
GRADING = PUBLIC.with_name('grading.json')
LEDGER = ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
VARIANTS = ('C_active', 'Free_active', 'C_eager', 'Free_eager')
read = lambda path: json.loads(path.read_text())
arm_for = lambda variant: 'ConstraintAcquire' if variant.startswith('C_') else 'FreeUpdate'


class MissingActualReading(RuntimeError):
    pass


class CachedOnly:
    def __init__(self, actual):
        self.actual = actual
        self.config = actual.config
    def tokenize(self, *args, **kwargs):
        return self.actual.tokenize(*args, **kwargs)
    def generate(self, call_id, **kwargs):
        raise MissingActualReading(json.dumps({'call_id': call_id, 'source': kwargs['source'],
            'messages_sha256': digest(kwargs['messages']), 'not_a_failed_model_request': True}))


def prepare():
    if (OUT / 'protocol.json').exists():
        return read(OUT / 'protocol.json')
    assert read(PARENT / 'TERMINAL_PRESERVATION.json')['run_boundary_terminal']
    prior = read(PARENT / 'protocol.json')
    public = read(PUBLIC)
    excluded = set(prior['acquisition_sources'] + prior['reuse_sources'])
    excluded.update(s['source'] for s in read(PARENT / 'shared/initial_library.json')['spec']['seeds'])
    # Freeze by membership/order, before opening any selected view's labels.
    selected = [s for s in public if s['dataset'] == 'ContractNLI' and s['key'] not in excluded][:4]
    assert len(selected) == 4
    with sqlite3.connect('file:' + str(LEDGER) + '?mode=ro', uri=True) as db:
        rows = db.execute('select * from calls order by id').fetchall()
    assert not any(r[6] == 'reserved' for r in rows)
    files = [Path(__file__), ROOT / 'experiments/legal_skill_evolution_query_refinement_train.py',
        ROOT / 'experiments/legal_skill_evolution_diagnosed_update_train.py',
        ROOT / 'experiments/legal_skill_evolution_open_acquisition_train.py',
        *sorted((ROOT / 'legal_skill_guard/skill_evolution').glob('*.py')),
        *sorted((ROOT / 'tests').glob('test_skill_evolution*.py'))]
    data = [PUBLIC, GRADING, PARENT / 'protocol.json', PARENT / 'TERMINAL_PRESERVATION.json',
            PARENT / 'C_active/learned.json', PARENT / 'Free_active/learned.json',
            PARENT / 'base.json', PARENT / 'grammar.json', PARENT / 'shared/initial_library.json']
    p = {'run_id': RUN, 'same_goal': True, 'goal_complete': False,
        'sources': [s['key'] for s in selected],
        'selection': 'First4 original TRAIN ContractNLI mothers outside current8 acquisition, last2 reuse and shared seeds; no score-based selection',
        'old_full_TRAIN_and_earlier_study_exposure_retained': True,
        'not_new_blind_test': True, 'variants': list(VARIANTS),
        'question': 'Does the whole frozen independently acquired C program help relative to Free? Eager execution shares each respective learned program and does not constitute independent acquisition.',
        'same_selector_and_eager_access_for_both': True,
        'no_teacher_updates_refitting_or_new_sources': True,
        'no_new_full_training_DEV_TEST_or_paper': True,
        'executor_profile': prior['executor_profile'],
        'query_ids': prior['query_ids_from_actual_training'],
        'source_sha256': {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
        'data_sha256': {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in data}}
    for item in ('base.json', 'grammar.json', 'shared/initial_library.json'):
        immutable_json(OUT / item, read(PARENT / item))
    for arm, variant in [('ConstraintAcquire', 'C_active'), ('FreeUpdate', 'Free_active')]:
        library = read(PARENT / variant / 'learned.json')
        immutable_json(OUT / arm / 'library.json', library)
    immutable_json(OUT / 'selection.json', {'sources': [{k: s[k] for k in ('key', 'parent_id', 'runtime_actor_views_sha256')} for s in selected],
        'selected_before_new_scoring': True, 'old_exposure_disclosed': True})
    immutable_json(OUT / 'ledger_before_row_hashes.json', {r[0]: digest(r) for r in rows})
    for f in files:
        dst = OUT / 'source_snapshot' / f.relative_to(ROOT)
        dst.parent.mkdir(parents=True, exist_ok=True); dst.write_bytes(f.read_bytes())
    immutable_json(OUT / 'protocol.json', p)
    return p


def setup():
    p = prepare()
    for name, sha in {**p['source_sha256'], **p['data_sha256']}.items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != sha:
            raise ValueError('Frozen source/data changed: ' + name)
    ledger = EvolutionLedger(LEDGER, run_id=RUN,
        sources={'train': p['sources'], 'dev': [], 'test': []}, binding=digest(p))
    return p, ledger, {s['key']: s for s in read(PUBLIC) if s['key'] in p['sources']}


def histories(key, source_text, units):
    observations = {}; origins = {}
    for folder in sorted((ROOT / 'artifacts').glob('legal_skill_evolution_*')):
        if folder == OUT:
            continue
        for stage in ('acquisition', 'reuse'):
            for f in (folder / stage).glob('**/' + key.replace(':', '_') + '.json'):
                d = read(f); o = d.get('observation', d)
                if 'visible_inputs' not in o or o.get('counterfactual_only'):
                    continue
                v = o['visible_inputs']
                if v['source_text'] == source_text and v['units'] == units:
                    identity = digest(v); observations.setdefault(identity, o)
                    origins.setdefault(identity, []).append(str(f.relative_to(ROOT)))
    return list(observations.values()), origins


def run(cached_only=False):
    p, ledger, public = setup(); pending = []
    actual_client = FrozenExecutor(ledger, OUT, p['executor_profile'])
    # Exact semantic-history reuse handles batching changes. Exact wire reuse is
    # additionally available for a previously paid identical physical payload.
    actual_client.exact_replay_roots = [f for f in (ROOT / 'artifacts').glob('legal_skill_evolution_*')
                                       if f != OUT and (f / 'calls').exists()]
    client = CachedOnly(actual_client) if cached_only else actual_client
    for key in p['sources']:
        source = public[key]; name = key.replace(':', '_') + '.json'
        pub, units, shared = source_material(OUT, public, key)
        history, origins = histories(key, pub['source_text'], units)
        immutable_json(OUT / 'history_index' / name, {'observations': origins,
            'only_identical_current_text_and_units': True, 'semantics_scope_and_choices_rechecked_by_observe': True})
        for variant in VARIANTS:
            dst = OUT / 'unscored' / variant / name
            if dst.exists():
                history.append(read(dst)['observation']); continue
            library = read(OUT / arm_for(variant) / 'library.json')
            ids = p['query_ids'][arm_for(variant)]
            requests = [{'id': ids[o['name']], 'operation': o['name'], 'unit_ids': [u['id'] for u in units]}
                        for o in library['operations']] if variant.endswith('_eager') else []
            try:
                current = observe(client, RUN + ':' + variant + ':' + key, key, library,
                    source_text=pub['source_text'], units=units, source_output=shared,
                    previous_observations=history, requested_queries=requests,
                    save_event=lambda e: immutable_json(OUT / 'events' / (digest(e['call_id']) + '.json'), e))
                decisions = []
                if variant.endswith('_active'):
                    while True:
                        decision = select_query(library, current, objective(library, source, None),
                            objective_name='unlabeled_core_coverage', query_ids=ids)
                        decisions.append(decision)
                        if decision['query'] is None:
                            break
                        requests.append(decision['query'])
                        current = observe(client, RUN + ':' + variant + ':' + key, key, library,
                            source_text=pub['source_text'], units=units, source_output=shared,
                            previous_observations=[current, *history], requested_queries=requests,
                            save_event=lambda e: immutable_json(OUT / 'events' / (digest(e['call_id']) + '.json'), e))
            except MissingActualReading as missing:
                pending.append({'source': key, 'variant': variant, 'missing': json.loads(str(missing))})
                continue
            immutable_json(dst, {'source': key, 'observation': current, 'query_selection': decisions,
                'labels_used': False, **evaluate_source(library, current, source, None)})
            history.append(current)
            print(json.dumps({'source': key, 'variant': variant, 'unscored_saved': True}), flush=True)
    immutable_json(OUT / ('cached_boundary.json' if cached_only else 'execution_boundary.json'), {
        'cached_only': cached_only, 'missing_first_actual_reads': pending,
        'all_unscored_variants_saved': not pending, 'native_labels_not_opened': True})
    print(json.dumps({'cached_only': cached_only, 'pending_variant_sources': len(pending)}), flush=True)


def score():
    p, _, public = setup()
    assert all((OUT / 'unscored' / v / (k.replace(':', '_') + '.json')).exists()
               for k in p['sources'] for v in VARIANTS)
    grading = read(GRADING)
    for key in p['sources']:
        name = key.replace(':', '_') + '.json'
        for variant in VARIANTS:
            library = read(OUT / arm_for(variant) / 'library.json')
            observation = read(OUT / 'unscored' / variant / name)['observation']
            immutable_json(OUT / 'scores' / variant / name,
                           evaluate_source(library, observation, public[key], grading[key]))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('phase', choices=['prepare', 'cached', 'execute', 'score'])
    phase = parser.parse_args().phase
    with (ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        if phase == 'prepare': prepare()
        elif phase == 'score': score()
        else: run(phase == 'cached')
