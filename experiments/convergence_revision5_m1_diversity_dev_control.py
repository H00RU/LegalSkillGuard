"""Apply the TRAIN literal control to the actual Diversity B8 DEV reads."""

import base64
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from experiments.convergence_formal_curves import pointer
from experiments.convergence_m1_incumbent_audit import DATASET, M1
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha
from experiments.convergence_revision5_m1_quote_amount_control import HOME as TRAIN_HOME, quote_amounts
from legal_skill_guard.paired_interfaces import diversity, diversity_claim_groups, relational_program, residual
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.formal_evaluation import verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view, restore_enum_transport
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE/'revision5_M1_diversity_DEV_literal_20261119'
ORDINARY = 'common_teacher_skill_learning'
EXTERNAL = 'strongest_matched_external_baseline'
TASK = 'native'
DEPENDENCIES = (
    'legal_skill_guard/paired_interfaces/diversity.py',
    'legal_skill_guard/paired_interfaces/diversity_relational.py',
    'legal_skill_guard/paired_interfaces/diversity_source_binding.py',
    'legal_skill_guard/paired_interfaces/diversity_claim_groups.py',
    'legal_skill_guard/paired_interfaces/relational_program.py',
    'legal_skill_guard/paired_interfaces/residual.py',
)


def coordinates(unit, request):
    quotes = request['source_excerpts']
    entities = unit['entity_context']
    if 'claim_count' in entities:
        quote, = quotes
        return quote_amounts(quote, entities['claim_count'])
    result = {}
    for role,quote in zip(('plaintiff','defendant'),quotes,strict=True):
        name = re.escape(entities[role])
        match = re.fullmatch(rf'{name} is from ([A-Za-z]+(?: [A-Za-z]+)*)\.',quote)
        if match is None:
            raise ValueError('The original paid citizenship scope is not a single literal statement')
        result[role+'_state'] = match[1]
    return result


def encode_literal(program, requests):
    assert set(program['units'])==set(requests)
    return {
        name: {'status':'complete',
               'observation':{'source_anchor':name,
                              'relations':residual.encode(unit['asset']['features'],coordinates(unit,requests[name]))},
               'evidence':[{'field':'source_text','quote':q} for q in requests[name]['source_excerpts']]}
        for name,unit in program['units'].items()
    }


def amount_only(learned_program, learned_raw, literal, requests):
    """Correct amount observations using the very quotations in the paid read."""
    current = deepcopy(learned_raw)
    changes = Counter()
    for name,unit in learned_program['units'].items():
        row = current[name]
        offered = requests[name]['source_excerpts']
        assert row['status']=='complete' and row['observation']['source_anchor']==name
        assert set(offered)=={e['quote'] for e in row['evidence'] if e['field']=='source_text'}
        actual, expected = (x['observation']['relations'] for x in (row,literal[name]))
        kind = unit['template_key'].split(':',1)[0]
        if actual!=expected:
            changes[kind]+=1
        if kind!='citizenship':
            row['observation']['relations']=expected
    return current, changes


def cell(root, stage_terminal, arm, cohort):
    folder = root/'dev'/'B8'/arm
    task = read(folder/'task.json')
    seal = verify(read(folder/'prediction_seal.json'),'prediction_seal_sha256')
    grades = verify(read(folder/'scores.json'),'cell_sha256')
    assert grades['partition']=='dev' and seal['task_sha256']==digest(task)
    assert grades['prediction_seal_sha256']==seal['prediction_seal_sha256']
    assert grades['cell_sha256']==stage_terminal['cell_sha256'][arm]
    assert seal['predictions_sha256'].keys()=={s['key'] for s in cohort}
    return folder,seal,grades


