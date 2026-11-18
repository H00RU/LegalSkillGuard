"""Recheck a native-positive TRAIN policy after feedback about its actual rejected allocation."""

import argparse
import json
import sqlite3
from pathlib import Path

from experiments import convergence_oe_feedback_pair as prior
from experiments.convergence_formal_train_fit import _validate_relation
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces.convergence_actors import ConvergenceActor
from legal_skill_guard.paired_interfaces.convergence_ev_inventory import EVInventoryActor
from legal_skill_guard.paired_interfaces.formal_actors import ProgramActor
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest


POINTER = HANDOFF / 'revision5_oe_candidate_feedback_repair_current.json'
SYSTEM = prior.SYSTEM + (
    ' This is a corrective pass on a measured proposal. Keep its native gains as well as the stable '
    'literal source checks. Diagnose the actual recorded allocations under the supplied checking rule. '
    'Describe how to handle the title decision consistently without assuming possession establishes title. '
    'Generalize the policy beyond the supplied query rows.'
)


def materials():
    spec, study, base, visible, pilot, literal, context, _ = prior.materials()
    original_stage = ROOT / read(prior.POINTER)['artifact_root']
    old = read(original_stage/'terminal.json')
    if original_stage.name != digest(spec) or old['status'] != 'completed_B8_OE_feedback_pair' or old['TEST_opened']:
        raise ValueError('The fixed prior TRAIN feedback comparison must be complete')
    audit_path = BASE/'revision5_evidence_reconciliation_20261119'/'m2_teacher_and_selection.json'
    audit = read(audit_path)['isolated_feedback_pilot']
    if audit['terminal_sha256'] != sha(original_stage/'terminal.json'):
        raise ValueError('Use the exact audit of the earlier paired raw teacher requests')
    start = read(original_stage/'shared_explanation.json')
    before = read(original_stage/'incumbent.json')
    start_program = start['candidate']
    observed = start['audit']['typed_reads']
    supports = prior.support(context, observed)
    if not (start['controls']['native_only'] and start['controls']['literal_only']
            and supports['independent_completions']['retained'] > 0
            and supports['shared']['retained'] == 0):
        raise ValueError('The informative prior intervention is a literal-valid native-positive proposal with a shared contradiction')
    shared = prior.signatures(context, 'shared')
    independent = prior.signatures(context, 'independent_completions')
    allowed = [sorted(set(values)) for values in zip(*independent, strict=True)]
    if allowed != [sorted(set(values)) for values in zip(*shared, strict=True)]:
        raise ValueError('Both teachers must retain the same per-query information')
    rows = []
    for i, (case, query, result) in enumerate(zip(context['cases'], context['inputs'], observed, strict=True)):
        if (result['case'] != case.source_id or result['source_sha256'] != digest(case.public)
                or result['failure'] is not None):
            raise ValueError('Feedback must cite the matched physical TRAIN observation')
        rows.append({'slot':i+1,'requested_component':query['requested_component'],
                     'verified_source_facts':query['independently_verified_source_facts'],
                     'measured_allocation_tag':result['read_tag'],
                     'measured_allocation':result['value'],'per_query_allowed_amounts':allowed[i]})
    common = {'starting_policy':start_program[prior.OWNERSHIP_FIELD],
              'same_source_observations':rows,'native_current_policy':prior._aggregate(start['native']),
              'native_entering_policy':prior._aggregate(before['native']),
              'literal_source_gate_passed':True,
              'unresolved_rule':'An unresolved reading makes no assertion about this slot.',
              'native_contract':'Keep the existing complete EC/EV task and exact source-evidence mapping.'}
    relation = {'independent_completions': {
                    'rule':'Each query may use its own admissible completion.',
                    'observations_have_a_compatible_signature':supports['independent_completions']['retained'] > 0},
                'shared_explanation': {
                    'rule':'The same title must explain the asserted components of both amount variants.',
                    'jointly_allowed_allocations':shared,
                    'observations_have_a_compatible_signature':supports['shared']['retained'] > 0}}
    payloads = {role:{**common,'relation_diagnosis':relation[role]} for role in prior.ROLES}
    path = str(Path(__file__).resolve().relative_to(ROOT))
    sources = {**spec['source_sha256'],path:sha(ROOT/path)}
    for filename, expected in sources.items():
        if sha(ROOT/filename) != expected:
            raise ValueError('The reused public pipeline differs from the original matched experiment')
    binding = {'study':'revision5_openexempt_targeted_actual_candidate_contradiction',
               'parent_feedback_terminal_sha256':sha(original_stage/'terminal.json'),
               'raw_feedback_audit_sha256':sha(audit_path),'prior_program_sha256':digest(start_program),
               'prior_source_evidence_sha256':digest(rows),'teacher_contract_sha256':digest([SYSTEM,prior.SCHEMA]),
               'matched_payload_sha256':{k:digest(v) for k,v in payloads.items()},
               'source_sha256':sources,'teacher_profile':spec['teacher_profile'],
               'teacher_config':spec['teacher_config'],'executor':spec['executor'],
               'four_original_TRAIN_mothers_sha256':digest([s['key'] for s in pilot]),
               'model_comparison_budget':{'matched_teacher_per_condition':1},
               'postfreeze_TRAIN_only':True,'original_TEST_content_or_labels_used':False}
    return (binding,spec,study,base,visible,pilot,literal,context,original_stage,
            start_program,start,before,payloads)


