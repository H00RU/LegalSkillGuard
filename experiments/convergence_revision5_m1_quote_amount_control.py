"""Reuse actual TRAIN responses to check an identically available literal-amount control."""

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import re
import sqlite3

from experiments.convergence_formal_b1_observe import load_roster
from experiments.convergence_formal_bootstrap import POINTER
from experiments.convergence_formal_train_observe import pointer as observe_pointer
from experiments.convergence_m1_incumbent_audit import DATASET, M1, _verify_reads
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha
from legal_skill_guard.paired_interfaces import diversity_claim_groups, relational_program, residual
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view, restore_enum_transport


HOME = BASE/'revision5_m1_amount_polarity_20261119'
AMOUNT = r'\$(?:[1-9][0-9]{0,2}(?:,[0-9]{3})+|[1-9][0-9]*|0)'
CLAIM = rf'[A-Za-z]+(?: [A-Za-z]+)* for ({AMOUNT})'
CLAUSES = {n:re.compile(' and '.join([CLAIM]*n)+r'\.') for n in (1,2)}


def quote_amounts(quote, count):
    _, separator, tail = quote.partition(' for ')
    match = CLAUSES[count].fullmatch(tail)
    if not separator or not match:
        raise ValueError('Outside the explicit one- or two-claim Diversity clause syntax')
    numbers = [int(amount[1:].replace(',','')) for amount in match.groups()]
    if any(amount % 1000 for amount in numbers):
        raise ValueError('Fractional thousands are outside the certified coordinate domain')
    return {f'claim{i}':min(amount//1000,76) for i,amount in enumerate(numbers)}


def score(source, view, raw, plan, labels):
    outputs=relational_program.decode(plan['relational_program'],raw,view['relational_public_source'])['outputs']
    task, = source['views']
    return grade_view(DATASET,task,labels[task['id']],outputs[task['id']])['grade']


def run():
    assert quote_amounts('A sues B for negligence for $75,000.',1)=={'claim0':75}
    assert quote_amounts('A sues B for negligence for $40,000 and defamation for $36,000.',2)=={'claim0':40,'claim1':36}
    for quote in ('A sues B for negligence for $75,001.', 'A sues B for negligence for $75,000.99.',
                  'A sues B for negligence for $75,000 or $80,000.'):
        try:
            quote_amounts(quote,1)
        except ValueError:
            pass
        else:
            raise ValueError('Unsupported source numbers must fail closed')
    root=ROOT/read(POINTER)['artifact_root']
    study=read(root/'binding.json')
    batches=load_roster(study)
    source_map={s['key']:(n,s) for n,b in enumerate(batches,1) for s in b if s['dataset']==DATASET}
    bank=TrainingJournal(root,study,batches).library(M1,8)['interface_library']['observations']
    _verify_reads(bank)
    provider=diversity_claim_groups.Provider()
    views={k:provider.views(source)[0] for k,(_,source) in source_map.items()}
    grade=ROOT/read(HANDOFF/'diversity_train_current.json')['artifact_root']/'grading.json'
    observed=read(ROOT/read(observe_pointer(8))['artifact_root']/'binding.json')
    assert ROOT/observed['native_grade_paths'][DATASET]==grade
    assert observed['native_grade_sha256'][observed['native_grade_paths'][DATASET]]==sha(grade)
    labels=read(grade)
    original_path=ROOT/read(HANDOFF/'M1_incumbent_through_B8_20261118.json')['receipt']
    original=read(original_path)
    forward={r['source']:r for r in original['folds']}
    physical_scores={}
    totals=Counter()
    changed_amounts=Counter()
    coordinate_vs_relation=Counter()
    paired_by_citizenship={}
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        db.execute('begin')
        ledger_before=db.execute('select count(*) from calls').fetchone()[0]
        for row in bank:
            key=row['source']
            batch,source=source_map[key]
            view=views[key]
            plan=next(p for p in view['plans'] if p['version']==row['plan_version'])
            choices=plan['choices']
            citizen=choices['citizenship']
            amount, = [pick for kind,pick in choices.items() if kind!='citizenship']
            body=json.loads(db.execute('select result from calls where id=?',(row['physical_call_id'],)).fetchone()[0])
            prior,_=restore_enum_transport(json.loads(body['content']),plan['schema'])
            current=deepcopy(prior)
            anchors={u['source_anchor']:u for u in view['read_input']['unit_requests']}
            rewritten=0
            for key_unit,unit in plan['relational_program']['units'].items():
                kind=unit['template_key'].split(':',1)[0]
                if kind=='citizenship':
                    continue
                raw=current[key_unit]
                evidence, = raw['evidence']
                quote=evidence['quote']
                if (evidence['field']!='source_text' or [quote]!=anchors[key_unit]['source_excerpts']
                        or raw['status']!='complete' or raw['observation']['source_anchor']!=key_unit):
                    raise ValueError('Use only the actual verified source-local claim quote')
                coordinates=quote_amounts(quote,unit['entity_context']['claim_count'])
                new=residual.encode(unit['asset']['features'],coordinates)
                rewritten+=raw['observation']['relations']!=new
                raw['observation']['relations']=new
                totals['quoted_amount_units']+=1
            before=score(source,view,prior,plan,labels[key])
            after=score(source,view,current,plan,labels[key])
            assert before==row['native_utility']
            totals['stored_candidate_reads']+=1
            tag=f'citizenship_{citizen}_amount_{amount}'
            changed_amounts[tag]+=rewritten
            physical_scores[row['physical_call_id']]=(before,after)
            paired_by_citizenship.setdefault((key,citizen),{})[amount]=(before,after)
            for sample in ('all_TRAIN',*(('chronological_B2_B8',) if batch>=2 else ())):
                totals[sample,tag,'sources']+=1
                totals[sample,tag,'before']+=int(before)
                totals[sample,tag,'after']+=int(after)
        assert db.execute('select count(*) from calls').fetchone()[0]==ledger_before
    for (key,citizen),data in paired_by_citizenship.items():
        assert len(data)==2
        coordinate_vs_relation[f'citizenship_{citizen}',f'{int(data[0][1])}->{int(data[1][1])}']+=1
    selected=Counter()
    for r in forward.values():
        physical=r['current'].get('physical_call_id')
        before,after=(physical_scores[physical] if physical else (r['current']['native'],)*2)
        assert before==r['current']['native']
        selected[f'{int(before)}->{int(after)}']+=1
    aggregate={'methods':{'amount_0':'fixed_coordinates','amount_1':'synthesized_amount_relation',
                          'citizenship_0':'fixed_coordinates','citizenship_1':'synthesized_citizenship_relation'},
               'cached_TRAIN_reads':totals['stored_candidate_reads'],'quoted_amount_units':totals['quoted_amount_units'],
               'rewritten_amount_units':dict(changed_amounts),
               'native_correct':{sample:{tag:{metric:totals[sample,tag,metric] for metric in ('sources','before','after')}
                                         for tag in sorted(changed_amounts)} for sample in ('all_TRAIN','chronological_B2_B8')},
               'matched_amount_native_pairs_after_common_literal_read':{
                   k:{f:n for (t,f),n in coordinate_vs_relation.items() if t==k}
                   for k in ('citizenship_0','citizenship_1')},
               'original_chronological_route_pairs_with_only_amount_replaced':dict(selected),
               'new_model_calls':0,'ledger_rows':ledger_before,'TEST_opened':False,
               'original_train_grade_sha256':sha(grade),'forward_selection_sha256':sha(original_path),
               'source_sha256':sha(Path(__file__))}
    assert aggregate['cached_TRAIN_reads']==96
    immutable_json(HOME/'literal_amount_control.json',aggregate)
    print(json.dumps(aggregate,indent=2),flush=True)


if __name__=='__main__':
    run()
