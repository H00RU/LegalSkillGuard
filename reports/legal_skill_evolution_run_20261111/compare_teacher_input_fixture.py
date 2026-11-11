from pathlib import Path
from types import SimpleNamespace
import hashlib,inspect,json,sys,tempfile
from unittest.mock import patch
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.study import Study
from legal_skill_guard.skill_evolution.objects import Library

class Captured(RuntimeError):pass
packets=[]
class Teacher:
    ledger=SimpleNamespace(run_id='fixture_same_identity')
    def propose(self,call_id,**kwargs):
        packet={'call_id':call_id,**kwargs}
        raw=json.dumps(packet,ensure_ascii=False).encode()
        packets.append({'arm':json.loads(kwargs['user_prompt'])['arm'],'payload_sha256':hashlib.sha256(raw).hexdigest(),
                        'raw':raw.decode()})
        raise Captured()
with tempfile.TemporaryDirectory() as folder:
    for memory_candidate in (False,True):
        study=object.__new__(Study);study.folder=Path(folder)/str(memory_candidate);study.stage='formal'
        study.batches=[[f'parent_{i}' for i in range(16)],[f'parent_{i}' for i in range(16,32)]]
        study.order=sum(study.batches,[]);study.profile={};study.teacher=Teacher()
        study.records={key:{'key':key,'dataset':'SARA_v2_Binary','views':[{'id':'native','public':{'text':'Fixture source only.'},'answer_schema':{'type':'string','enum':['Entailment','Contradiction']}}]} for key in study.order}
        study.grading={key:{'native':{'answer':'Entailment'}} for key in study.order}
        def parent(key,library):return {'source':key,'dataset':'SARA_v2_Binary','library_hash':library.hash,'selection_grade':(int(key.split('_')[1])%4)/4,'native_grade':0,'views':[]}
        study.parent=parent
        for arm in ('FreeEvolution','LiftOnly','CoRevOnly','Full','Lift+GenericJoint','AllPorts+CoRev'):
            library=Library(provisional_edits=[{'batch':1,'candidate_index':0,'revisions':None,'error':'Fixture transcription failure','raw_block':{'revisions':[{'operation':'create','skill':{'id':'fixture-retained'}}]}}])
            library.save(study.library_path(arm,1))
            immutable_json(study.folder/arm/'initial_B2.json',{'binding':{'batch':2,'arm':arm,'source_ids':study.batches[1],'library_hash':library.hash},'results':[parent(key,library) for key in study.batches[1]]})
            with patch('legal_skill_guard.skill_evolution.patterns.candidates',return_value=[{'fixture_memory':True}] if memory_candidate else []),patch('urllib.request.OpenerDirector.open',side_effect=AssertionError('network forbidden')):
                try:study.update(arm,2)
                except Captured:pass
                else:raise AssertionError('Fixture did not intercept teacher dispatch')
            packets[-1]['memory_candidate_present']=memory_candidate
result={'study_code_path':inspect.getfile(Study),'study_code_sha256':hashlib.sha256(Path(inspect.getfile(Study)).read_bytes()).hexdigest(),'packets':packets,'actual_model_calls':0,'scope':'Fixtures intercept before teacher or executor dispatch; checks exact serialized teacher inputs only.'}
Path(sys.argv[1]).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'captured_packets':len(packets),'actual_model_calls':0,'study_file':inspect.getfile(Study)}))
