"""Acquire two paired component proposals per arm, using existing TRAIN only.

Acquisition closes before validation/recombination. No DEV record or label is
loaded. Prior B8 exposure is inherited and disclosed, not called a fresh split.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path

from experiments import legal_skill_evolution_observation_library_train as previous
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.observation_component_library import import_saved_library
from legal_skill_guard.skill_evolution.sara_statute_kernel import current_case_interface, GIVENS
from legal_skill_guard.skill_evolution.teacher_transport import pack_programs, unpack_programs, INSTRUCTION, PROGRAM_INSTRUCTION
from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues


ROOT=previous.ROOT
RUN='legal_skill_evolution_observation_component_learning_20261115'
OUT=ROOT/'artifacts'/RUN
ARMS=('CoverageRecombine','FreeGlobalUpdate')
ACQUISITION_HEADS=('s3306_b','s63_d','s63_c_5')
REUSE_HEADS=('s152_b_1','s2_a_1_A')
read=previous.read

EDIT=record_schema({'id':{'type':'string'},'meaning':{'type':'string'},'prompt':{'type':'string'},
    'schema_json':{'type':'string'},'conversion_program':{'type':'string'},
    'parent_component_hash':{'type':['string','null']},
    'error_feedback_ids':{'type':'array','items':{'type':'string'}}})
COVER=record_schema({'id':{'type':'string'},'complete_native_families':{'type':'array','items':{'type':'string'}},
    'coverage_explanation':{'type':'string'},'error_feedback_ids':{'type':'array','items':{'type':'string'}}})
SCHEMA=record_schema({'rationale':{'type':'string'},'candidates':{'type':'array','minItems':2,'maxItems':2,
    'items':record_schema({'name':{'type':'string'},'rationale':{'type':'string'},
        'component_edits':{'type':'array','items':EDIT},'coverage_updates':{'type':'array','items':COVER}})}})

SYSTEM='''Revise reusable observation representations AND their conversions for
the unchanged author legal program. This is a finite continuation on original
TRAIN, not new data or model-weight training. Two alternatives are requested,
not two repeated calls. Both arms have the same seed, full author program,
legitimate TRAIN evidence, code capacity, error/source checks and resources.
Use no tools. No DEV/TEST or unseen case labels are available. No case/person/
source-ID lookup or target applicability fact is allowed.

The public host now derives native input families from ANY author query's
dependency graph. There is NO per-query-name planner. Learn complete-family
coverage contracts for source-native components, plus schema/prompt/conversion
repairs. Coverage is substantive: merely emitting payment_ in a termination
episode does NOT cover ordinary wages. Do not relabel a specialized view as
general. Either retain narrow coverage, widen its real schema/conversion, or
use/create a genuinely general component. Complete means reading this finite
case, not proving real-world absence; neural unread remains explicit. A missing
channel cannot be changed to zero/false or guessed from a known native answer.

Return exactly TWO useful candidate updates. Each component edit contains its
full meaning/prompt/schema and a complete pure conversion_program with one
apply(inputs,premises). It receives component_id,view,public_case,kernel and
returns {facts:[{predicate,arguments}],negative_givens:[],witnesses:[{field,quote}],
complete:boolean,reasons:[string]}. The same fixed shared_helpers are prepended;
they may be called, or you may add pure uniquely named helpers in the component
program. Do not redefine shared helpers. The current imported lower routine is
an asset, not an obligation to preserve an inappropriate interface. Schemas and
conversion change TOGETHER; no separate drifting field aliases or guessed
defaults. Alternatives in views remain alternatives; no favorable answer is
selected. Use only the declared native factual signatures.

coverage_updates must include EVERY resulting component ID in each candidate.
complete_native_families lists only unary native event/entity families or exact
declared source-given predicates whose WHOLE finite-source family that component
can observe and lower faithfully. [] is valid for restricted/incomplete views.
Some native input families are missing from the old library: disclose gaps or
add a compact source-only general component; do not fabricate a coverage proof.
The host records these as learned claims, not verified semantics. All candidates
must pass the SAME source and native checks. Untouched component code/schemas
are reused exactly. Parent hashes must name actual base components; new ones
use null. Error IDs must exist in this task, or remain [] for source-only work.

Current failures: TRAIN-name dispatch has no compositional basis; specialized
termination views cannot replace general payment views. Source annual income
is not a151(b) exemption. A source-stated151(b) personal exemption is not a63(d)
deduction_; keep its distinction observable. A question can name a source event
but cannot establish its occurrence, date, death or statutory entitlement.
Only source-stated legal givens with the exact native roles/polarity may be
asserted. No query-derived death/date, no invented payment day from a service
interval, no private-home assumption from the phrase domestic service.

Pure Python only: no imports, IO, classes, nested functions, lambdas, recursion
or model calls in code. Input/output schema must agree with actual conversion.
Return compact valid code and inline JSON schemas, without $ref/definitions.
'''


def prepare():
    path=OUT/'protocol.json'
    if path.exists():
        protocol=read(path)
        for name,sha in protocol['binding_sha256'].items():
            assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha,name
        return protocol
    prior=read(previous.OUT/'protocol.json')
    bank=read(previous.parent.OUT/'SARA_native_kernel_bank.json')
    by_head={r['kernel']['name']:r for r in bank}
    acquisition=[by_head[h]['source'] for h in ACQUISITION_HEADS]
    reuse=[by_head[h]['source'] for h in REUSE_HEADS]
    assert set(acquisition).isdisjoint(reuse)
    seed_path=previous.OUT/'B8/FreeHistory/library.json'
    seed=import_saved_library(read(seed_path))
    immutable_json(OUT/'seed_library.json',seed)
    public={s['key']:s for s in read(previous.parent.OUT/'SARA_corrected_TRAIN_views.json')}
    cases=[]
    for sid in acquisition:
        historic=[]
        for b in range(1,9):
            for stage in ('initial_scored_results.json','scored_results.json'):
                p=previous.OUT/f'B{b}'/stage
                if p.exists():historic.extend(r for r in read(p)['rows'] if r['source']==sid)
        cases.append({'source':sid,'public_case':public[sid]['views'][0]['public'],
            'kernel':current_case_interface(next(r['kernel'] for r in bank if r['source']==sid)),
            'actual_paid_observations_and_conversions':historic})
    kernel=cases[0]['kernel']
    statutes={name:(ROOT/kernel['statute_directory']/name).read_text() for name in kernel['statute_sha256']}
    assert all(hashlib.sha256(text.encode()).hexdigest()==kernel['statute_sha256'][name] for name,text in statutes.items())
    feedback={
        'ordinary_wage_scope':{'source':acquisition[0], 'finding':'Actual original TRAIN source pays2325 in hay for agricultural labor. A termination/disability/death-only schema cannot represent that ordinary payment without inventing a cause. Preserve payment/source roles and means; do not use its emitted native symbols as an unconditional coverage claim.'},
        'personal_exemption_basis':{'source':acquisition[1], 'finding':'Source explicitly allows2000 for Alice under151(b), while the native query asks63(d). Do not emit deduction_ for the151(b) exemption. Preserve an actual observation of the151(b) basis/amount; empty/default output is not evidence that the distinction was learned.'},
        'income_is_not_statutory_entitlement':{'source':acquisition[2], 'finding':'Source income33200 for Alice and10 for Bob does not establish151(b) exemption amounts. General negative151 entitlement for Bob must not be narrowed to an exact151(b)/(c) source-given without evidence. The query cannot establish63(c)(5) as a fact.'}}
    task={'same_goal':True,'same_seed_both_arms':seed,'full_unchanged_author_statutes':statutes,
        'source_native_signatures':kernel['fact_arities'],'explicit_source_given_signatures':GIVENS,
        'acquisition_cases':cases,'error_feedback_by_id':feedback,
        'original_TRAIN_supervision':{sid:read(previous.parent.PREPARED/'grading.json')[sid] for sid in acquisition},
        'public_dependency_reader_code':(ROOT/'legal_skill_guard/skill_evolution/statute_input_dependencies.py').read_text(),
        'component_format_and_execution_code':(ROOT/'legal_skill_guard/skill_evolution/observation_component_library.py').read_text(),
        'same_minimal_case_context_as_prior_readers':['facts','question','native_query','query_clause'],
        'prior_B8_exposure_to_all_original24_SARA_disclosed':True,
        'two_reuse_cases_withheld_from_this_update_not_claimed_blind_history':True,
        'never_infer_source_semantic_truth_from_native_correctness':True}
    encoded=json.dumps(task,ensure_ascii=False)
    assert not any(sid in encoded or public[sid]['views'][0]['public']['facts'] in encoded for sid in reuse)
    assert unpack_programs(pack_programs(task))==task
    immutable_json(OUT/'teacher_task.json',task)
    code=[Path(__file__),ROOT/'legal_skill_guard/skill_evolution/observation_component_library.py',
        ROOT/'legal_skill_guard/skill_evolution/component_observation_execution.py',
        ROOT/'legal_skill_guard/skill_evolution/statute_input_dependencies.py',
        ROOT/'legal_skill_guard/skill_evolution/clients.py',ROOT/'legal_skill_guard/skill_evolution/ledger.py',
        ROOT/'legal_skill_guard/skill_evolution/case_observation_contract.py']
    bindings={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in code}
    for p in (OUT/'seed_library.json',OUT/'teacher_task.json',seed_path):bindings[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
    protocol={'run_id':RUN,'same_goal':True,'acquisition_sources':acquisition,'reuse_sources':reuse,
        'all_inherited_TRAIN_exposure':prior['sources'],'new_sources':[],
        'executor_profile':prior['executor_profile'],'teacher_profile':prior['teacher_profile'],
        'binding_sha256':bindings,'teacher_concurrency':2,'teacher_calls_planned':2,
        'candidates_per_arm':2,'calibration_TRAIN_mothers':3,'reuse_TRAIN_mothers':2,
        'one_finite_mechanism_probe_not_new_full_TRAIN_or_DEV':True,'DEV_or_TEST_opened':False,
        'method':'Pair observation-schema and converter versions; select compatible component recombinations from actual reads and fixed source/native feedback.',
        'control':'Best complete ordinary-teacher candidate from same two proposals and same actual read budget.',
        'common_public_routing_not_innovation':True,'goal_complete':False}
    immutable_json(path,protocol)
    for p in code:
        target=OUT/'source_snapshot'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(p.read_bytes())
    return protocol


def acquire(protocol):
    ledger=EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,
        sources={'train':protocol['all_inherited_TRAIN_exposure'],'dev':[],'test':[]},
        binding=digest(protocol),teacher_concurrency=2)
    task=read(OUT/'teacher_task.json')
    assert not strict_output_schema_issues(SCHEMA)
    def one(arm):
        target=OUT/arm/'teacher.json'
        if target.exists():return
        mode=('Your updates are decomposed into paired component units. The host will fit recombinations using the actual per-case reads, source-semantic constraints and unchanged native program. Propose genuinely useful alternative local repairs, rather than cosmetic variants.' if arm=='CoverageRecombine' else
            'Independently propose the two strongest complete ordinary-teacher updates. Any joint/structured repair, new representation, converter, coverage reasoning and same modular capacity are allowed. The best whole candidate is retained under the same source/native feedback. Do not weaken the control or avoid a useful method merely to differ.')
        value=FrozenTeacher(ledger,OUT,protocol['teacher_profile']).propose(RUN+':'+arm+':update',
            source_ids=[s for s in protocol['all_inherited_TRAIN_exposure'] if s.startswith('SARA_v2_Binary:')],
            system_prompt=SYSTEM+'\n'+mode+'\n'+INSTRUCTION+'\n'+PROGRAM_INSTRUCTION,
            user_prompt=json.dumps(pack_programs(task),ensure_ascii=False,separators=(',',':')),output_schema=SCHEMA)
        immutable_json(target,value)
        print(json.dumps({'teacher_saved':arm,'same_seed':True}),flush=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs=[pool.submit(one,arm) for arm in ARMS]
        for job in jobs:job.result()


if __name__=='__main__':
    with (ROOT/'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        acquire(prepare())