def selected_read(db, stage, source, view, saved, library):
    key = source['key']
    selection = saved['result']['selection']
    assert selection['route']=='synthesized_interface' and selection['current_source_truth_or_read_used'] is False
    assert selection['source_public_sha256']==digest(source) and selection['library_sha256']==library
    assert read(stage/'convergence_decisions'/(digest([selection,'skill_dev'])+'.json'))==selection
    reading, = saved['result']['reads']
    choice, = selection['choices']
    plan, = (p for p in view['plans'] if p['version']==choice['version']==reading['raw_read_version'])
    target = stage/'interface_reads'/digest(reading['logical_call_id'])
    task = read(target/'task.json')
    assert read(target/'decoded.json')==reading and reading['task_sha256']==digest(task)
    assert task['source_public_sha256']==digest(source) and task['purpose']=='skill_dev'
    assert plan['schema']==task['output_schema'] and plan['system']==task['messages'][0]['content']
    original_input=json.loads(task['messages'][-1]['content'])
    assert original_input==view['read_input']
    identity = reading['physical_call_id']
    status,role,root,purpose,fingerprint,result = db.execute(
        'select status,role,source,purpose,request_hash,result from calls where id=?',(identity,)).fetchone()
    assert (status,role,root,purpose)==('completed','executor',key,'skill_dev')
    actual = json.loads(result)
    directory=Path(actual['artifact_directory'])
    request,wire=(read(directory/name) for name in ('request.json','wire_request.json'))
    raw=base64.b64decode(wire['body_b64'],validate=True)
    assert hashlib.sha256(raw).hexdigest()==wire['body_sha256'] and json.loads(raw)==request['payload']
    assert request['payload']['messages']==task['messages']
    assert request['payload']['model']=='Qwen/Qwen3-8B'
    assert request['payload']['chat_template_kwargs']['enable_thinking'] is False
    assert actual['thinking_requested'] is False and actual['finish_reason']=='stop'
    assert request['id']==identity and request['request_hash']==actual['request_hash']==fingerprint
    assert read(directory/'result.json')==actual and digest(actual['content'])==reading['response_content_sha256']
    content,_ = restore_enum_transport(json.loads(actual['content']),plan['schema'])
    assert not reading['production_errors']
    assert saved['result']['native']==reading['native']
    return plan,content,identity,original_input['unit_requests']


def verify_condition(predictions, official, views, labels):
    for source,value in predictions.items():
        assert value==official[source]['answer']
        grade = grade_view(DATASET,views[source]['views'][0],labels[source][TASK],value)['grade']
        assert grade==official[source]['grade']


def contrast(before, after, labels):
    strata = {source:row[TASK]['answer'] for source,row in labels.items()}
    def scored(data):
        return [{'source':key,'view':TASK,'grade':int(value==strata[key])} for key,value in data.items()]
    return paired_source_effect(scored(before),scored(after),strata=strata)


