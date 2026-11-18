"""Test a certified complement of the original Diversity amount relation."""

import argparse
from collections import Counter
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace

from experiments.convergence_formal_b1_observe import load_roster
from experiments.convergence_formal_bootstrap import POINTER as BOOTSTRAP
from experiments.convergence_formal_train_observe import pointer as observation_pointer
from experiments.convergence_m1_incumbent_audit import DATASET, M1, _verify_reads
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import diversity_claim_groups, diversity_relational, relational_program, residual
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.paired_interfaces.formal_actors import InterfaceActor
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


FAMILY = ('single_claim', 'same_pair_claims')
POINTER = HANDOFF / 'revision5_M1_Diversity_amount_polarity_current.json'
HOME = BASE / 'revision5_m1_amount_polarity_20261119'
DONE = 'completed_revision5_M1_amount_polarity'


@lru_cache(maxsize=len(FAMILY))
def amount_assets(kind):
    original = diversity_relational.candidates(kind)[1]
    features = deepcopy(original['features'])
    feature, = features
    expression = feature['expression']
    if feature['operation']!='relation' or expression['op']!='gt':
        raise ValueError('Only the original strict amount predicate may be complemented')
    expression['op'] = 'le'
    module = diversity_relational.module(kind)
    inverted = residual.compile_pair(module,features,operation='certified_amount_complement',layout=original['layout'])
    binding = module.binding
    field = feature['name']
    for state in module.states:
        old = residual.encode(original['features'],state)
        new = residual.encode(features,state)
        if (new[field] != (None if old[field] is None else not old[field])
                or any(residual.decode(original,old,c,module_binding=binding)!=
                       residual.decode(inverted,new,c,module_binding=binding) for c in module.contexts)):
            raise ValueError('Complement must preserve the entire original consumer on the complete declared domain')
    return original, inverted


def complement(source, view, original):
    program = original['relational_program']
    units = deepcopy(program['units'])
    changed = set()
    for unit in units.values():
        kind = unit['template_key'].split(':',1)[0]
        if kind not in FAMILY:
            continue
        verified, inverted = amount_assets(kind)
        if unit['asset']!=verified:
            raise ValueError('Use only the attested amount synthesis candidate')
        unit.update(asset=inverted, asset_sha256=digest(inverted), template_key=kind+':'+inverted['version'])
        changed.add(kind)
    updated = relational_program.sealed({**{k:v for k,v in program.items() if k!='program_sha256'},'units':units})
    old_prompt = relational_program.prompt(program)
    schema = relational_program.schema(updated)
    if (not changed or not original['system'].startswith(old_prompt)
            or json.dumps(schema,ensure_ascii=False)!=json.dumps(original['schema'],ensure_ascii=False)
            or relational_program.unit_requests(updated)!=relational_program.unit_requests(program)):
        raise ValueError('Keep the original literal JSON grammar and unit attachment information')
    system = relational_program.prompt(updated)+original['system'][len(old_prompt):]
    plan = {**{k:v for k,v in original.items() if k!='version'},'name':original['name']+':complement',
            'relational_program':updated,'schema':schema,'system':system,
            'reader_template_sha256':relational_program.template_version(
                updated,system=system,public_rules=view['read_input']['rules'],
                protocol='diversity_one_amount_predicate_complement_v1')}
    plan['version'] = digest(plan)
    diversity_claim_groups.Provider().verify_plan(source,view,plan)
    return plan,changed


