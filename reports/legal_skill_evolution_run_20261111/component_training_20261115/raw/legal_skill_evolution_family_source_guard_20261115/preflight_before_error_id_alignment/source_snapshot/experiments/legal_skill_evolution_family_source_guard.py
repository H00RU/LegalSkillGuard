"""Learn a focused observation repair from actual TRAIN family misreadings.

Two teacher calls update the same real component in independent arms. Original
libraries, source examples and post-decoding failures are preserved. The new
source-token schema annotation compiles only acquired finite lexical guards;
it is not an assertion that matching words establish a relationship or role.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import fcntl
import hashlib
import json
from pathlib import Path

from experiments import legal_skill_evolution_mixed_component_training as train
from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.observation_teacher_transport import pack_task, unpack_task, INSTRUCTION

ROOT = train.ROOT
RUN = 'legal_skill_evolution_family_source_guard_20261115'
OUT = ROOT / 'artifacts' / RUN
COMPONENT = 'family_relationship_residence'
ACQUISITION_PREFIXES = ('1ff7d9', 'a51930')
REUSE_PREFIXES = ('5c29a3',)
EDIT = train.actor.acquisition.EDIT
SCHEMA = record_schema({'rationale': {'type': 'string'}, 'candidates': {'type': 'array', 'minItems': 2,
    'maxItems': 2, 'items': EDIT}})
SYSTEM = '''Repair the actual reusable family observation schema AND conversion
from real source-grounding errors. This is the current legal observation-learning
method, not a new dataset, legal rule or weight update. Use no tools. Both arms
receive identical original TRAIN material, actual errors, both current components,
their same helpers, compiler capacity and resources. No DEV/TEST or new cases.

Return two full alternatives for family_relationship_residence, each with the
existing EDIT fields. Keep the current conversion signature and exact output:
facts,negative_givens,witnesses,complete,reasons. Existing shared_helpers are
prepended unchanged. Pure Python only: no imports, IO, nested functions, classes,
lambdas or recursion. No source/person/company IDs, native answers or case/year
lookup branches. Derive roles and facts from the current source, not examples.

The actual error is substantive: 'Alice and Bob have been married' was labeled
brother/father, with source_basis='explicit_brother'/'explicit_father'; a source_term
containing the marriage sentence passed loose internal consistency. Residence
'shared a home' was fabricated. Marriage never establishes a parent, sibling,
co-residence or birth. Exact quotes alone do not establish their assigned types.
Retain actual explicit son relations and source-stated residence intervals.

Learn source-grounded categorical distinctions and enforce them jointly in the
schema and conversion. A finite literal enum field may use the annotation
"x-source-facts-token":true. The supplied common compiler restricts this enum
to whole tokens/phrases actually present in CURRENT facts, case-insensitively,
and removes the annotation before guided decoding. It never inserts observations.
For example this can project a LEARNED source-cue enum; it is not a predefined
kinship lexicon. OneOf variants may couple relation_type, source_basis and their
actual source cue. Do not annotate canonical categories which are NOT literal
source text. Both arms may use this compiler, any equally expressive schema,
helpers and joint repairs. This facility alone is not a novelty certificate.

Keep unread/null distinct from source-read empty arrays. A source-stated onset
does not require a fabricated end date. Do not infer a residence place from
marriage. Support each emitted relation's direction from source evidence; fields
agreeing with each other are insufficient. Unsupported/paraphrased observations
must remain unresolved rather than guessed. Do not force empty arrays for an
unknown read, weaken source checks, or add default positive facts. Keep source
facts and question separate. The source-token projection is a necessary lexical
guard only, not semantic proof. Return compact valid inline JSON schemas with
no $ref; requested candidates must be complete executable component versions.
'''


def prepare():
    old = train.read(train.OUT / 'protocol.json')
    bank = train.actor.acquisition.previous.parent.OUT
    public = {s['key']: s for s in train.read(bank / 'SARA_corrected_TRAIN_views.json')}
    selected = [sid for sid in public if any(sid.startswith('SARA_v2_Binary:' + p) for p in ACQUISITION_PREFIXES)]
    reuse = [sid for sid in public if any(sid.startswith('SARA_v2_Binary:' + p) for p in REUSE_PREFIXES)]
    assert len(selected) == 2 and len(reuse) == 1 and not set(selected) & set(reuse)
    checkpoint = train.read(train.OUT / 'B8/checkpoint.json')
    libraries = {a: train.read(ROOT / checkpoint['libraries'][a]['path']) for a in train.ARMS}
    seeds = {a: next(c for c in l['components'] if c['id'] == COMPONENT) for a, l in libraries.items()}
    replay = train.read(ROOT / 'artifacts/legal_skill_evolution_observation_TRAIN_replay_20261115/result.json')
    examples = []
    for sid in selected:
        assert public[sid]['split'] == 'train'
        observations = {}
        for arm in train.ARMS:
            if sid.startswith('SARA_v2_Binary:1ff7'):
                row = train.read(ROOT / 'artifacts/legal_skill_evolution_literal_guard_probe_20261115' / arm / 'after.json')
            else:
                row = next(r for r in replay['rows'] if r['source'] == sid and r['candidate'] == arm)
            observations[arm] = row['observation'][COMPONENT]
        examples.append({'source': sid, 'original_public': public[sid]['views'][0]['public'],
                         'actual_observations': observations})
    task = {'current_components_both': seeds, 'shared_helpers_by_arm': {a: l['shared_helpers'] for a, l in libraries.items()},
        'actual_parent_hash_by_arm': {a: digest(c) for a, c in seeds.items()},
        'original_TRAIN_examples': examples,
        'error_feedback_by_id': {'actual_nonkinship_hallucination': examples[0],
            'preserve_explicit_son_source': examples[1]},
        'actual_partial_source_reviews': train.read(OUT / 'actual_unchecked_sibling_error.json'),
        'source_schema_compiler_code': (ROOT / 'legal_skill_guard/skill_evolution/literal_statutory_givens.py').read_text(),
        'current_task_excludes_fixed_reuse_source': True,
        'old_B8_exposure_disclosed_not_new_blind_acquisition': True,
        'all_output_candidates_receive_same_source_semantic_checks': True}
    packed = pack_task(task)
    assert unpack_task(packed) == task
    immutable_json(OUT / 'teacher_task.json', task)
    files = [Path(__file__), train.OUT / 'protocol.json', train.OUT / 'B8/checkpoint.json']
    files += [ROOT / v['path'] for v in checkpoint['libraries'].values()]
    files += sorted((ROOT / 'legal_skill_guard/skill_evolution').glob('*.py'))
    files += [OUT / 'teacher_task.json', OUT / 'actual_unchecked_sibling_error.json']
    protocol = {'run_id': RUN, 'same_goal': True, 'sources': old['sources'],
        'current_repair_acquisition': selected, 'fixed_reuse_excluded_from_this_task': reuse,
        'not_fresh_blind_split_original_B8_exposure': True,
        'teacher_profile': old['teacher_profile'], 'executor_profile': old['executor_profile'],
        'schema': SCHEMA, 'same_compiler_both_arms': True,
        'source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        'no_new_sources_seeds_or_model_configuration': True, 'DEV_TEST_accessed': False,
        'not_a_whole_training_or_DEV_rerun': True, 'goal_complete': False}
    immutable_json(OUT / 'protocol.json', protocol)
    for p in files:
        target = OUT / 'source_snapshot' / p.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_bytes(p.read_bytes())
        else:
            assert target.read_bytes() == p.read_bytes()
    return protocol, packed


def acquire():
    protocol = train.read(OUT / 'protocol.json')
    for p, sha in protocol['source_sha256'].items():
        assert hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == sha, p
    task = train.read(OUT / 'teacher_task.json')
    assert not strict_output_schema_issues(SCHEMA)
    ledger = EvolutionLedger(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3', run_id=RUN,
        sources={'train': protocol['sources'], 'dev': [], 'test': []}, binding=digest(protocol), teacher_concurrency=2)
    def one(arm):
        target = OUT / arm / 'teacher.json'
        if target.exists():
            return
        mode = ('Propose paired categorical/semantic component versions with error-to-constraint justification.'
                if arm == 'CoverageRecombine' else 'Propose the strongest ordinary teacher repairs; all the same compiler and representations are available. Do not weaken this control.')
        value = FrozenTeacher(ledger, OUT, protocol['teacher_profile']).propose(RUN + ':' + arm + ':family_repair',
            source_ids=protocol['current_repair_acquisition'], system_prompt=SYSTEM + '\n' + mode + '\n' + INSTRUCTION,
            user_prompt=json.dumps(pack_task({**task, 'this_arm': arm}), ensure_ascii=False, separators=(',', ':')),
            output_schema=SCHEMA)
        immutable_json(target, value)
        print(json.dumps({'teacher_saved': arm}), flush=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(one, arm) for arm in train.ARMS]
        for f in futures:
            f.result()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('prepare', 'acquire'))
    args = parser.parse_args()
    if args.phase == 'prepare':
        protocol, task = prepare()
        print(json.dumps({'acquisition': protocol['current_repair_acquisition'],
            'fixed_reuse_not_in_task': protocol['fixed_reuse_excluded_from_this_task'],
            'packed_characters': len(json.dumps(task)), 'new_model_calls': 0}), flush=True)
    else:
        with (ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquire()
