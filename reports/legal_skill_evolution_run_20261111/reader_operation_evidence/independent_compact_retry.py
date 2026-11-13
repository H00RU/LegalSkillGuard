"""Lossless compact-output retry for the one timed-out independent acquisition.

Default is offline preparation. --dispatch issues one new accounted teacher
request with the unchanged original TRAIN input and unrestricted reader scope.
"""
import argparse
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from experiments import legal_skill_evolution_semantic_operations as study
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenTeacher
from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.runtime import decoder_schema
from legal_skill_guard.skill_evolution.semantic_operations import OPERATION,validate_operations
from legal_skill_guard.skill_evolution.source_effect_update import function_update

SCHEMA=record_schema({'rationale':{'type':'string'},'operations_delta':{'type':'array','items':OPERATION},
                     'source_functions':{'type':'array','items':{'type':'string'}}})


def normalize(value,base):
    ops={o['name']:deepcopy(o) for o in base['operations']}
    for op in value['operations_delta']: ops[op['name']]=deepcopy(op)
    return {'rationale':value['rationale'],'operations':list(ops.values()),
            'source_functions':value['source_functions']}


def prepare():
    folder,p,ledger,public=study.setup();base=study.read(folder/'base.json')
    previous=study.read(folder/'IndependentReader/teacher_input.json')
    system=previous['system']
    # The control keeps all tools/expressivity but need not follow the candidate's
    # constructive-operation architecture. This removes a confusing instruction,
    # not evidence, correctness checks, source material or a baseline capability.
    start=system.index('Do not merely');end=system.index('The free arm is allowed',start)
    system=system[:start]+'Choose an unrestricted, economical reader independently. Pure Python and any combination of the common semantic tool are allowed. You need not reproduce the candidate architecture or invent a research contribution.\n'+system[end:]
    system=system.replace('Return the complete operations list, including any common operation still used.',
        'Return operations_delta: only new operations or replacements by an existing name. Unchanged common operations are inherited and need not be repeated. Unused operations need not be called.')
    system+='\nThe earlier independent request timed out after600 seconds without a proposal. Keep the output compact: changed complete functions only, inherited functions remain callable. Empty operations_delta is valid for a pure-code reader. Preserve the full original task and all correctness requirements. Do not add sources or use current execution results; none are supplied.'
    # Offline roundtrip on the actual acquired candidate, not an invented toy.
    actual=study.read(folder/'LearnedOperations/teacher.json')['value']
    old={o['name']:o for o in base['operations']}
    delta={'rationale':actual['rationale'],'source_functions':actual['source_functions'],
           'operations_delta':[o for o in actual['operations'] if old.get(o['name'])!=o]}
    roundtrip=normalize(delta,base);assert roundtrip==actual
    functions=[]
    for module in roundtrip['source_functions']:
        functions.extend(ast.get_source_segment(module,n) for n in ast.parse(module).body)
    assert function_update(base['source_program'],functions)==study.read(folder/'LearnedOperations/compiled.json')['program']
    wire,host=decoder_schema(SCHEMA)
    request={'system':system,'user':previous['user'],'logical_schema':SCHEMA,'wire_schema':wire,'host_constraints':host}
    immutable_json(folder/'IndependentReader/compact_teacher_input.json',request)
    immutable_json(folder/'IndependentReader/compact_offline_evidence.json',{
        'actual_successful_proposal_roundtrips_exactly':True,'compiled_program_roundtrips_exactly':True,
        'TRAIN_input_byte_identical_to_failed_request':request['user']==previous['user'],
        'TRAIN_input_sha256':hashlib.sha256(request['user'].encode()).hexdigest(),
        'no_new_semantic_labels_or_model_execution_results_supplied':True,
        'unrestricted_control_expressivity_preserved':True,'no_configuration_or_source_changes':True,
        'specific_change':'Inherited operation definitions need not be repeated; explicitly remove candidate-only architecture wording from the independent control.',
        'adapter_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'new_model_requests_for_this_offline_evidence':0})
    return folder,p,ledger,public,base,request


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--dispatch',action='store_true');args=parser.parse_args()
    folder,p,ledger,public,base,request=prepare()
    if args.dispatch:
        raw=FrozenTeacher(ledger,folder,p['teacher_profile']).propose(study.RUN+':teacher:IndependentReader_compact:'+digest(request),
            source_ids=p['teacher_sources'],system_prompt=request['system'],user_prompt=request['user'],output_schema=request['wire_schema'])
        immutable_json(folder/'IndependentReader/compact_teacher_raw.json',raw)
        canonical=normalize(raw['value'],base)
        validate_operations(canonical['operations'],{k:public[k]['views'][0]['public']['source_text'] for k in p['teacher_sources']})
        immutable_json(folder/'IndependentReader/teacher.json',{'value':canonical,
            'raw_result_path':'IndependentReader/compact_teacher_raw.json',
            'representation_adaptation':'Declared operation delta merged with exact common acquired operations; original raw response retained. No semantic values invented.'})
        result=study.compile_arm(folder,p,public,'IndependentReader')
        print(json.dumps({'compiled':True,'operations':len(result['operations'])}))
    else: print(json.dumps({'offline_roundtrip_passed':True,'new_model_requests':0,
                            'next_command':'independent_compact_retry.py --dispatch'}))
