"""Source-only correct-kernel frontier for case-grounding research.

The first two mothers are a development frontier. The other two original TRAIN
facts/annotations remain outside teacher requests until their controller freeze.
This does not reopen the previous three-case pilot or any full experiment.
"""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path

from experiments import legal_skill_evolution_execution_kernel_bank as old
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.span_compiler import CALLS, METHODS


ROOT = old.ROOT
RUN = 'legal_skill_evolution_grounding_frontier_20261114'
OUT = ROOT / 'artifacts' / RUN
TARGETS = [('a51930fd', '152(b)(1)', 'dependent_disqualification'),
    ('8175fcb9', '63(c)(6)(A)', 'separate_return_itemization_gate'),
    ('743ac2e5', '7703(a)(2)', 'legal_separation_status'),
    ('a3080e73', '63(f)(2)(A)', 'taxpayer_blind_year_end')]
SYSTEM = '''Acquire the FOUR supplied statutory predicates as common correct
legal kernels. No tools. Future case facts, question entity names, native labels
and answers are withheld. These kernels are shared with every execution control;
this request cannot establish an independent rule-acquisition advantage.

Keep actual source semantics. Programs are complete pure modules with
apply(inputs,premises), returning {handled:boolean,answer:string|null}, using
Entailment/Contradiction only when supported. Use explicit unresolved/null for
unread or uncovered information. The same original SARA finite-case semantics
applies; a resolved finite fact extraction and a neural extraction failure are
different. Do not impose an extra explicit-world-exhaustiveness gate, fabricate
events, infer undisclosed roles, or substitute missing fields with False/zero.

The target clauses are respectively dependent disqualification, the married
separate-return/either-spouse-itemizes standard-deduction gate, legal separation
under a decree, and the taxpayer's own year-end blindness condition. Cover the
actual target predicate, not all surrounding statute conclusions. The blind
predicate is the A condition, not a request to compute the full dollar deduction.
Source statements and benchmark-native annotations are not interchangeable.

Input fields must be case observations: queried person/year, directed explicit
qualifying-child/relative givens with their taxpayer and year, factual marriage
and legal-separation events/dates, stated return and itemization records, and
explicit blindness interval/onset/status facts as appropriate. Do not ask a reader
to decide the final target clause or provide a statutory legal answer. Preserve
the orientation of who is dependent OF whom and whose itemization matters.
An explicitly GIVEN legal intermediate predicate can be consumed as given;
do not invent missing qualifying-child conditions or additional clinical tests.
Distinguish itemized deduction eligibility/amount from actual election/itemization
where the source requires the latter; explain a genuine semantic ambiguity in
rationale instead of guessing a later case. A target query is not proof of its
own premise. Raw date normalization and source-explicit persistent intervals are
allowed. Unknown ending dates are not a fabricated closing date.

Use the original output schema. input_fields_json maps port names to
{type,description}. Describe exact array/object member schemas in descriptions.
Each kernel has exactly the supplied name and target query_clause, scope
exact_clause, and a verbatim source_quote. All statutory tests/thresholds remain
in the kernel, not a factual binding adapter. No imports, nested definitions,
lambdas, network/files, source IDs or entity-name branches. Shared law-free
calendar primitives and allowed Python calls are included. Compact code only.
'''


def read(p):
    return json.loads(p.read_text())


def prepare():
    if (OUT / 'protocol.json').exists():
        return read(OUT / 'protocol.json')
    public = read(ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')
    sources = [next(s for s in public if s['key'].split(':')[1].startswith(prefix)) for prefix, _, _ in TARGETS]
    assert all(s['split'] == 'train' for s in sources)
    task = {'source_only_targets': [{'source_id': s['key'], 'query_clause': clause,
        'kernel_name': name, 'source_text': s['views'][0]['public']['source_text']}
        for s, (_, clause, name) in zip(sources, TARGETS)],
        'future_case_facts_and_native_annotations_absent': True,
        'shared_calendar_code': (ROOT / 'legal_skill_guard/skill_evolution/calendar_ops.py').read_text()}
    before = old.rows(); assert not any(r[6] == 'reserved' for r in before)
    immutable_json(OUT / 'teacher_task.json', task)
    immutable_json(OUT / 'ledger_before_row_hashes.json', {r[0]: digest(r) for r in before})
    files = [Path(__file__), ROOT / 'legal_skill_guard/skill_evolution/span_compiler.py',
        ROOT / 'legal_skill_guard/skill_evolution/span_compiler_worker.py',
        ROOT / 'legal_skill_guard/skill_evolution/calendar_ops.py',
        ROOT / 'legal_skill_guard/skill_evolution/clients.py',
        ROOT / 'legal_skill_guard/skill_evolution/ledger.py']
    for f in files:
        dst = OUT / 'source_snapshot' / f.relative_to(ROOT)
        dst.parent.mkdir(parents=True, exist_ok=True); dst.write_bytes(f.read_bytes())
    previous = read(ROOT / 'artifacts/legal_skill_evolution_case_observation_20261114/protocol.json')
    p = {'run_id': RUN, 'same_goal': True, 'goal_complete': False,
        'sources': [s['key'] for s in sources], 'development_mothers': [s['key'] for s in sources[:2]],
        'frozen_transfer_mothers': [s['key'] for s in sources[2:]],
        'historical_original_TRAIN_exposure_disclosed': True,
        'kernel_definitions_all_four_exposed': True, 'case_facts_and_labels_not_in_teacher_task': True,
        'new_sources': 0, 'full_training_DEV_TEST': False,
        'teacher_profile': previous['teacher_profile'], 'executor_profile': previous['executor_profile'],
        'shared_kernel_acquisition_planned': 1,
        'source_sha256': {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
        'task_sha256': digest(task)}
    immutable_json(OUT / 'protocol.json', p)
    return p


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('phase', choices=['preflight', 'acquire'])
    phase = parser.parse_args().phase
    with (ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        p = prepare()
        for name, h in p['source_sha256'].items():
            assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == h
        assert digest(read(OUT / 'teacher_task.json')) == p['task_sha256']
        system = SYSTEM + '\nAllowed calls: ' + ','.join(sorted(CALLS)) + '\nAllowed attributes: ' + ','.join(sorted(METHODS))
        user = json.dumps(read(OUT / 'teacher_task.json'), ensure_ascii=False, separators=(',', ':'))
        issues = old.prior.strict_output_schema_issues(old.SCHEMA)
        size = len(old.prior.render_structured_codex_prompt(system, user))
        assert not issues and size <= old.prior.CODEX_TURN_INPUT_CHARACTER_LIMIT
        immutable_json(OUT / 'preflight.json', {'schema_issues': issues, 'request_characters': size,
            'no_case_facts_or_native_annotations_in_task': True})
        if phase == 'acquire' and not (OUT / 'teacher.json').exists():
            ledger = EvolutionLedger(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3', run_id=RUN,
                sources={'train': p['sources'], 'dev': [], 'test': []}, binding=digest(p))
            value = FrozenTeacher(ledger, OUT, p['teacher_profile']).propose(RUN + ':common_correct_kernels',
                source_ids=p['sources'], system_prompt=system, user_prompt=user, output_schema=old.SCHEMA)
            immutable_json(OUT / 'teacher.json', value)
            print('Source-only common-kernel frontier saved', flush=True)


if __name__ == '__main__':
    main()
