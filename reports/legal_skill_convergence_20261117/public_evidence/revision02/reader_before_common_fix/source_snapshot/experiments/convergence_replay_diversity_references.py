"""TRAIN references through exactly the production relational decoder.

Reference preparation is deliberately separate from inference. Native labels
are read only after all reference-produced predictions are sealed in memory.
No weak model or teacher is invoked; these are adapter/decoder checks.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path

from legal_skill_guard.paired_interfaces import diversity_relational as interfaces,residual
from legal_skill_guard.paired_interfaces.diversity import audit_source,reference_outputs
from legal_skill_guard.paired_interfaces.production_decode import decode_response
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/legal_skill_convergence_20261117'


def reference_reading(source,plan):
    text=source['views'][0]['public']['source_text'];record=audit_source(text)
    amounts=defaultdict(list)
    for claim in record['claims']:amounts[claim['plaintiff'],claim['defendant']].append(claim['amount'])
    raw={};fidelity=[]
    for name,unit in plan['relational_program']['units'].items():
        context=unit['entity_context'];p,d=context['plaintiff'],context['defendant']
        kind=unit['template_key'].split(':')[0]
        if kind=='citizenship':state={'plaintiff_state':record['citizenship'][p],'defendant_state':record['citizenship'][d]}
        else:
            values=amounts[p,d]
            if any(v%1000 or v<0 for v in values):raise ValueError('Reference falls outside certified nonnegative whole-thousand support')
            state={'claim'+str(i):min(value//1000,76) for i,value in enumerate(values)}
        asset=unit['asset'];values=residual.encode(asset['features'],state)
        raw[name]={'status':'complete','observation':{'source_anchor':name,'relations':values},
            'evidence':[{'field':'source_text','quote':text}]}
        check=residual.source_fidelity(interfaces.module(kind),asset,values,admissible_states=[state],
            provenance=[{'kind':'explicit_source','evidence_sha256':hashlib.sha256(text.encode()).hexdigest()}])
        fidelity.append({'unit':name,'status':check['status'],'source_fidelity_verified':check['source_fidelity_verified']})
    return raw,fidelity


def run():
    pointer=json.loads((BASE/'handoff/normalized_inputs_current.json').read_text());data=ROOT/pointer['artifact_root']
    train=[s for s in json.loads((data/'train/public.json').read_text()) if s['dataset']=='LegalBench_Diversity']
    rows=[]
    for source in train:
        view=interfaces.views(source)[0]
        for plan in view['plans']:
            raw,fidelity=reference_reading(source,plan)
            decoded=decode_response(source,view,plan,{'content':json.dumps(raw,ensure_ascii=False),'finish_reason':'stop'})
            if decoded['production_errors'] or not all(v['source_fidelity_verified'] for v in fidelity):
                raise ValueError('Source-reference production chain discrepancy')
            rows.append({'source':source['key'],'choices':plan['choices'],'plan_sha256':digest(plan),
                'reference_input_sha256':digest(raw),'decoded_native':decoded['native'],
                'decoded_diagnostics':decoded['decoder_receipt']['diagnostics'],'fidelity':fidelity})
    seal=digest(rows)
    preparation=json.loads((BASE/'handoff/diversity_train_current.json').read_text())
    gold=json.loads((ROOT/preparation['artifact_root']/'grading.json').read_text())
    for row in rows:
        native=gold[row['source']]['native']
        if row['decoded_native']['native']['answer']!=native['answer'] or row['decoded_diagnostics']!=native['diagnostics']:
            raise ValueError('Native annotation mismatch; do not remove or repair a source by its score')
    files=['experiments/convergence_replay_diversity_references.py','legal_skill_guard/paired_interfaces/diversity_relational.py',
        'legal_skill_guard/paired_interfaces/relational_program.py','legal_skill_guard/paired_interfaces/residual.py',
        'legal_skill_guard/paired_interfaces/production_decode.py','legal_skill_guard/paired_interfaces/diversity.py']
    binding={'name':'convergence_Diversity_production_reference_replay_v1','input_root':pointer['artifact_root'],
        'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in files},
        'predictions_sha256_before_grading':seal,'native_labels_in_reader_inputs':False,'new_model_calls':0}
    out=BASE/'diversity_reference_chain_v1'/digest(binding)
    immutable_json(out/'binding.json',binding);immutable_json(out/'predictions.json',rows)
    summary={'artifact_root':str(out.relative_to(ROOT)),'TRAIN_mothers':len(train),'reference_decodings':len(rows),
        'all_three_native_fields_match':len(rows),'production_errors':0,'new_model_calls':0,
        'weak_model_efficacy_established':False,'reference_inputs_to_real_production_decoder':True}
    immutable_json(out/'summary.json',summary)
    (BASE/'handoff/diversity_reference_chain_current.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary),flush=True)


if __name__=='__main__':run()
