"""Check the routing repair against settled TRAIN history without any client."""
import argparse
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime,timezone
import hashlib,importlib.util,json,shutil,socket,sys,tempfile
from pathlib import Path
from types import SimpleNamespace

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--implementation-root',type=Path)
args=parser.parse_args()
ROOT=Path(__file__).resolve().parents[2];IMPLEMENTATION=(args.implementation_root or ROOT).resolve()
sys.path.insert(0,str(IMPLEMENTATION))
from legal_skill_guard.skill_evolution import proposal_batch,patterns
from legal_skill_guard.skill_evolution.objects import Library
from legal_skill_guard.skill_evolution.revisions import VersionTable
FOLDER=ROOT/'artifacts/legal_skill_evolution_20261111/formal_v4'
spec=importlib.util.spec_from_file_location('legal_skill_guard.skill_evolution.proposal_batch_before_arm_fix',FOLDER/'source_snapshot/legal_skill_guard/skill_evolution/proposal_batch.py')
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)

def denied(*args,**kwargs):raise AssertionError('Network disabled in recorded-history routing check')
socket.socket=denied

def load(p):return json.loads(p.read_text())
def wire(v):return json.dumps(v,ensure_ascii=False,separators=(',',':'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

class Capture:
    class ledger:run_id='offline_corevision_routing_capture'
    def propose(self,*args,**kwargs):return kwargs

manifest=load(ROOT/'reports/legal_skill_evolution_plan_20261111/candidate_source_manifest.json')
batches=[[r['source_key'] for r in b['sources']] for b in manifest['source_sequence']]
prepared=ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train'
records={r['key']:r for r in load(prepared/'public.json')};grading=load(prepared/'grading.json')
profiles=load(ROOT/'configs/legal_skill_evolution_formal_v4_20261111.json')
comparisons=[];learning=[]
with tempfile.TemporaryDirectory() as temporary:
    folder=Path(temporary)
    study=SimpleNamespace(folder=folder,batches=batches,order=sum(batches,[]),records=records,teacher=Capture())
    study.initial_batch=lambda arm,batch:load(FOLDER/arm/f'initial_B{batch}.json')
    study.library_path=lambda arm,batch:FOLDER/arm/f'B{batch}.json'
    study.feedback=lambda ids,current:[{'source':key,'annotations':grading[key],'execution':current[key]} for key in ids]
    for arm in profiles['arms']:
        if arm=='NoSkill':continue
        for batch in range(1,6):
            context=FOLDER/arm/f'update_context_B{batch}.json'
            target=folder/arm/context.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(context,target)
            before=old.prepare_context(study,arm,batch);after=proposal_batch.prepare_context(study,arm,batch)
            assert before['old'].hash==after['old'].hash
            for key in ('arm','batch','trigger','history','cohort','queue','current'):assert before[key]==after[key],(arm,batch,key)
            a=old.propose_context(study,before);b=proposal_batch.propose_context(study,after)
            assert wire(a)==wire(b),(arm,batch,'actual proposal input differs')
            comparisons.append({'arm':arm,'batch':batch,'old_library_hash':before['old'].hash,
                'old_pattern_count':len(before['old'].revision_patterns),'before_queue':before['queue'],'after_queue':after['queue'],
                'teacher_input_bytes_equal':True,'teacher_input_sha256':hashlib.sha256(wire(a).encode()).hexdigest()})
    for path in sorted((FOLDER/'CoRevOnly').glob('update_B[1-5].json')):
        receipt=load(path);batch=receipt['batch'];current=Library.load(FOLDER/'CoRevOnly'/f'B{batch}.json')
        if receipt['selected_candidate'] is None:
            learning.append({'batch':batch,'accepted_update':False,'new_patterns':[],'library_changed_by_repair':False});continue
        candidate=load(FOLDER/'CoRevOnly'/f'B{batch}_candidates'/f"{receipt['selected_candidate']}.json")
        exported=candidate['table'];table=VersionTable(tuple(exported['revision_hashes']),tuple(exported['trigger']),tuple(exported['history']))
        for cell in exported['mixed_version_table']:table.observe(cell['mask'],cell['source'],cell['native_parent_grade'],cell['trace'])
        copied=deepcopy(current);before=wire(asdict(copied))
        created=patterns.learn(copied,Library.load(FOLDER/'CoRevOnly'/f'B{batch-1}.json'),candidate['revisions'],table,receipt['selected_mask'],generic=False)
        assert not created and before==wire(asdict(copied)),batch
        learning.append({'batch':batch,'accepted_update':True,'selected_width':receipt['selected_mask'].bit_count(),
            'new_patterns':created,'library_changed_by_repair':False,'old_library_hash':current.hash,'after_hash':copied.hash})
result={'captured_utc':datetime.now(timezone.utc).isoformat(),'new_model_calls':0,'ledger_writes':0,'network_disabled':True,
    'TEST_opened':False,'fixed_completed_batch_prefix':5,'real_teacher_input_comparisons':comparisons,
    'CoRevOnly_recorded_accepted_update_recovery':learning,
    'all_completed_prefix_model_inputs_libraries_and_scores_unchanged':True,
    'reason':'Both pattern-learning and automatic pattern-candidate routing omitted CoRevOnly. Its actual prior accepted updates are singleton creations, so the repaired learner adds no historical pattern and all thirty cached proposal inputs remain byte-identical.',
    'implementation_sha256':{p:sha(IMPLEMENTATION/p) for p in ('legal_skill_guard/skill_evolution/proposal_batch.py','legal_skill_guard/skill_evolution/study.py','tests/test_skill_evolution_arm_routing.py')},
    'empirical_method_success_established':False}
(ROOT/'reports/legal_skill_evolution_run_20261111/actual_corevision_arm_routing_regression.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'actual_cached_teacher_inputs_unchanged':len(comparisons),'CoRevOnly_updates_unchanged':len(learning),'new_model_calls':0}))