def materials():
    root = ROOT / read(BOOTSTRAP)['artifact_root']
    study = read(root/'binding.json')
    batches = load_roster(study)
    journal = TrainingJournal(root,study,batches)
    direction = HOME/'directional_train_audit.json'
    discovery = read(direction)
    if discovery['selected_native_errors_with_amount_misread'] != [
            {'batch':3,'relation_kind':'single_claim','error':'false_positive','local_quote_set_complete':True}]:
        raise ValueError('The comparison needs the exact original TRAIN amount-polarity failure')
    bank = journal.library(M1,8)['interface_library']['observations']
    provider = diversity_claim_groups.Provider()
    rows, originals, proof_families = [], [], set()
    for batch in (3,4):
        for source in batches[batch-1]:
            if source['dataset']!=DATASET:
                continue
            view, = provider.views(source)
            old, = (plan for plan in view['plans']
                    if plan['choices']['citizenship']==0 and all(value==1 for k,value in plan['choices'].items()
                                                               if k!='citizenship'))
            fixed, = (plan for plan in view['plans'] if plan['is_correct_fixed_raw_control'])
            observed = {r['plan_version']:r for r in bank if r['source']==source['key']}
            new, changed = complement(source,view,old)
            proof_families.update(changed)
            originals += [observed[old['version']],observed[fixed['version']]]
            rows.append({'batch':batch,'source':source,'view':view,'before':observed[old['version']],
                         'fixed':observed[fixed['version']],'comparison_plan':new})
    if len(rows)!=6 or proof_families!=set(FAMILY):
        raise ValueError('Compare on all original Diversity TRAIN mothers in B3 and its following batch')
    _verify_reads(originals)
    observed = ROOT/read(observation_pointer(4))['artifact_root']
    grades = read(observed/'binding.json')
    grade_path = grades['native_grade_paths'][DATASET]
    expected_hash = grades['native_grade_sha256'][grade_path]
    sealed_train = ROOT/read(HANDOFF/'diversity_train_current.json')['artifact_root']/'grading.json'
    if ROOT/grade_path!=sealed_train or sha(sealed_train)!=expected_hash:
        raise ValueError('Only the original sealed TRAIN grade file may score these sources')
    dependencies = {*read(ROOT/read(observation_pointer(4))['artifact_root']/'binding.json')['source_sha256'],
                    str(Path(__file__).resolve().relative_to(ROOT))}
    spec = {'study':'revision5_M1_Diversity_amount_polarity','sealed_B8_M1_interface_sha256':
                journal.library(M1,8)['interface_library']['snapshot_sha256'],
            'comparison_rows_sha256':digest(rows),'source_sha256':{p:sha(ROOT/p) for p in sorted(dependencies)},
            'fixed_executor':study['executor'],'source_direction_audit_sha256':sha(direction),
            'candidate_proof_state_counts':{g:len(diversity_relational.module(g).states) for g in sorted(proof_families)},
            'cohort':'All original Diversity TRAIN sources in B3 and B4; original chronology preserved',
            'original_grade_sha256':expected_hash,'original_grade_path':grade_path,
            'preserve_original_predictions_and_libraries':True,'TEST_opened':False}
    return spec, rows


def audit_observations(source, view, plan, decoded):
    evidence = diversity_claim_groups.unit_reviews(source,view)
    if not decoded['decoder_receipt']:
        return {'fully_faithful':False,'counts':{}}
    audited = {}
    for name, unit in plan['relational_program']['units'].items():
        scope = evidence[name]
        readout = decoded['decoder_receipt']['local_receipts'][name]['source_read']
        kind = unit['template_key'].split(':',1)[0]
        status = 'unread'
        if readout['supported']:
            check = residual.source_fidelity(scope['module'],unit['asset'],readout['values'],
                                             admissible_states=scope['admissible_states'],provenance=scope['provenance'])
            status = check['status']
        audited[name]={'kind':kind,'status':status}
    return {'fully_faithful':all(r['status']=='entailed' for r in audited.values()),
            'counts':dict(Counter(r['kind']+'/'+r['status'] for r in audited.values()))}


