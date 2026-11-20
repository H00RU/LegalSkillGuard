"""Use measured B7 amount-edit evidence in formal M2 update and forward scoring."""

import base64
import json
from pathlib import Path
import sqlite3

from experiments import convergence_revision5_oe_assertion_coverage as matched
from experiments import convergence_revision5_oe_edit_acquisition as edits
from experiments import convergence_revision6_candidate_fit as native
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces.control_answers import source_bundle
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

HOME = BASE / 'revision6_formal_candidate_edits_M2'
POINTER = HANDOFF / 'revision6_formal_candidate_edits_M2_current.json'


def read_edited_results(stage, spec, source, ev, text, variants, original, db):
    outputs, identities = {}, set()
    for policy in edits.ACQUISITIONS:
        outputs[policy] = {}
        for role in edits.ROLES:
            saved = read(stage/'reads'/f'{policy}_{role}.json')
            physical = saved['call_id']
            edits.physical_wire(db,{source['key']},physical,source['key'])
            row, = db.execute('select result from calls where id=?',(physical,)).fetchone()
            response = json.loads(row)
            wire = read(Path(response['artifact_directory'])/'wire_request.json')
            original_payload = original[role]['payload']
            messages, public = edits.edited_messages(original_payload,text,variants[policy])
            expected = json.dumps({**original_payload,'messages':messages},ensure_ascii=False).encode()
            if base64.b64decode(wire['body_b64'],validate=True) != expected or wire['body_sha256'] != saved['wire_sha256']:
                raise ValueError('The actual projection did not use this policy’s exact source edit')
            task = source_bundle({**source,'views':[{**ev,'public':public}]})
            schema = original_payload['response_format']['json_schema']['schema']
            answer = edits.projection(task,schema,response)
            if answer != saved['answer']:
                raise ValueError('An actual projection no longer matches its native execution')
            outputs[policy][role] = answer
            identities.add(physical)
    if len(identities) != 4 or not spec['TRAIN_only']:
        raise ValueError('The matched edit conditions need both retained actual reads each')
    return outputs, sorted(identities)


def select(measured, gain):
    """Require a supported winning update and an observed error in the entering program."""
    observations = measured['on_common_base_slots']
    if not measured['complete_common_support'] or gain <= 0:
        return 'incumbent','insufficient_coverage_or_native_gain'
    candidate = observations['candidate']
    incumbent = observations['incumbent']
    if incumbent['joint_conflicts'] > 0 and candidate['joint_conflicts'] == 0:
        return 'proposal','selective_actual_support'
    return 'incumbent','no_directional_witness'


def run(execute=False):
    _, _, _, programs, native_pairs, fit = native.original(7)
    spec, source, ev, text, inv, law, variants, original = edits.materials()
    stage = ROOT / read(edits.POINTER)['artifact_root']
    old = read(stage/'terminal.json')
    if (stage.name != digest(spec) or read(stage/'binding.json') != spec
            or old['status'] != 'settled_OE_edit_acquisition_TRAIN' or not old['same_information_direct_cap_matches']):
        raise ValueError('Use the completed same-budget TRAIN edits and fixed independent reference')
    gain = sum(q['patch_utility']-q['baseline_utility'] for q in native_pairs)/len(native_pairs)
    binding = {'stage':'revision6_M2_candidate_edit_formal_update','batch':7,'TRAIN_only':True,
               'source_sha256':{str(p.relative_to(ROOT)):sha(p) for p in (
                   Path(__file__).resolve(),Path(native.__file__),Path(edits.__file__),Path(matched.__file__))},
               'frozen_fit_terminal_sha256':sha(fit/'terminal.json'),
               'matched_edit_terminal_sha256':sha(stage/'terminal.json'),
               'programs':dict(zip(('incumbent','proposal'),map(digest,programs),strict=True)),
               'same_pool':spec['same_public_pool_scores'], 'selection':spec['selected'],
               'actual_budget_per_selection_policy':2, 'native_train_gain':gain,
               'native_pair_sha256':digest(native_pairs),'TEST_opened':False}
    out = HOME/digest(binding)
    immutable_json(out/'binding.json',binding)
    if (out/'terminal.json').exists():
        print(out,flush=True)
        return
    if not execute:
        write_status(out,{'status':'prepared','new_model_calls_planned':0},POINTER)
        print(out,flush=True)
        return
    if ROOT/read(POINTER)['artifact_root'] != out:
        raise ValueError('Prepare the exact specified acquisition and update binding')
    for name,h in binding['source_sha256'].items():
        p = out/'source_snapshot'/name
        p.parent.mkdir(parents=True,exist_ok=True)
        if not p.exists():
            with p.open('xb') as stream:
                stream.write((ROOT/name).read_bytes())
        if sha(p) != h:
            raise ValueError('The recorded production path changed')
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
        outputs, identities = read_edited_results(stage,spec,source,ev,text,variants,original,db)
        forward, context, known_programs, count, grade = matched.archived_pairs(db)
    if ledger.get('reserved') or binding['programs'] != known_programs:
        raise ValueError('Use the exact adopted program when reusing forward evidence')
    common, verified = edits.report_counts(original,outputs,inv,law,variants)
    # report_counts recomputes both cap checks on each comparable assertion
    # and asserts equality before either observation may drive a fit decision.
    if common != old['common_base_slots'] or verified != old['by_acquisition']:
        raise ValueError('The original matched projection result cannot change')
    predictions, decisions = {}, {}
    for policy, observation in verified.items():
        adopted, reason = select(observation,gain)
        program = programs[1 if adopted == 'proposal' else 0]
        decision = {'selected_group':binding['selection'][policy],'decision':adopted,
                    'direct_decision':adopted,'reason':reason,'actual_read_count':2}
        library = sealed({'batch':7,'dataset':native.OE,'program':program,
                          'frozen_fit_terminal_sha256':binding['frozen_fit_terminal_sha256'],
                          'fit_decision_sha256':digest(decision)},'snapshot_sha256')
        immutable_json(out/'TRAIN_batch_libraries'/f'{policy}.json',library)
        decisions[policy] = {**decision,'snapshot_sha256':library['snapshot_sha256']}
        predictions[policy] = forward[8]['raw'][adopted]
    predictions_sha = immutable_json(out/'B8_forward_predictions.json',predictions)
    scores = matched.score(forward[8]['original_views'],
                           {'incumbent':predictions[edits.ACQUISITIONS[0]],'proposal':predictions[edits.ACQUISITIONS[1]]},
                           read(grade))
    result = sealed({'status':'settled_revision6_M2_candidate_edit_formal_update','binding_sha256':out.name,
                     'decisions':decisions,'common_source_bound_slots':common,'measured_group_effects':verified,
                     'same_information_direct_cap_matched_on_every_assertion':True,
                     'forward_TRAIN_scores':scores,'forward_predictions_sha256':predictions_sha,
                     'forward_TRAIN_execution_binding':context,'verified_native_reads':count,
                     'bound_physical_edit_requests':len(identities),
                     'new_model_calls':0,'TEST_opened':False,'ledger':ledger},'terminal_sha256')
    immutable_json(out/'terminal.json',result)
    write_status(out,{'status':result['status'],'terminal_sha256':result['terminal_sha256']},POINTER)
    print(out,flush=True)
