"""One concrete learner-synthesis attempt from preserved real TRAIN evidence.

This is a proposal, not a verified mechanism. No executor experiment is queued
by a successful transport response; proposed code is reviewed before use.
"""
import fcntl
import json
from pathlib import Path
import sqlite3

from experiments.legal_skill_evolution_refutation_learning import ROOT, read, sha
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.teacher_transport import INSTRUCTION, pack

RUN = 'legal_skill_evolution_learning_operator_proposal_20261113'
OUT = ROOT/'artifacts'/RUN
RESULT = record_schema({
    'decision': {'type': 'string', 'enum': ['concrete_candidate', 'no_supported_candidate']},
    'learning_object': {'type': 'string'},
    'mechanism_and_difference': {'type': 'string'},
    'algorithm_steps': {'type': 'array', 'items': {'type': 'string'}},
    'learner_python': {'type': 'string'},
    'real_TRAIN_application': {'type': 'string'},
    'strongest_same_information_control': {'type': 'string'},
    'minimal_comparison_and_rejection_condition': {'type': 'string'},
    'relationship_to_given_prior_work': {'type': 'string'},
    'remaining_gap': {'type': 'string'},
})
SYSTEM = '''Synthesize one executable external legal-skill LEARNING/UPDATE operator
from the supplied existing real TRAIN material. Both language models are frozen.
We need a substantive learning mechanism and its discriminating same-information
comparison, not another source-format interface or a paper name. First establish
one contribution, then a second independent one; neither is currently established.

The current repository has candidate/evidence management but no complete source
production induction operator. Implement what changes the next acquired source
program/library from real evidence. learner_python must contain concrete runnable
Python with an explicit data contract and update entry, not pseudocode or calls to
an undefined synthesizer. Standard-library algorithm code is allowed. Do not run
tools, call other models, access files/network, or inspect held-out material.
Do not hardcode company/source IDs, example positions or answers. No invented laws,
fault injection, extra empirical sources, TEST labels or model-weight training.
An observed rejection does not provide a replacement meaning; unknown stays open.
Deleting all rules or returning unknown is not correct source acquisition.

Keep the same legal-rule acquisition/update/reuse problem and original five tasks.
Do not force capped-fold onto incompatible programs or reproduce its completed
proof/tests. Query-clause guards, literal familial edges and explicit actor roles
already exist. Ordinary source-policy caching, direct role extraction, generic
Python repair, complete helper reuse and ordinary synthesis are strong controls.
Old NQG/source grammars, source attachment, DNF scope, regex residuals, source-check
selection, helper hoisting and local slicing have actual null/equivalence evidence.
Do not rename those objects, recommend unchanged retries, or create another critic.

Mature algorithms are allowed. Ordinary Python expressibility alone does not refute
a legal acquisition reliability/cost contribution. Do not reject ambitious ideas
merely because implementation is difficult or improvement is not guaranteed before
the prototype. We DO need a clear learning object, concrete update algorithm, a
real existing-TRAIN opportunity and a plausible actual difference from the strongest
same-information control. If you cannot supply these, return no_supported_candidate
and name the concrete gap rather than produce an impressive wrapper.

Propose at most one strong candidate. Explain how its execution changes future G,
what actual existing observations it consumes, what it cannot infer, and which
finite prospective result would refute it. The same source, supervision, history,
public fixes, open architecture and comparable cost are available to the control.
Do not demand repeated identical target clauses, all-branch tests, zero fallback,
a preset score gain, or a fundamentally new low-level solver. This response alone
will not count as implementation success, method evidence, or Goal completion.
''' + INSTRUCTION


def run():
    prior = ROOT/'artifacts/legal_skill_evolution_refutation_learning_20261113'
    old = read(prior/'protocol.json')
    inputs = read(prior/'input.json')
    base = ROOT/'artifacts/legal_skill_evolution_open_effect_acquisition_20261113/SourceEffect/compiled.json'
    repaired = ROOT/'artifacts/legal_skill_evolution_effect_slots_20261113/reused_compiler'
    actor_source = read(repaired/'receipt.json')['source']
    sources = old['train_sources'] + [actor_source]
    public = {s['key']: s for s in read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
    task = {'raw_original_TRAIN': [public[k] for k in sources],
            'actual_original_compiler': read(base),
            'actual_current_semantic_reader': read(ROOT/'artifacts/legal_skill_evolution_residual_reader_20261113/seed.json'),
            'actual_source_feedback': inputs['explicit_source_negative_feedback'],
            'actual_supported_and_rejected_interpretations': inputs['training_cases'],
            'known_source_role_operation_meanings': inputs['operations'],
            'public_actor_fix_not_contribution': {'bundle': read(repaired/'bundle.json'),
                'receipt': read(repaired/'receipt.json'), 'source_review': read(repaired/'source_review.json')},
            'current_incomplete_candidate_manager': (ROOT/'legal_skill_guard/skill_evolution/semantic_learning.py').read_text(),
            'focused_skill_literature_and_evidence': Path('/tmp/lsg_fresh_skill_mechanism_20261113.md').read_text(),
            'focused_program_literature_and_evidence': Path('/tmp/lsg_fresh_program_mechanism_20261113.md').read_text(),
            'current_goal': (ROOT/'docs/CURRENT_GOAL.md').read_text()}
    # Literal reports describe old validation but supply no held-out source text,
    # annotations or executable answer tables. Only these five TRAIN enter models.
    user = json.dumps(pack(task), ensure_ascii=False)
    p = {'run_id': RUN, 'same_goal': True, 'goal_complete': False,
         'source_ids': sources, 'teacher_profile': old['teacher_profile'],
         'input_sha256': digest(task), 'system_sha256': digest(SYSTEM),
         'question': 'Can a concrete nontrivial source-constrained program learner be synthesized from existing real evidence, beyond the already tested ordinary repairs?',
         'workload': 'One teacher learner-proposal attempt. No executor experiment auto-starts.',
         'no_new_mechanical_call_cap': True, 'new_sources_or_DEV_TEST': False,
         'implementation_sha256': sha(Path(__file__))}
    immutable_json(OUT/'protocol.json', p)
    immutable_json(OUT/'input.json', task)
    immutable_json(OUT/'request_schema.json', RESULT)
    if not (OUT/'ledger_before.json').exists():
        with sqlite3.connect(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3') as db:
            rows = [list(r) for r in db.execute('select * from calls order by id')]
        assert not any(r[6] == 'reserved' for r in rows)
        immutable_json(OUT/'ledger_before.json', {'rows': rows})
    ledger = EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',
        run_id=RUN, sources={'train': sources, 'dev': [], 'test': []}, binding=digest(p))
    teacher = FrozenTeacher(ledger, OUT, p['teacher_profile'])
    r = teacher.propose(RUN+':one', source_ids=sources, system_prompt=SYSTEM,
                        user_prompt=user, output_schema=RESULT)
    immutable_json(OUT/'teacher.json', r)
    print(json.dumps({'decision': r['value']['decision'],
        'learning_object': r['value']['learning_object'],
        'mechanism_and_difference': r['value']['mechanism_and_difference'],
        'remaining_gap': r['value']['remaining_gap'],
        'elapsed_seconds': r['elapsed_seconds']}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    with (ROOT/'artifacts/rr_v2_preflight/current_learning_operator_proposal.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        run()
