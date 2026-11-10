"""Independent native references: TRAIN supervision and grading only.

These functions are never prediction tools. SARA checks only original selected
TRAIN cases, with their original facts and full official Prolog dependency set.
No reference clause or fact is inserted into a model's generated program.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import tarfile
import time

from .data import load_json,write_json,sha


def sara_reference_audit(root,out):
    root=Path(root);out=Path(out);location=out/'reference_sara';location.mkdir(parents=True,exist_ok=True)
    release=root/'data/cache/rr_v2/sara_v2.tar.gz'
    prolog_root=root/'.local-tools/swi-prolog/root'
    binary=prolog_root/'usr/lib/swi-prolog/bin/amd64/swipl'
    env=dict(os.environ,SWI_HOME_DIR=str(prolog_root/'usr/lib/swi-prolog'),LD_LIBRARY_PATH=str(prolog_root/'usr/lib'))
    rows=[r for r in load_json(out/'open_dataset.json')['records'] if r['dataset']=='SARA_v2_Binary' and r['split']=='train']
    records=[];native_supervision=[];source_hashes={}
    with tarfile.open(release) as archive:
        for member in archive.getmembers():
            if not member.isfile() or not member.name.startswith('sara_v2/statutes/prolog/') or Path(member.name).name.startswith('._'):continue
            relative=Path(member.name).relative_to('sara_v2');dest=location/relative
            dest.parent.mkdir(parents=True,exist_ok=True);data=archive.extractfile(member).read();dest.write_bytes(data)
            source_hashes[str(relative)]=hashlib.sha256(data).hexdigest()
        for row in rows:
            cid=row['grade']['original_id'];text=archive.extractfile('sara_v2/cases/'+cid+'.pl').read().decode()
            fact=text.split('% Facts',1)[1].split('% Test',1)[0].strip()
            test=text.split('% Test',1)[1].strip();test=re.sub(r':-\s*halt\s*\.\s*$','',test).strip()
            if not test.startswith(':-') or not test.endswith('.'):raise ValueError('Unknown original SARA test directive')
            goal=test[2:-1].strip()
            negated=goal.startswith('\\+')
            if negated:goal=goal[2:].strip()
            elif goal.startswith('not(') and goal.endswith(')'):goal=goal[4:-1].strip();negated=True
            # Preserve the official logical predicate. We invert only the
            # explicit original test's negation to expose native E/C polarity.
            case_file=location/('case_'+hashlib.sha256(row['key'].encode()).hexdigest()[:16]+'.pl')
            case_file.write_text(fact+'\ncheck_native_case :- ('+goal+').\n')
            query="(catch(call_with_time_limit(10,check_native_case), E, (print_message(error,E),halt(3))) -> write('REFERENCE_ENTAILMENT') ; write('REFERENCE_CONTRADICTION')), halt."
            begin=time.monotonic()
            try:
                process=subprocess.run([str(binary),'-q','-s',str(case_file),'-g',query],cwd=location,env=env,text=True,capture_output=True,timeout=15)
                answer='Entailment' if 'REFERENCE_ENTAILMENT' in process.stdout else 'Contradiction' if 'REFERENCE_CONTRADICTION' in process.stdout else None
                valid=process.returncode==0 and answer is not None
                record={'key':row['key'],'original_case_id':cid,'expected':row['grade']['answer'],
                        'reference_answer':answer,'reference_executed':valid,'matches_original_label':valid and answer==row['grade']['answer'],
                        'returncode':process.returncode,'stderr':process.stderr[-4000:],'seconds':time.monotonic()-begin,
                        'original_negative_directive':negated,'reference_calls':1}
            except Exception as e:record={'key':row['key'],'original_case_id':cid,'reference_executed':False,'matches_original_label':False,'error':type(e).__name__+': '+str(e),'reference_calls':1,'seconds':time.monotonic()-begin}
            records.append(record)
            native_supervision.append({'key':row['key'],'original_case_id':cid,'official_fact_section':fact,
                'official_direct_query':goal,'verified_for_original_case':record['matches_original_label'],
                'actor_input':False,'source_alignment_claim':'native author-provided case representation; no invented source spans or full natural-language rule AST'})
            print(json.dumps({k:record.get(k) for k in ('original_case_id','reference_executed','matches_original_label','reference_answer','error')},ensure_ascii=False),flush=True)
    result={'sources':len(rows),'original_cases_only':True,'TEST_or_DEV_cases_executed':0,
        'raw_release_sha256':sha(release),'prolog_version':'SWI-Prolog7.6.4 isolated Ubuntu package',
        'reference_source_hashes':source_hashes,'records':records,
        'verified':sum(r['matches_original_label'] for r in records),
        'arbitrary_counterfactual_oracle_claimed':False,'new_model_calls':0}
    write_json(out/'sara_native_reference_audit.json',result);write_json(out/'sara_native_supervision.json',native_supervision)
    return result
