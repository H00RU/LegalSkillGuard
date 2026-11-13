"""Run source-only operational semantics probes, not benchmark evaluations.

Official statute code is an isolated reference, never supplied as learned code
or extra teacher supervision. Fixtures below are software tests, not new law
sources, benchmark cases or training labels. No official case files are read.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

from legal_skill_guard.rr.checkpoint import immutable_json

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/legal_skill_evolution_scoped_premise_repair_20261113'
SOURCE=OUT/'native_semantics_source_only'
FIXTURE=r'''
:- discontiguous s152_c_1/3.
:- discontiguous s151_b_applies/3.

s152_c_1(fixture_child,fixture_parent,2015).
s151_b_applies(fixture_owner,fixture_subject,2015).

residence_(fixture_res_child).
agent_(fixture_res_child,fixture_date_child).
patient_(fixture_res_child,fixture_home).
start_(fixture_res_child,"2015-09-01").
end_(fixture_res_child,"2019-02-03").
residence_(fixture_res_parent).
agent_(fixture_res_parent,fixture_date_parent).
patient_(fixture_res_parent,fixture_home).
start_(fixture_res_parent,"2015-09-01").
end_(fixture_res_parent,"2019-02-03").

residence_(fixture_default_child_res).
agent_(fixture_default_child_res,fixture_default_child).
patient_(fixture_default_child_res,fixture_default_home).
residence_(fixture_default_parent_res).
agent_(fixture_default_parent_res,fixture_default_parent).
patient_(fixture_default_parent_res,fixture_default_home).

probe(Name,Goal) :-
    catch((once(Goal) ->
        format('~w=true~n',[Name]);format('~w=false~n',[Name])),
        Error,format('~w=ERROR:~q~n',[Name,Error])).

reference_main :-
    probe(calendar_tax_year,first_day_year(2015,"2015-01-01")),
    probe(no_joint_return_negative_guard,s152_c_1_E(fixture_unmarried,_,2019)),
    probe(given_child_to_dependent,s152(fixture_child,fixture_parent,2015)),
    probe(given_child_to_b1,s152_b_1(fixture_child,fixture_parent,2015)),
    probe(exemption_zero_without_individual_fact,s151_d_2(fixture_subject,fixture_owner,0,2015)),
    probe(no_independent_individual_predicate,\+current_predicate(individual/1)),
    probe(early_year_residence_is_not_half,s152_c_1_B(fixture_date_child,fixture_home,fixture_date_parent,"2015-01-01","2020-12-31",2019)),
    probe(unstated_residence_endpoints_have_native_defaults,s152_c_1_B(fixture_default_child,fixture_default_home,fixture_default_parent,"2019-01-01","2019-12-31",2019)),
    probe(missing_rule_is_an_error_not_false,never_acquired_source_rule(fixture_person)),
    halt.
'''


def run():
    manifest=json.loads((SOURCE/'source_manifest.json').read_text())
    files={Path(s['member']).name:s for s in manifest['selected_files']}
    for name,entry in files.items():
        assert hashlib.sha256((SOURCE/name).read_bytes()).hexdigest()==entry['sha256']
    runtime=ROOT/'.local-tools/swi-prolog-reference/root'
    binary=runtime/'usr/lib/swi-prolog/bin/amd64/swipl'
    env={**os.environ,'LD_LIBRARY_PATH':str(runtime/'usr/lib'),
         'SWI_HOME_DIR':str(runtime/'usr/lib/swi-prolog')}
    version=subprocess.run([str(binary),'--version'],env=env,capture_output=True,text=True,check=True).stdout.strip()
    # One compilation unit keeps source rule definitions and explicit GIVEN
    # facts together; consulting another file must not replace a source predicate.
    order=['events.pl','utils.pl']+sorted(n for n in files if n.startswith('section'))
    # The portable nox package has no generated autoload index. A hard parent
    # process timeout bounds these finite probes without loading optional alarms.
    body=':- style_check(-singleton).\n:- use_module(library(lists)).\n'
    body+=':- discontiguous s152_c_1/3.\n:- discontiguous s151_b_applies/3.\n'
    body+='\n'.join((SOURCE/name).read_text() for name in order)+'\n'+FIXTURE
    started=time.monotonic()
    with tempfile.TemporaryDirectory(prefix='lsg-sara-semantics-') as folder:
        path=Path(folder)/'source_only_reference.pl';path.write_text(body)
        completed=subprocess.run([str(binary),'-q','-s',str(path),'-g','reference_main'],env=env,
            cwd=folder,capture_output=True,text=True,timeout=35)
    values=dict(line.split('=',1) for line in completed.stdout.splitlines() if '=' in line)
    expected={'calendar_tax_year':'true','no_joint_return_negative_guard':'true',
        'given_child_to_dependent':'true','given_child_to_b1':'true',
        'exemption_zero_without_individual_fact':'true','no_independent_individual_predicate':'true',
        'early_year_residence_is_not_half':'false',
        'unstated_residence_endpoints_have_native_defaults':'true'}
    verified=completed.returncode==0 and all(values.get(k)==v for k,v in expected.items())
    missing=values.get('missing_rule_is_an_error_not_false','')
    verified=verified and missing.startswith('ERROR:error(existence_error(procedure,')
    result={'scope':'Source-only operational unit probes; not native dataset scores or learned-method success.',
        'runtime':version,'runtime_exact_original_author_version':False,
        'official_source_manifest_sha256':hashlib.sha256((SOURCE/'source_manifest.json').read_bytes()).hexdigest(),
        'fixture_sha256':hashlib.sha256(FIXTURE.encode()).hexdigest(),
        'combined_program_sha256':hashlib.sha256(body.encode()).hexdigest(),
        'returncode':completed.returncode,'observed':values,'expected':expected,
        'verified':verified,'elapsed_seconds':time.monotonic()-started,
        'stderr':completed.stderr,'official_case_files_or_labels_read':False,
        'official_rule_code_sent_to_teacher':False,'new_model_requests':0,'goal_complete':False}
    immutable_json(OUT/'native_semantics_reference_execution_bounded.json',result)
    print(json.dumps({k:result[k] for k in ('runtime','observed','verified','returncode')},ensure_ascii=False))
    assert verified,result


if __name__=='__main__':run()