def run():
    stage = ROOT/read(pointer(8))['artifact_root']
    binding,terminal = (read(stage/f) for f in ('binding.json','terminal.json'))
    assert stage.name==digest(binding) and not terminal['TEST_opened'] and terminal['batch']==8
    assert all(sha(stage/'source_snapshot'/name)==h for name,h in binding['source_sha256'].items())
    assert all(sha(ROOT/name)==binding['source_sha256'][name] for name in DEPENDENCIES)
    checkpoint = ROOT/binding['checkpoint_root']
    study = read(checkpoint/'binding.json')
    assert digest(study)==binding['checkpoint_binding_sha256']
    dev = ROOT/binding['b0_dev_data_root']
    cohort = read(dev/'public_DEV_sources.json')
    assert digest(cohort)==read(dev/'binding.json')['DEV_public_sha256'] and len(cohort)==80
    sources = {s['key']:s for s in cohort if s['dataset']==DATASET and s['project_split']=='dev'}
    assert len(sources)==16
    train = read(TRAIN_HOME/'literal_amount_control.json')
    reader_file = ROOT/'experiments/convergence_revision5_m1_quote_amount_control.py'
    assert train['cached_TRAIN_reads']==96 and sha(reader_file)==train['source_sha256']
    grade = study['grading_paths'][DATASET]
    assert 'dev' in Path(grade).parts
    spec = {'study':'archived_Diversity_DEV_same_information_literal_control','partition':'dev','dataset':DATASET,
            'fixed_B8_DEV_binding_sha256':stage.name,'fixed_B8_DEV_terminal_sha256':sha(stage/'terminal.json'),
            'source_cohort_sha256':digest(sources),'TRAIN_literal_receipt_sha256':sha(TRAIN_HOME/'literal_amount_control.json'),
            'grade_sha256':study['grading_file_sha256'][grade],'source_sha256':sha(Path(__file__)),
            'all_original_arms_preserved':True,'physical_new_requests':0}
    out = HOME/digest(spec)
    immutable_json(out/'protocol.json',spec)
    cells = {arm:cell(checkpoint,terminal,arm,cohort) for arm in (ORDINARY,M1,EXTERNAL)}
    comparison = {arm:{} for arm in (*cells,'amount_only','literal_fixed','literal_learned')}
    provider = diversity_claim_groups.Provider()
    wire_ids, changes, bindings, diagnostics = set(),Counter(),Counter(),{}
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
        assert not ledger.get('reserved')
        for key,source in sources.items():
            for arm,(folder,seal,score) in cells.items():
                saved = read(folder/'predictions'/(digest(key)+'.json'))
                assert saved['source']==key and saved['dataset']==DATASET and saved['public_source_sha256']==digest(source)
                assert seal['predictions_sha256'][key]==digest(saved)
                assert saved['library_sha256']==score['libraries'][DATASET]
                comparison[arm][key]=saved['result']['native'][TASK]['answer']
                if arm==M1:
                    archive = saved
                    library = saved['library_sha256']
            view, = provider.views(source)
            learned,raw,identity,units=selected_read(db,stage,source,view,archive,library)
            wire_ids.add(identity)
            requests={r['source_anchor']:r for r in units}
            fixed, = (p for p in view['plans'] if p['is_correct_fixed_raw_control'])
            learned_program, fixed_program = learned['relational_program'], fixed['relational_program']
            source_public = view['relational_public_source']
            actual=relational_program.decode(learned_program,raw,source_public)
            assert actual['outputs'][TASK]==comparison[M1][key]
            literal_learned = encode_literal(learned_program,requests)
            literal_fixed = encode_literal(fixed_program,requests)
            repaired, changed = amount_only(learned_program,raw,literal_learned,requests)
            changes.update(changed)
            bindings.update(learned['choices'].keys())
            for mode,program,value in (('amount_only',learned_program,repaired),
                                       ('literal_fixed',fixed_program,literal_fixed),
                                       ('literal_learned',learned_program,literal_learned)):
                decoded=relational_program.decode(program,value,source_public)
                comparison[mode][key]=decoded['outputs'][TASK]
                diagnostics[key,mode]=decoded['diagnostics']
            assert comparison['literal_fixed'][key]==comparison['literal_learned'][key]
            assert diagnostics[key,'literal_fixed']==diagnostics[key,'literal_learned']
            ref=diversity.reference_outputs(diversity.audit_source(source['views'][0]['public']['source_text']))
            assert ref=={'answer':comparison['literal_fixed'][key],**diagnostics[key,'literal_fixed']}
    assert len(wire_ids)==16
    immutable_json(out/'predictions.json',comparison)
    assert sha(ROOT/grade)==spec['grade_sha256']
    full_grade=read(ROOT/grade)
    labels={k:full_grade[k] for k in sources}
    for arm,(_,_,score) in cells.items():
        official={r['source']:r for r in score['source_scores'] if r['dataset']==DATASET and r['view']==TASK}
        verify_condition(comparison[arm],official,sources,labels)
    statistics = {arm:diversity.score(pred,labels) for arm,pred in comparison.items()}
    summary = {'DEV_conditions':statistics,'distinct_paid_interface_wires_verified':len(wire_ids),
               'changed_observations_by_kind':dict(changes),'selected_plan_kind_coverage':dict(bindings),
               'same_consumer_literal_outputs_equal':comparison['literal_fixed']==comparison['literal_learned'],
               'amount_only_repairs_against_original_route':contrast(comparison[M1],comparison['amount_only'],labels),
               'fixed_literal_minus_original_M1':contrast(comparison[M1],comparison['literal_fixed'],labels),
               'synthetic_literal_minus_fixed_literal':contrast(comparison['literal_fixed'],comparison['literal_learned'],labels),
               'new_model_requests':0,'ledger':ledger,'runner_sha256':spec['source_sha256']}
    immutable_json(out/'summary.json',summary)
    print(json.dumps({'artifact_root':str(out.relative_to(ROOT)),**summary},sort_keys=True))


if __name__=='__main__':
    run()
