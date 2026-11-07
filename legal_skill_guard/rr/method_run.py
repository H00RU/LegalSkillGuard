"""One current shared acquisition, fixed paired thinking check and six DEV arms.

This entry uses the existing physical ledger and current source contracts.
Historical FormalRun policies/results are never restarted or silently mixed in.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3

from .checkpoint import immutable_json
from .controls import ARMS,SharedMaterial,project_material
from .coverage import digest
from .example_synthesis import _fit_horn_examples
from .learning import SkillLibrary
from .ledger import BudgetError
from .method_client import MethodExecutor,MethodTeacher,TEACHER_BINARY,TEACHER_SHA
from .method_ledger import MethodLedger
from .preflight import atomic_json,science_files,scientific_code_binding,score_source
from .scoring import aggregate
from .source_inference import predict_source
from .source_interface_learning import learn_source_interfaces
from .source_interfaces import fit_source_examples
from .source_learning import DurableOracle
from .thinking import select_thinking
from .strict_contract import obj


OFFLINE_RECEIPT='reports/rr_method_runtime_20261107/offline_method_run_v8.json'


def prepare_method_run(root,run_id):
    root=Path(root);cfg=json.loads((root/'configs/rr_v2_preflight.json').read_text())
    manifest=json.loads((root/cfg['source_manifest']).read_text())
    authorization=json.loads((root/'docs/rr_v2/method_runtime_authorization_20261107.json').read_text())
    protocol=json.loads((root/'reports/legalskillguard_rule_reasoning_protocol_v2.json').read_text())
    files=science_files(root);offline=json.loads((root/OFFLINE_RECEIPT).read_text())
    if offline['exit_code'] or not offline['network_blocked'] or offline['files']!=files:
        raise ValueError('Current method runtime requires matching offline evidence')
    if hashlib.sha256(Path(TEACHER_BINARY).read_bytes()).hexdigest()!=TEACHER_SHA:
        raise ValueError('Original pinned teacher resource changed')
    with sqlite3.connect('file:'+str(root/cfg['ledger_path'])+'?mode=ro',uri=True) as db:
        if db.execute("select 1 from calls where status='reserved'").fetchone():
            raise BudgetError('Reconcile the existing physical request before preparing a run')
        baseline=dict(db.execute('select role,count(*) from calls group by role'))
    sources={'train':manifest['formal_train_order'],
        'dev':[s['key'] for bank in manifest['split']['datasets'].values() for s in bank['dev']]}
    if len(sources['train'])!=128 or len(sources['dev'])!=40 or len(manifest['pilot_order'])!=20:
        raise ValueError('Original source scope changed')
    if set(sources['train'])&set(sources['dev']):raise ValueError('TRAIN/DEV overlap')
    config={'executor':cfg['executor'],'teacher':{**cfg['teacher'],'executable':TEACHER_BINARY},
        'original_protocol_methods':protocol['methods'],'original_per_prediction_tools':protocol['evaluation'],
        'train_calls_per_source':2,'teacher_attempts_per_batch':2,'oracle_views_per_source':4,
        'sources_per_batch':16,'prediction_calls_including_fallback':3,
        'thinking_comparison':'one fixed20 paired current two-parse pipeline; no fallback/teacher/extra views',
        'oracle_artifacts':'artifacts/rr_v2_preflight/oracle_guard'}
    seal={'run_id':run_id,'files':files,'code_hash':scientific_code_binding(files),'config':config,
        'source_manifest_hash':digest(manifest),'source_manifest':cfg['source_manifest'],
        'data_hash':manifest['data_hash'],'sources':sources,'thinking_sources':manifest['pilot_order'],
        'ledger_path':cfg['ledger_path'],'authorization_hash':digest(authorization),
        'offline_receipt_hash':digest(offline),'baseline_counts':baseline,
        'test_authorized':False,'paper_authorized':False,'full_goal_complete':False}
    stage=root/'artifacts/rr_method_runtime_20261107'/run_id
    immutable_json(stage/'seal.json',seal)
    return {'prepared':True,'run_id':run_id,'baseline_counts':baseline,'new_model_calls':0}


class MethodRun:
    def __init__(self,root,run_id):
        self.root=Path(root);self.run_id=run_id
        self.stage=self.root/'artifacts/rr_method_runtime_20261107'/run_id
        self.seal=json.loads((self.stage/'seal.json').read_text())
        self.config=self.seal['config'];self.verify()
        self.manifest=json.loads((self.root/self.seal['source_manifest']).read_text())
        if digest(self.manifest)!=self.seal['source_manifest_hash']:raise ValueError('Original manifest changed')

    def verify(self):
        if science_files(self.root)!=self.seal['files']:raise ValueError('Frozen scientific method files changed')

    def packet(self,kind,partition):
        if partition not in {'train','dev'}:raise BudgetError('No TEST packet in the current runtime')
        folder=self.root/'data/packets/rr_v2'
        path=folder/(f'public_{partition}.json' if kind=='public' else f'grading_only/{partition}.json')
        if kind not in {'public','grading'}:raise ValueError('Unknown packet kind')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=self.manifest['packet_sha256'][kind+'_'+partition]:
            raise ValueError('Original data packet changed')
        data=json.loads(path.read_text())
        if data['split']!=partition:raise ValueError('Wrong packet partition')
        if kind=='public' and data['contains_gold_or_reference_program']:raise ValueError('Public packet contains grading data')
        if kind=='grading' and not data['never_to_actor_or_teacher']:raise ValueError('Grading packet lacks isolation marker')
        return data['sources']

    def clients(self,phase,thinking):
        config=deepcopy(self.config);config['executor']['enable_thinking']=thinking
        identity={'config':config,'phase':phase}
        if phase=='dev':identity['parent_build']=digest(json.loads((self.stage/'build/completion.json').read_text()))
        binding={'code_hash':self.seal['code_hash'],'config_hash':digest(identity)}
        ledger=MethodLedger(self.root/self.seal['ledger_path'],run_id=self.run_id+':'+phase,binding=binding,
            sources=self.seal['sources'],authorization_hash=self.seal['authorization_hash'],
            question='Current fixed128 source-scoped A/B method; '+phase)
        stage=self.stage/phase
        return ledger,MethodExecutor(ledger,stage,config['executor']),MethodTeacher(ledger,stage,config['teacher']),binding

    def dispatcher(self,ledger,executor,source,prefix,purpose,thinking):
        def generate(messages,*,purpose: str,step,schema):
            self.verify()
            actual='method_primitive_observation' if dispatch_purpose=='method_train_synthesis' and \
                set(schema.get('properties',{}))=={'observations'} else dispatch_purpose
            return executor.generate(prefix+':'+str(step),source=source['key'],purpose=actual,
                messages=messages,thinking=thinking,schema=schema)
        dispatch_purpose=purpose
        return generate

    def thinking_profile(self,source,thinking,ledger,executor,binding,profiles):
        """One original comparison unit, also used by exact paid-wire replay."""
        source_id=source['key']
        if source_id not in self.seal['thinking_sources'] or type(thinking) is not bool:
            raise ValueError('Only an original fixed20 comparison profile is allowed')
        path=self.stage/'thinking'/'records'/(digest((source_id,thinking))+'.json')
        if path.exists():record=json.loads(path.read_text())
        else:
            prefix=ledger.run_id+':'+digest(source_id)+':'+str(thinking)
            prediction=predict_source(source,arm='M11',library={'frozen':False,'patterns':[]},
                generate=self.dispatcher(ledger,executor,source,prefix,'method_thinking_comparison',thinking),
                tokenize=executor.tokenize,request_config=self.config['executor'],thinking=thinking,
                partition='train',controlled_shortcut=False,journal=self.stage/'thinking'/'journals'/digest((source_id,thinking)))
            grade=self.packet('grading','train')[source_id]
            score=score_source(source,prediction['result'],grade)
            calls=prediction['calls'];usage_known=all(isinstance(c.get('usage'),dict) for c in calls)
            record={'source':source_id,'dataset':source['dataset'],'thinking':thinking,'binding':binding,
                'prediction':prediction,'score':score,'task_correct':score['task_correct'],
                'structural_pass':any(h.get('structural_pass') for h in prediction['history']),
                'usage':{'prompt_tokens':sum(c['usage']['prompt_tokens'] for c in calls),
                         'completion_tokens':sum(c['usage']['completion_tokens'] for c in calls)} if usage_known else None,
                'elapsed_seconds':sum(c.get('elapsed_seconds') or 0 for c in calls),
                'reasoning_present':any(c.get('reasoning_content_present') for c in calls),
                'template_profile_observed':profiles['different_actual_templates'],'actual_backend_effect_verified':False,
                'source_hash':source['content_hash'],'comparison_unit':'whole bounded two-parse source pipeline'}
            immutable_json(path,record)
        if record['binding']!=binding or record['source_hash']!=source['content_hash']:
            raise ValueError('Thinking comparison record changed')
        return record

    def thinking(self):
        phase='thinking';ledger,executor,_,binding=self.clients(phase,False)
        probe=[{'role':'user','content':'Verify the configured chat-template thinking switch.'}]
        on=executor.tokenize(probe,thinking=True);off=executor.tokenize(probe,thinking=False)
        profiles={'on_tokens_hash':digest(on['tokens']),'off_tokens_hash':digest(off['tokens']),
            'different_actual_templates':on['tokens']!=off['tokens'],'model':self.config['executor']['model']}
        immutable_json(self.stage/phase/'template_profiles.json',profiles)
        public={s['key']:s for s in self.packet('public','train')};records=[]
        for source_id in self.seal['thinking_sources']:
            source=public[source_id]
            for thinking in (True,False):
                record=self.thinking_profile(source,thinking,ledger,executor,binding,profiles)
                records.append(record)
                print(json.dumps({'stage':'thinking','complete_profiles':len(records),'source':source_id,
                    'thinking':thinking,'structure':record['structural_pass'],'correct':record['task_correct']}),flush=True)
        selection=select_thinking(records,self.seal['thinking_sources'])
        # The user's current preference supersedes the historical default-ON
        # Pareto rule. Faster failures or format-only passes are no benefit.
        original_recommendation=selection['selected_thinking']
        semantic_gain=selection['stats']['true']['task_correct']>selection['stats']['false']['task_correct']
        selection.update(selected_thinking=semantic_gain and not selection['engineering_block'],
            historical_pareto_policy_recommendation=original_recommendation,
            demonstrated_net_semantic_gain=semantic_gain,
            selection_rule='current_user_default_OFF_unless_paired_core_semantic_gain; report_measured_tokens_and_time')
        selection.update(binding=binding,records_hash=digest(records),new_teacher_calls=0,
            comparison='one paired current source pipeline on the original fixed20; at most two parsing calls/profile; no native fallback',
            extra_sweep_authorized=False,full_goal_complete=False)
        immutable_json(self.stage/'thinking_selection.json',selection)
        return selection

    def selected(self):
        value=json.loads((self.stage/'thinking_selection.json').read_text())
        config=deepcopy(self.config);config['executor']['enable_thinking']=False
        expected={'code_hash':self.seal['code_hash'],'config_hash':digest({'config':config,'phase':'thinking'})}
        records=[json.loads((self.stage/'thinking/records'/(digest((source,mode))+'.json')).read_text())
                 for source in self.seal['thinking_sources'] for mode in (True,False)]
        if (value['binding']!=expected or value['records_hash']!=digest(records) or
                value['engineering_block'] or any(r['binding']!=expected for r in records)):
            raise ValueError('Current thinking/contract verification is unresolved; no blind extra switch sweep')
        return value['selected_thinking']

    def summarize(self,teacher,ledger,records,library,batch):
        path=self.stage/'build'/'teacher_batches'/f'B{batch}.json'
        source_ids=[r['source'] for r in records]
        if path.exists():
            result=json.loads(path.read_text())
            if result['source_ids']!=source_ids or result['library_hash']!=digest(library.export()):
                raise ValueError('Teacher batch snapshot differs')
            return result
        common=[{'source':r['source'],'dataset':r['dataset'],
            'program_status':r['prediction']['result']['program_status'],
            'certificate_status':r['prediction']['result']['certificate_status'],
            'learning_status':r['learning']['status'],'refinement':r['learning'].get('refinement'),
            'pattern':r['learning'].get('learned_pattern')} for r in records]
        pattern=obj({'fields':{'type':'array','items':{'type':'string'}},
            'graphs':{'type':'array','items':{'type':'string'}},'basis':{'type':'string'},
            'universal_semantic_equivalence_claim':{'type':'boolean'}})
        schema=obj({'patterns':{'type':'array','items':pattern},'notes':{'type':'string'}})
        response=None;errors=[]
        for attempt in range(2):
            try:
                response=teacher.summarize(ledger.run_id+f':teacher:B{batch}:{attempt}',source_ids=source_ids,
                    system_prompt='Summarize only observed source-grounded patterns. No tools. Do not invent verified laws, fields, labels or routing IDs. Encode each graph as a JSON string; unverified proposals remain unverified.',
                    user_prompt=json.dumps({'common_training_records':common,'library':library.export(),
                        'previous_transport_or_schema_errors':errors},ensure_ascii=False),output_schema=schema)
                break
            except BudgetError:raise
            except Exception as exc:errors.append({'type':type(exc).__name__,'message':str(exc)})
        known={p['pattern_hash'] for p in library.patterns};accepted=[];pending=[]
        if response:
            for item in response['value']['patterns']:
                try:
                    proposal={**item,'graphs':[json.loads(g) for g in item['graphs']]}
                    key=SkillLibrary().add(proposal,source='common_batch')
                    if key in known:accepted.append(key)
                    else:pending.append({'proposal':proposal,'reason':'not_verified_by_common_training_evidence'})
                except (ValueError,TypeError,KeyError) as exc:pending.append({'proposal':item,'reason':str(exc)})
        result={'source_ids':source_ids,'library_hash':digest(library.export()),'response':response,
            'errors':errors,'accepted_pattern_hashes':accepted,'pending_proposals':pending,
            'status':'summary_recorded' if response else 'two_teacher_attempts_failed'}
        immutable_json(path,result);return result

    def build(self):
        thinking=self.selected();ledger,executor,teacher,binding=self.clients('build',thinking)
        public={s['key']:s for s in self.packet('public','train')};grades=self.packet('grading','train')
        library=SkillLibrary(stage='formal_train');completed=[]
        state_path=self.stage/'build/state.json'
        committed_prefix=json.loads(state_path.read_text())['complete_sources'] if state_path.exists() else 0
        for source_id in self.seal['sources']['train']:
            self.verify();source=public[source_id];before=digest(library.export())
            path=self.stage/'build'/'sources'/(digest(source_id)+'.json')
            if path.exists():record=json.loads(path.read_text())
            else:
                prefix=ledger.run_id+':'+digest(source_id)
                prediction=predict_source(source,arm='M11',library=library.export(),
                    generate=self.dispatcher(ledger,executor,source,prefix,'method_train_synthesis',thinking),
                    tokenize=executor.tokenize,request_config=executor.config,thinking=thinking,partition='train',
                    journal=self.stage/'build'/'journals'/digest(source_id))
                oracle=DurableOracle(ledger,self.root/self.config['oracle_artifacts'],source,grades[source_id])
                learning=learn_source_interfaces(source,grades[source_id],oracle,program=prediction['program'],
                    observation_rows=prediction['observation_rows'],library=library.export())
                record={'source':source_id,'dataset':source['dataset'],'binding':binding,
                    'input_hash':source['content_hash'],'library_before_hash':before,'prediction':prediction,
                    'calls':prediction['calls'],'learning':learning,'score':score_source(source,prediction['result'],grades[source_id]),
                    'model_source_IR_semantic_faithfulness':'requires source review beyond TRAIN label match'}
                immutable_json(path,record)
            if record['binding']!=binding or record['input_hash']!=source['content_hash'] or record['library_before_hash']!=before:
                raise ValueError('Current build resume source/library/version mismatch')
            if record['learning'].get('learned_pattern'):library.add(record['learning']['learned_pattern'],source=source_id)
            completed.append(record)
            if len(completed)%16==0:
                batch=len(completed)//16;summary=self.summarize(teacher,ledger,completed[-16:],library,batch)
                snapshot={'binding':binding,'batch':batch,'source_record_hashes':[digest(r) for r in completed],
                    'sources':[r['source'] for r in completed],'library':library.export(),'teacher_summary':summary}
                immutable_json(self.stage/'build'/'batches'/f'B{batch}.json',snapshot)
                for row in completed[-16:]:
                    grade=grades[row['source']];labels=grade['targets'] if row['dataset']=='OpenExempt' else {'answer':grade['answer']}
                    proposals=[{'raw_content':c['raw_content'],'analysis':c['analysis'],'wire_request_hash':c['request_hash']} for c in row['calls']]
                    material=SharedMaterial(row['source'],proposals,labels,row['learning']['oracle_views'],summary,
                        [row['learning']['learned_pattern']] if row['learning'].get('learned_pattern') else [])
                    immutable_json(self.stage/'build'/'arm_shared_material'/(digest(row['source'])+'.json'),
                        {arm:project_material(material,arm) for arm in ARMS})
                if batch in {1,8}:
                    SkillLibrary(library.patterns,stage=f'formal_B{batch}').freeze(self.stage/'build'/f'B{batch}.frozen.json')
                    families,_=_fit_horn_examples(public,completed,grades)
                    immutable_json(self.stage/'build'/f'B{batch}.MB.frozen.json',fit_source_examples(completed,horn_families=families))
            if len(completed)>=committed_prefix:
                atomic_json(state_path,{'complete_sources':len(completed),'completed_batches':len(completed)//16,
                    'source_hashes':[digest(r) for r in completed],'binding':binding,'full_goal_complete':False})
            print(json.dumps({'stage':'build','complete_sources':len(completed),'source':source_id,
                'A':record['prediction']['result']['A_main_path_executed'],'B':record['prediction']['result']['B_main_path_executed'],
                'learning':record['learning']['status'],'TRAIN_match':record['score']['task_correct']}),flush=True)
        result={'build_complete':True,'sources':128,'batches':8,'binding':binding,'library_hash':digest(library.export()),
            'source_hashes':[digest(r) for r in completed],'thinking':thinking,'DEV_complete':False,'full_goal_complete':False,
            'frozen_files':{name:hashlib.sha256((self.stage/'build'/name).read_bytes()).hexdigest()
                for name in ('B1.frozen.json','B8.frozen.json','B1.MB.frozen.json','B8.MB.frozen.json')}}
        immutable_json(self.stage/'build'/'completion.json',result);return result

    def verify_build(self):
        completion=json.loads((self.stage/'build/completion.json').read_text())
        if (not completion['build_complete'] or completion['sources']!=128 or completion['batches']!=8
                or len(completion['source_hashes'])!=128):raise ValueError('Incomplete shared build')
        for name,sha in completion['frozen_files'].items():
            if hashlib.sha256((self.stage/'build'/name).read_bytes()).hexdigest()!=sha:
                raise ValueError('Frozen build artifact changed: '+name)
        library=SkillLibrary(stage='formal_train')
        for index,source in enumerate(self.seal['sources']['train']):
            row=json.loads((self.stage/'build/sources'/(digest(source)+'.json')).read_text())
            if (digest(row)!=completion['source_hashes'][index] or row['source']!=source or
                    row['binding']!=completion['binding'] or row['library_before_hash']!=digest(library.export())):
                raise ValueError('Shared source prefix or version differs')
            if row['learning'].get('learned_pattern'):library.add(row['learning']['learned_pattern'],source=source)
            if index+1 in {16,128}:
                batch=(index+1)//16
                expected=SkillLibrary(library.patterns,frozen=True,stage=f'formal_B{batch}').export()
                if SkillLibrary.restore(self.stage/'build'/f'B{batch}.frozen.json').export()!=expected:
                    raise ValueError('Frozen library includes an incompatible/future source prefix')
        if digest(library.export())!=completion['library_hash']:raise ValueError('Final source/library identity differs')
        return completion

    def dev(self):
        complete_build=self.verify_build()
        if not complete_build['build_complete'] or complete_build['sources']!=128:raise ValueError('DEV requires all128 source records')
        thinking=self.selected();ledger,executor,_,binding=self.clients('dev',thinking)
        library=SkillLibrary.restore(self.stage/'build/B8.frozen.json').export()
        examples=json.loads((self.stage/'build/B8.MB.frozen.json').read_text())
        public=self.packet('public','dev');predictions={}
        for arm in ARMS:
            predictions[arm]={}
            for source in public:
                self.verify();source_id=source['key'];path=self.stage/'dev'/'predictions'/arm/(digest(source_id)+'.json')
                if path.exists():record=json.loads(path.read_text())
                else:
                    prediction=predict_source(source,arm=arm,library=library,
                        generate=self.dispatcher(ledger,executor,source,ledger.run_id+':'+arm+':'+digest(source_id),'method_dev',thinking),
                        tokenize=executor.tokenize,request_config=executor.config,thinking=thinking,partition='dev',
                        example_model=examples if arm=='MB' else None,journal=self.stage/'dev'/'journals'/arm/digest(source_id))
                    record={'binding':binding,'input_hash':source['content_hash'],'prediction':prediction}
                    immutable_json(path,record)
                if record['binding']!=binding or record['input_hash']!=source['content_hash']:raise ValueError('DEV resume identity changed')
                predictions[arm][source_id]=record['prediction']
                print(json.dumps({'stage':'dev','arm':arm,'complete_sources':len(predictions[arm]),'source':source_id}),flush=True)
        # No DEV labels are opened until every arm/source prediction is saved.
        grades=self.packet('grading','dev');scores={};source_scores={}
        expected={(s['dataset'],s['key'],v) for s in public for v in (['EC','EV'] if s['dataset']=='OpenExempt' else ['main'])}
        for arm,rows in predictions.items():
            records=[];source_scores[arm]={}
            for source in public:
                prediction=rows[source['key']]['result'];score=score_source(source,prediction,grades[source['key']])
                source_scores[arm][source['key']]=score
                for view,value in score['views'].items():
                    records.append({'dataset':source['dataset'],'source':source['key'],'view':view,
                        'correct':value['correct'],'answered':prediction['answer'] is not None,
                        'certificate_status':prediction['certificate_status']})
            scores[arm]=aggregate(records,expected_outputs=expected)
        result={'scores':scores,'source_scores':source_scores,'outputs_per_arm':48,'sources_per_arm':40,
            'binding':binding,'DEV_complete':True,'TEST_started':False,'full_goal_complete':False}
        immutable_json(self.stage/'dev'/'scores.json',result);return result
