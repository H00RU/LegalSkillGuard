"""Prepare only the fixed native TRAIN candidate pool. No TEST/model access."""
import csv
from io import StringIO
import json
import hashlib
from pathlib import Path

from legal_skill_guard.paired_interfaces.diversity import (
    GOLD_FIELDS,REVISION,annotation,audit_source,public_source,reference_outputs,structural_group)
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/legal_skill_convergence_20261117'


def prepare():
    receipt=json.loads((BASE/'handoff/diversity_train_download_receipt.json').read_text())
    public=[];audit=[];grading={};groups={};duplicates=[]
    for item in receipt['files']:
        rows=list(csv.DictReader(StringIO((ROOT/item['path']).read_text(encoding='utf-8-sig')),delimiter='\t'))
        # Fixed per-variant first four, with only objective cross-variant
        # duplicates eligible for ordered replacement. No labels select rows.
        selected=0
        for ordinal,row in enumerate(rows):
            record=audit_source(row['text']);group=structural_group(record)
            if selected>=4:break
            if group in groups:
                duplicates.append({'variant':item['variant'],'native_id':row['index'],'group_hash':group,
                                   'matches':groups[group],'reason':'objective_name_invariant_duplicate'})
                continue
            source=public_source(row,item['variant'],project_split='train')
            assert not (GOLD_FIELDS&set(source['views'][0]['public']))
            groups[group]=source['key'];public.append(source)
            # Audit predictions are sealed separately before native annotations
            # are exposed to any scoring/learning path. This is not a weak read.
            audit.append({'source':source['key'],'mother_group':group,'native_config':item['variant'],
                'native_index':row['index'],'native_split':'train','project_split':'train',
                'original_ordinal':ordinal,'audit_reference':record,'outputs_before_grading':reference_outputs(record)})
            grading[source['key']]=annotation(row);selected+=1
        if selected!=4:raise ValueError('Fixed Diversity TRAIN quota lacks distinct groups: '+item['variant'])
    protocol={'name':'convergence_Diversity_native_TRAIN_preparation_v2','revision':REVISION,
        'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in (
            'legal_skill_guard/paired_interfaces/diversity.py',
            'experiments/convergence_prepare_diversity_train.py')},
        'requested_train_mothers':24,'test_opened':False,'raw_files':receipt['files'],
        'public_inputs_have_no_native_gold':True,'reference_parser_is_not_model_inference':True,
        'selection':'first four per config; only group duplicates replaced in native index order',
        'historical_cross_dataset_exposure_dedup_pending':True}
    out=BASE/'diversity_train_v2'/digest(protocol)
    immutable_json(out/'protocol.json',protocol)
    immutable_json(out/'public.json',public)
    immutable_json(out/'source_audit_before_grading.json',audit)
    immutable_json(out/'prediction_seal.json',{'reference_outputs_sha256':digest(audit),'new_weak_model_predictions':0})
    immutable_json(out/'grading.json',grading)
    correct=0
    for row in audit:
        gold=grading[row['source']]['native'];value=row['outputs_before_grading']
        match=value['answer']==gold['answer'] and all(value[k]==gold['diagnostics'][k] for k in GOLD_FIELDS-{'answer'})
        if not match:raise ValueError('Native adapter discrepancy; repair code rather than removing a hard source')
        correct+=1
    summary={'artifact_root':str(out.relative_to(ROOT)),'prepared_train_mothers':len(public),
        'all_three_native_fields_match':correct,'objective_duplicates_skipped':duplicates,
        'formal_all_five_dataset_manifest_locked':False,'reference_not_model_accuracy':True,
        'teacher_sees_native_gold_only_when_source_is_in_current_train_prefix':True,
        'DEV_TEST_opened':False,'new_model_calls':0}
    immutable_json(out/'summary.json',summary)
    # Mutable recovery pointer; versioned preparation/evidence remains immutable.
    (BASE/'handoff/diversity_train_current.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='objective_duplicates_skipped'},ensure_ascii=False))


if __name__=='__main__':prepare()
