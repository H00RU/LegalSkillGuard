"""Source-only common kernels for a fixed, finite original-TRAIN reuse check.

The selected cases require payer/year, directed negative givens, spouse/death,
or service/enrollment joins. No closed pilot is reopened. Both learning arms
and the direct control will share the same checked legal programs.
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
RUN = 'legal_skill_evolution_execution_reuse_20261114'
OUT = ROOT / 'artifacts' / RUN
TARGETS = [
    ('6939fedab0', '3306(a)(1)', 'general_employer'),
    ('1ff7d9eafc', '63(c)(5)', 'dependent_basic_deduction_limit'),
    ('cd2ab8fce3', '2(a)(1)(A)', 'surviving_spouse_death_window'),
    ('250fc5e766', '3306(c)(10)(A)(i)', 'student_service_exception'),
]
SYSTEM = '''Acquire the FOUR target clauses as common executable legal kernels
from the supplied source text. Do not use tools. Case facts, concrete question
entities, native labels and answers are withheld. These are shared components,
not a rule-acquisition comparison or a claim of learning new legal semantics
from the earlier observation library.

Preserve each exact clause's scope and its source dependencies. Do not implement
an unrelated sufficient subrule as a complete native query. Return handled=false
for missing extraction or a genuinely uncovered legal branch. Original SARA
finite-case semantics applies: an explicitly completed source-fact extraction
with no matching predicate can support native finite failure; an unread/null
channel cannot be silently treated as that absence. State exact input contracts
and completion status. Do not add a global explicit-world-exhaustiveness gate.

All statutory tests stay in the legal kernel, not an observation adapter.
Inputs describe raw case events/givens: identified query actors/year, payer and
payee, service kind/place/period and stated payments, directed explicit positive
or negative statutory givens, marriage/death dates, student/enrollment/employment
and institution identities as needed. Do not ask a weak reader for the final
clause's applicability or an eligibility verdict. Preserve direction, time and
same-entity joins. Do not split an undated cross-year payment into fabricated
amounts. If the supplied source requires an intermediate condition that cannot
be determined from these source facts, leave that exact issue explicit.

The targets are general employer paragraph3306(a)(1), applicability of the
dependent basic-deduction limit63(c)(5), the two-previous-years spouse-death
condition2(a)(1)(A), and the student-services-at-the-school exception
3306(c)(10)(A)(i). The death-window target does not ask for every surrounding
surviving-spouse condition. The dependent-limit target asks applicability,
not a dollar deduction. Do not impose a clinical/student/full-spouse condition
outside the specified target. Native explicit intermediate legal givens may be
used as givens, while a query never establishes its own premise.

Each kernel must have exactly the supplied name and query_clause, scope
exact_clause, verbatim source_quote, and a complete pure apply(inputs,premises)
module returning {handled:boolean,answer:Entailment|Contradiction|null}.
input_fields_json maps ports to {type,description}, with concrete member
schemas/status meanings explained for arrays/objects. No imports, nested defs,
lambdas, IO, source IDs or entity-name/year-specific case branches. Shared
calendar primitives are available. Keep code compact.
'''


def read(path):
    return json.loads(path.read_text())


def prepare():
    if (OUT / 'protocol.json').exists():
        return read(OUT / 'protocol.json')
    public = read(ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')
    sources = [next(s for s in public if prefix in s['key']) for prefix, _, _ in TARGETS]
    assert all(s['dataset'] == 'SARA_v2_Binary' and s['split'] == 'train' for s in sources)
    closed = read(ROOT / 'artifacts/legal_skill_evolution_temporal_contract_learning_20261114/protocol.json')
    assert not set(s['key'] for s in sources) & set(closed['sources'])
    task = {'source_only_targets': [{'source_id': s['key'], 'query_clause': clause,
        'kernel_name': name, 'source_text': s['views'][0]['public']['source_text']}
        for s, (_, clause, name) in zip(sources, TARGETS)],
        'case_facts_questions_and_annotations_withheld': True,
        'shared_calendar_code': (ROOT / 'legal_skill_guard/skill_evolution/calendar_ops.py').read_text()}
    before = old.rows()
    assert len(before) == 10619 and not any(r[6] == 'reserved' for r in before)
    immutable_json(OUT / 'teacher_task.json', task)
    immutable_json(OUT / 'ledger_before_row_hashes.json', {r[0]: digest(r) for r in before})
    paths = [Path(__file__), ROOT / 'legal_skill_guard/skill_evolution/clients.py',
             ROOT / 'legal_skill_guard/skill_evolution/ledger.py',
             ROOT / 'legal_skill_guard/skill_evolution/span_compiler.py',
             ROOT / 'legal_skill_guard/skill_evolution/span_compiler_worker.py',
             ROOT / 'legal_skill_guard/skill_evolution/calendar_ops.py']
    for path in paths:
        dest = OUT / 'source_snapshot' / path.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(path.read_bytes())
    protocol = {'run_id': RUN, 'same_goal': True, 'goal_complete': False,
        'sources': [s['key'] for s in sources],
        'selection_rule': 'four existing TRAIN source claims requiring payer/year, directed negative given, spouse/death, school/service joins; fixed before new calls',
        'researcher_has_seen_public_facts': True, 'not_a_new_blind_test': True,
        'not_reopening_closed_three_or_four_mother_studies': True,
        'new_sources': 0, 'full_training_DEV_TEST': False,
        'current_stage': 'common_source_only_kernels_then_offline_semantic_review',
        'common_kernel_teacher_requests_planned': 1,
        'no_executor_before_common_kernel_review': True,
        'teacher_profile': closed['teacher_profile'], 'executor_profile': closed['executor_profile'],
        'task_sha256': digest(task),
        'source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}
    immutable_json(OUT / 'protocol.json', protocol)
    return protocol


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['preflight', 'acquire'])
    args = parser.parse_args()
    with (ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        protocol = prepare()
        for name, value in protocol['source_sha256'].items():
            assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == value
        task = read(OUT / 'teacher_task.json')
        assert digest(task) == protocol['task_sha256']
        system = SYSTEM + '\nAllowed calls: ' + ','.join(sorted(CALLS)) + '\nAllowed attributes: ' + ','.join(sorted(METHODS))
        user = json.dumps(task, ensure_ascii=False, separators=(',', ':'))
        issues = old.prior.strict_output_schema_issues(old.SCHEMA)
        size = len(old.prior.render_structured_codex_prompt(system, user))
        assert not issues and size <= old.prior.CODEX_TURN_INPUT_CHARACTER_LIMIT
        immutable_json(OUT / 'preflight.json', {'schema_issues': issues,
            'request_characters': size, 'case_facts_questions_labels_in_task': False})
        if args.phase == 'acquire' and not (OUT / 'teacher.json').exists():
            ledger = EvolutionLedger(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3',
                run_id=RUN, sources={'train': protocol['sources'], 'dev': [], 'test': []}, binding=digest(protocol))
            result = FrozenTeacher(ledger, OUT, protocol['teacher_profile']).propose(RUN + ':common_kernels',
                source_ids=protocol['sources'], system_prompt=system, user_prompt=user, output_schema=old.SCHEMA)
            immutable_json(OUT / 'teacher.json', result)
            print(json.dumps({'common_kernels_saved': True, 'new_executor_requests': 0}), flush=True)


if __name__ == '__main__':
    main()