def run(execute):
    if POINTER.exists():
        previous = ROOT / read(POINTER)['artifact_root']
        if (previous/'terminal.json').exists():
            if read(previous/'terminal.json')['status'] != 'completed_revision5_OE_actual_candidate_feedback':
                raise ValueError('Reconcile the existing comparison terminal before preparing a new run')
            print(previous.relative_to(ROOT),flush=True)
            return
    (binding,spec,study,base,visible,pilot,literal,context,parent,start_program,
     started,before,payloads) = materials()
    out = BASE / 'revision5_oe_candidate_feedback_repair' / digest(binding)
    if execute and (not POINTER.exists() or ROOT/read(POINTER)['artifact_root'] != out):
        raise ValueError('Use the prepared revision, bound TRAIN cohort, and evidence contracts')
    immutable_json(out/'binding.json',binding)
    if (out/'terminal.json').exists():
        print(out.relative_to(ROOT),flush=True)
        return
    if not execute:
        if POINTER.exists() and read(POINTER)['status']=='running':
            raise ValueError('The original revision run is still active')
        write_status(out,{'status':'prepared','postfreeze_TRAIN_only':True},POINTER)
        print(out.relative_to(ROOT),flush=True)
        return
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        if db.execute("select 1 from calls where status='reserved'").fetchone():
            raise ValueError('Reconcile the original in-flight generation before proceeding')
    for name, expected in binding['source_sha256'].items():
        archive = out/'source_snapshot'/name
        archive.parent.mkdir(parents=True,exist_ok=True)
        if not archive.exists():
            with archive.open('xb') as stream:
                stream.write((ROOT/name).read_bytes())
        if sha(archive)!=expected:
            raise ValueError('Preserve the versioned comparison source before any requests')
    keys = [source['key'] for source in pilot]
    allowed_train = [source['key'] for source in visible]
    run_id = 'convergence-revision5-OE-repair-' + out.name[:16]
    ledger = EvolutionLedger(LEDGER,run_id=run_id,sources={'train':keys,'dev':[],'test':[]},binding=binding)
    reader = FrozenExecutor(ledger,out,binding['executor'])
    reader.readiness()
    teacher = FrozenTeacher(ledger,out,binding['teacher_config'],authorized_profile=binding['teacher_profile'])
    actor = EVInventoryActor(ConvergenceActor(out,program_actor=ProgramActor(reader,out,max_calls=1),
                            interface_actor=None,providers={},train_sources=allowed_train,study_binding=study),
                            jurisdiction_scope=True)
    grade_path = ROOT/spec['native_TRAIN_grade_path']
    if sha(grade_path)!=spec['native_TRAIN_grade_sha256']:
        raise ValueError('Use the original independent TRAIN grader')
    annotations = read(grade_path)
    original_program = base['programs'][prior.OE]
    earlier = {digest(original_program):before, digest(start_program):started}
    outcomes = {}
    for role in prior.ROLES:
        write_status(out,{'status':'running','condition':role,'step':'teacher','postfreeze_TRAIN_only':True},POINTER)
        response = teacher.propose(run_id+':teacher:'+role,source_ids=keys,system_prompt=SYSTEM,
                                   user_prompt=json.dumps(payloads[role],sort_keys=True),output_schema=prior.SCHEMA)
        if response['model']!=binding['teacher_profile']['model']:
            raise ValueError('Use the same actual teacher for each matched condition')
        candidate = prior.edit_policy(start_program,response['value'][prior.OWNERSHIP_FIELD],allowed_train)
        identity = digest(candidate)
        write_status(out,{'status':'running','condition':role,'step':'executor','postfreeze_TRAIN_only':True},POINTER)
        if identity in earlier:
            scores = earlier[identity]['native']
        else:
            child = sealed({**{k:v for k,v in base.items() if k!='snapshot_sha256'},
                            'programs':{**base['programs'],prior.OE:candidate}},'snapshot_sha256')
            predictions = prior.measure_native(actor,child,pilot)
            scores = prior._native_scores(pilot,predictions,annotations)
            immutable_json(out/(role+'_native.json'),{'program_sha256':identity,'predictions':predictions,'scores':scores})
        pairs = [{'source':key,'baseline_utility':sum(before['native'][key].values())/2,
                  'patch_utility':sum(scores[key].values())/2} for key in keys]
        delta = sum(r['patch_utility']-r['baseline_utility'] for r in pairs)/len(pairs)
        detail = {'candidate':candidate,'native':scores,'earlier_native_reused':identity in earlier}
        result = {'native':prior._aggregate(scores),'native_mean_gain_over_B8':delta,
                  'candidate_sha256':identity,'literal_status':None,'support':None}
        if delta > 0:
            literal_receipt = (started['audit']['literal'] if identity==digest(start_program) else
                               _validate_relation(reader,out,candidate,literal,allowed_train,pairs))
            detail['literal_receipt'] = literal_receipt
            result['literal_status'] = literal_receipt['status']
            if literal_receipt['status']=='eligible_train_update':
                reads = (started['audit']['typed_reads'] if identity==digest(start_program) else
                         prior.measure_components(reader,out,candidate,context))
                detail['typed_reads'] = reads
                if all(row['failure'] is None for row in reads):
                    result['support'] = prior.support(context,reads)
                    result['asserted_projection_slots'] = sum(row['value'] is not None for row in reads)
        immutable_json(out/(role+'_result.json'),detail)
        outcomes[role]=result
    matched = {view:outcomes['shared_explanation']['native'][view]-outcomes['independent_completions']['native'][view]
               for view in ('EC','EV')}
    with ledger.transaction() as db:
        settled = db.execute('select role,status,result from calls where id like ?',(run_id+':%',)).fetchall()
    if any(status!='completed' for _,status,_ in settled):
        raise ValueError('Reconcile the bounded TRAIN requests before writing the terminal seal')
    usage = {role:{'physical_calls':0,'total_tokens':0} for role in ('teacher','executor')}
    for role,_,raw in settled:
        response = json.loads(raw)
        if role=='teacher':
            tokens = response['invocation']['usage']
            amount = tokens['input_tokens'] + tokens['output_tokens']
        else:
            amount = response['usage']['total_tokens']
        usage[role]['total_tokens'] += amount
        usage[role]['physical_calls'] += 1
    if usage['teacher']['physical_calls'] != len(prior.ROLES):
        raise ValueError('The paired repair requires exactly one settled teacher proposal per condition')
    done = {'status':'completed_revision5_OE_actual_candidate_feedback','outcomes':outcomes,
            'paired_shared_minus_independent':matched,'prior_native_positive_candidate':prior._aggregate(started['native']),
            'original_B8_native':prior._aggregate(before['native']),'physical_usage':usage,
            'postfreeze_TRAIN_only':True,'original_libraries_fitted_here':False}
    immutable_json(out/'terminal.json',done)
    write_status(out,{'status':done['status'],'postfreeze_TRAIN_only':True},POINTER)
    print(json.dumps(done,ensure_ascii=False,sort_keys=True),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=('prepare','run'))
    run(parser.parse_args().phase=='run')