def run(execute):
    if POINTER.exists():
        saved = read(POINTER)
        if saved['status']==DONE:
            print(saved['artifact_root'],flush=True)
            return
    spec, rows = materials()
    stage = HOME / digest(spec)
    if execute and (not POINTER.exists() or ROOT/read(POINTER)['artifact_root']!=stage):
        raise ValueError('Run only the prepared immutable comparison')
    immutable_json(stage/'binding.json',spec)
    if not execute:
        if POINTER.exists() and read(POINTER)['status']=='running':
            raise ValueError('Preserve the active comparison')
        write_status(stage,{'status':'prepared','TRAIN_mothers':len(rows)},POINTER)
        print(stage.relative_to(ROOT),flush=True)
        return
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        if db.execute("select 1 from calls where status='reserved'").fetchone():
            raise ValueError('Reconcile the current generation boundary before charging more calls')
    for name, expected in spec['source_sha256'].items():
        path = stage/'source_snapshot'/name
        path.parent.mkdir(parents=True,exist_ok=True)
        if not path.is_file():
            with path.open('xb') as file:
                file.write((ROOT/name).read_bytes())
        if sha(path)!=expected:
            raise ValueError('Archive the original comparison source before changing the run state')
    keys = [r['source']['key'] for r in rows]
    ledger = EvolutionLedger(LEDGER,run_id='convergence-revision5-M1-polarity-'+stage.name[:16],
                             sources={'train':keys,'dev':[],'test':[]},binding=spec)
    reader = FrozenExecutor(ledger,stage,spec['fixed_executor'])
    reader.readiness()
    provider = diversity_claim_groups.Provider()
    actor = InterfaceActor(reader,stage,plan_assets={},source_inputs=None,relational_provider=provider,
                           pipeline_binding=spec['source_sha256'])
    native_labels = read(ROOT/spec['original_grade_path'])
    summaries = []
    for index,row in enumerate(rows,1):
        source,view,plan = (row[k] for k in ('source','view','comparison_plan'))
        write_status(stage,{'status':'running','TRAIN_mothers':len(rows),'finished':index-1,
                            'next_batch':row['batch']},POINTER)
        result = actor.measure(source,{**view,'plans':[*view['plans'],plan]},plan,'skill_actor')
        audit = audit_observations(source,view,plan,result)
        native, = result['native'].values()
        task, = source['views']
        utility = (grade_view(DATASET,task,native_labels[source['key']][task['id']],native['answer'])['grade']
                   if native['handled'] else 0.0)
        before, coordinate = row['before'],row['fixed']
        summary = {'batch':row['batch'],'native':{'complement':utility,'original':before['native_utility'],
                                                'fixed_coordinates':coordinate['native_utility']},
                   'source_faithfulness':{'complement':audit['fully_faithful'],
                                          'original':before['source_fidelity']['all_local_relations_source_faithful'],
                                          'fixed_coordinates':coordinate['source_fidelity']['all_local_relations_source_faithful']},
                   'complement_unit_status':audit['counts'],'physical_call_id':result['physical_call_id']}
        immutable_json(stage/'scored'/f'{index}.json',summary)
        summaries.append(summary)
    totals = {name:{'correct':sum(r['native'][name] for r in summaries),
                    'fully_source_faithful':sum(r['source_faithfulness'][name] for r in summaries)}
              for name in ('complement','original','fixed_coordinates')}
    with ledger.transaction() as db:
        calls=db.execute('select status,result from calls where id like ?',(ledger.run_id+':%',)).fetchall()
    if len(calls)!=len(rows) or any(status!='completed' for status,_ in calls):
        raise ValueError('Seal only the actual complete six-source comparison')
    done = {'status':DONE,'totals':totals,'rows':summaries,'physical_executor_calls':len(calls),
            'tokens':sum(json.loads(value)['usage']['total_tokens'] for _,value in calls),
            'development_only':True,'TEST_opened':False}
    immutable_json(stage/'terminal.json',done)
    write_status(stage,{'status':DONE,'TRAIN_mothers':len(rows)},POINTER)
    print(json.dumps({'totals':totals,'physical_executor_calls':len(calls),'tokens':done['tokens']}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=('prepare','run'))
    run(parser.parse_args().phase=='run')
