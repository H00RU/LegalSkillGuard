"""TRAIN-only native-interface forensics; never augment a learned input.

Compare the original benchmark's literal convention with the current canonical
home value. Native labels and hidden case axioms are not used to repair output.
"""
from copy import deepcopy
import json
import re
import tarfile
import time

from experiments import legal_skill_evolution_payment_contract_refinement as generation
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.sara_statute_kernel import prepare_case, run_program

ROOT = generation.ROOT
OUT = ROOT / 'artifacts/legal_skill_evolution_native_alignment_diagnosis_20261115'


def run():
    public, kernels = generation.runtime.previous.data()
    sid = next(s for s in public if ':bb6b0bc1' in s)
    assert public[sid]['split'] == 'train'
    archive = ROOT / 'history/rr_v2_20261106/data/cache/rr_v2/sara_v2.tar.gz'
    with tarfile.open(archive) as source:
        raw = source.extractfile('sara_v2/cases/s3306_c_2_neg.pl').read().decode()
    prefix = raw.split('% Test', 1)[0]
    prefix = re.sub(r'^:-\s*\[statutes/prolog/init\]\.\s*$', '', prefix, flags=re.M)
    prepared = prepare_case(kernels[sid], {'facts': [], 'negative_givens': [], 'extraction_status': 'unread'})
    main = '''
diagnostic_main :-
 catch((once((''' + prepared['goal'] + ''')) -> Verdict="Entailment" ; Verdict="Contradiction"),
       Error,(term_string(Error,Detail),Verdict="execution_error")),
 (var(Detail)->Detail="none";true),
 format('~w~n~w~n',[Verdict,Detail]),halt.
'''
    # run_program enters lsg_case_main, the same fixed runtime executable.
    main = main.replace('diagnostic_main', 'lsg_case_main')
    variants = {'original_TRAIN_case_literals': prefix,
        'same_case_only_home_canonicalized': prefix.replace(
            'location_("domestic service","her home").',
            'location_("domestic service","private home").')}
    rows = []
    for name, facts in variants.items():
        started = time.monotonic()
        result = run_program(prepared['statute_program'] + '\n' + facts + '\n' + main)
        row = {'variant': name, 'stdout': result.stdout, 'stderr': result.stderr,
               'returncode': result.returncode, 'wall_time_seconds': time.monotonic()-started}
        rows.append(row)
        print(json.dumps(row), flush=True)
    immutable_json(OUT / 'result.json', {'source': sid, 'original_case': raw,
        'variants': rows, 'new_model_calls': 0, 'original_TRAIN_only': True,
        'hidden_case_premises_not_supplied_to_the_method': True,
        'no_labels_rules_or_checks_relaxed': True, 'not_method_success': True,
        'goal_complete': False})


if __name__ == '__main__':
    run()
