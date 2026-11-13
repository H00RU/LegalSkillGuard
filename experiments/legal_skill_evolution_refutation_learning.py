"""One finite learned source-check experiment; no old queue is resumed."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import sqlite3

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor,FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import source_spans
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.refutation_learning import BANK,validate_bank,instantiate,messages,fit
from legal_skill_guard.skill_evolution.runtime import decoder_schema
from legal_skill_guard.skill_evolution.scoped_grammar import material_public
from legal_skill_guard.skill_evolution.source_evidence_codec import schema,decode
from legal_skill_guard.skill_evolution.span_compiler import execution_source_units
from legal_skill_guard.skill_evolution.teacher_transport import INSTRUCTION,pack

ROOT=Path(__file__).resolve().parents[1]
RUN='legal_skill_evolution_refutation_learning_20261113'
OUT=ROOT/'artifacts'/RUN
PARENT=ROOT/'artifacts/legal_skill_evolution_residual_reader_20261113'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

SYSTEM='''Acquire a small bank of reusable CURRENT-SOURCE semantic interpretation
checks from the supplied original TRAIN, operation meanings, actual positive
examples and real source-refuted observations. No validation source is supplied.
Native answers already correct do not certify the source interpretation. The
old442 IR already contains a return/destroy alternative; do not repeat the prior
brief's overstatement that return was wholly absent. Actual remaining gaps are
local role readings, information scope and source qualifications/connections.

Learn checks and their evidence acquisition plans, not a regex wrong-choice to
right-choice mapping. Each check targets an acquired operation and candidate
choices. Its question_template uses {candidate_meaning}, {candidate_name} and/or
{operation_question}; these values are bound at runtime, not given truth labels.
The frozen Qwen3-8B will answer supported, refuted or unknown on the current source.
Checks must distinguish contradiction from missing context or a merely different
valid label. A rejected choice never automatically supplies a correct choice.

window_program is bounded pure Python with apply(inputs,premises), returning
ONLY {"unit_ids":[...current IDs...]}. Inputs are source_spans, query (id,
operation,unit_ids), candidate_choice and focus_unit_id. It may keep a supplied
window, resolve structural/context dependencies, or choose the entire source.
Always retain the actual focus. Choosing evidence context does not attribute
every contextual legal effect to the focus. Helpers and recursion are allowed;
no imports, introspection or external calls. Source text is available only as
current source_spans. Reusable context reading programs, no identity branches.

Return at most6 distinct complementary semantic checks, not synonym samples.
Keep target candidate_choices declared in the supplied operation. Include checks
able to protect actually supported interpretations as well as reject false ones.
Use current source semantics in the question, not TRAIN company names, source
IDs, positions, verbatim TRAIN quotations or an answer map. Do not invent new
norms, labels, fields or unknown defaults. All template legal meaning is acquired
here, not supplied by host rules. The host will measure checks on the true
frozen-reader responses and select a finite policy with ordinary subset search.
This is not a claim that selection is a new solver, or a new name for oldM1.
'''+INSTRUCTION


def prepare():
    protocol_path=OUT/'protocol.json'
    if protocol_path.exists():
        p=read(protocol_path);data=read(OUT/'input.json')
    else:
        previous=read(PARENT/'protocol.json');common=read(PARENT/'revision/common_input.json')
        public=read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')
        by_key={s['key']:s for s in public}
        sources={}
        for key in previous['train_sources']:
            pub=by_key[key]['views'][0]['public']
            units,_=execution_source_units(pub['source_text'],source_spans(material_public(pub)))
            sources[key]={'source_text':pub['source_text'],'units':units}
        acquired=read(ROOT/'artifacts/legal_skill_evolution_scope_learning_20261113/input.json')['existing_acquired_examples']
        cases=[]
        for e in acquired:
            if e['operation']!='disposal_retention_clause_role':continue
            cases.append({'id':'case_'+str(len(cases)),'source':e['source'],'operation':e['operation'],
                'focus_unit_id':e['focus_unit_id'],'unit_ids':e['quote_unit_ids'],
                'candidate_choice':e['choice'],'status':'supported',
                'origin':'Actual acquired TRAIN example, with source role interpretation reviewed; positive only, not exhaustive.'})
        feedback=read(PARENT/'revision/source_feedback.json')
        for r in feedback['current_source_negative_cases']:
            base={'source':r['source'],'operation':r['operation'],'focus_unit_id':r['focus_unit_id'],'unit_ids':r['unit_ids']}
            cases.append({**base,'id':'case_'+str(len(cases)),
                'candidate_choice':r['observed_answer']['choice'],'status':'rejected',
                'origin':'Actual frozen-reader answer explicitly refuted by TRAIN source review; no native label.'})
            if len(r['admissible_positive_examples_not_exhaustive'])==1:
                cases.append({**base,'id':'case_'+str(len(cases)),
                    'candidate_choice':r['admissible_positive_examples_not_exhaustive'][0],'status':'supported',
                    'origin':'Unambiguous positive interpretation in the same explicit source review.'})
        assert len(cases)==12 and sum(c['status']=='rejected' for c in cases)==4
        excluded=set(previous['train_sources']+previous['validation_sources']+
                     previous['closed_reuse_not_repeated']+previous['inherited_initial_acquisition_exposure'])
        validation=[s['key'] for s in public if s['dataset']=='ContractNLI' and s['key'] not in excluded][:2]
        assert len(validation)==2
        data={'operations':common['seed']['operations'],'sources':sources,'training_cases':cases,
            'explicit_source_negative_feedback':feedback,
            'scope':'Original4 TRAIN only. Candidate statuses do not require an exclusive single gold label. No current validation data.'}
        paths=[Path(__file__).resolve(),ROOT/'legal_skill_guard/skill_evolution/refutation_learning.py',
            ROOT/'tests/test_skill_evolution_refutation_learning.py']
        with sqlite3.connect(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3') as c:
            rows=[list(r) for r in c.execute('select * from calls order by id')]
        assert len(rows)==9615 and not any(r[6]=='reserved' for r in rows)
        p={'same_goal':True,'goal_complete':False,'run_id':RUN,
            'train_sources':previous['train_sources'],'validation_sources':validation,
            'validation_selection':'First2 original native TRAIN IDs outside original8 acquisition, closed reuse and the last2 fixed validation. No body/label-based selection; historical exposure retained.',
            'input_sha256':digest(data),'system':SYSTEM,'executor_profile':previous['executor_profile'],
            'teacher_profile':previous['teacher_profile'],
            'source_sha256':{str(q.relative_to(ROOT)):sha(q) for q in paths},
            'learning':'Measure each acquired check on explicit source-supported/refuted TRAIN candidates; lexicographic empirical subset selection protects known positives, covers known negatives and reduces checks. Unknown never refutes.',
            'controls':['Generic source judge with same TRAIN feedback','Same-material error-repair retrieval','All acquired checks','No checks / unchanged reader'],
            'next_stage_conditional':'Freeze before any validation. Do not expand if calibration has no useful test or ordinary same-information checks already absorb the tested difference. Fit is not reuse or method success.',
            'old_M1_family_acknowledged':True,'not_probability_channel_or_literal_regex_relabel':True,
            'no_full_training_DEV_TEST_or_paper':True,'no_new_mechanical_call_cap':True}
        immutable_json(protocol_path,p);immutable_json(OUT/'input.json',data);immutable_json(OUT/'ledger_before.json',{'rows':rows})
        for q in paths:
            dst=OUT/'source_snapshot'/q.relative_to(ROOT);dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(q.read_bytes())
    for name,h in p['source_sha256'].items():assert sha(ROOT/name)==h
    assert digest(data)==p['input_sha256']
    ledger=EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,
        sources={'train':p['train_sources']+p['validation_sources'],'dev':[],'test':[]},binding=digest(p))
    return p,data,ledger


def acquire():
    p,data,ledger=prepare();t=FrozenTeacher(ledger,OUT,p['teacher_profile'])
    result=t.propose(RUN+':teacher:check_bank',source_ids=p['train_sources'],system_prompt=p['system'],
        user_prompt=json.dumps(pack(data),ensure_ascii=False),output_schema=BANK)
    immutable_json(OUT/'teacher.json',result)
    bank=validate_bank(result['value'],data['operations'])
    for test in bank['tests']:
        for case in data['training_cases']:
            op=next(o for o in data['operations'] if o['name']==case['operation'])
            instantiate(test,case,op,data['sources'][case['source']]['units'])
    immutable_json(OUT/'validated_bank.json',bank)
    print(json.dumps({'acquired_tests':len(bank['tests']),'new_teacher_calls':int(not result.get('cache_hit',False))}),flush=True)


def calibration():
    p,data,ledger=prepare();bank=read(OUT/'validated_bank.json');client=FrozenExecutor(ledger,OUT,p['executor_profile'])
    client.readiness();observations=[]
    for key in p['train_sources']:
        target=OUT/'calibration'/(key.replace(':','_')+'.json')
        if target.exists():observations+=read(target)['observations'];continue
        units=data['sources'][key]['units'];queries=[];operations=[];focus={};binding={};rows=[]
        for case in data['training_cases']:
            if case['source']!=key:continue
            operation=next(o for o in data['operations'] if o['name']==case['operation'])
            for test in bank['tests']:
                item=instantiate(test,case,operation,units)
                if item is None:
                    rows.append({'case':case['id'],'test':test['name'],'verdict':'inapplicable'});continue
                op,q=item;operations.append(op);queries.append(q);focus[q['id']]=case['focus_unit_id']
                binding[q['id']]={'case':case['id'],'test':test['name']}
        events=[]
        if queries:
            prompt=messages(operations,queries,units,focus);wire,_=decoder_schema(schema(operations,queries))
            result=client.generate(RUN+':calibration:'+key,source=key,purpose='skill_replay',
                messages=prompt,thinking=False,schema=wire)
            if result['finish_reason']!='stop':raise ValueError('Incomplete output; no implicit retry')
            _,answers=decode(operations,queries,units,result['content'])
            rows += [{**binding[a['id']],'verdict':a['choice'],'answer':a} for a in answers]
            events.append(result)
        saved={'source':key,'observations':rows,'events':events,'queries':queries,'operations':operations}
        immutable_json(target,saved);observations+=rows
        print(json.dumps({'source':key,'checks':len(queries),'refuted':sum(r['verdict']=='refuted' for r in rows)}),flush=True)
    learned=fit(bank['tests'],data['training_cases'],observations)
    immutable_json(OUT/'learned_policy.json',learned)
    immutable_json(OUT/'calibration/completed.json',{'observations':observations,'policy':learned,
        'TRAIN_fit_not_reuse':True,'goal_complete':False})
    print(json.dumps(learned),flush=True)


if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('stage',choices=['prepare','acquire','calibrate']);args=a.parse_args()
    with (ROOT/'artifacts/rr_v2_preflight/current_refutation_learning_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        {'prepare':prepare,'acquire':acquire,'calibrate':calibration}[args.stage]()
