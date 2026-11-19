"""Preserve native notice predictions when the narrow rule lacks trigger coverage."""

import argparse
import json
from pathlib import Path
import re

from experiments.convergence_formal_b1_observe import POINTER as FIRST, load_roster
from experiments.convergence_formal_bootstrap import POINTER as BOOTSTRAP
from experiments.convergence_formal_curves import pointer as dev_pointer
from experiments.convergence_revision5_cni_compelled_notice import (
    DATASET, HOME, ROOT, TASK, TRAIN, bound_stage, estimate, read, sha, span_inventory, view_for,
)
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


AUTHORITY = re.compile(r'\b(?:subpoenas?|court orders?|orders? of (?:any |a )?court|'
                       r'courts? (?:of competent jurisdiction|or (?:other )?government\w*)|'
                       r'legal process|lawful process|judicial process|government\w*\s+(?:agenc\w*|authorit\w*|body|entit\w*)|'
                       r'regulatory\s+(?:agenc\w*|body|authorit\w*)|'
                       r'required by law|operation of law|public records disclosure|freedom of information act)\b',re.I)
COMPULSION = re.compile(r'\b(?:requir\w*|compel\w*|mandat\w*|request\w*|pursuant to|in response to|'
                        r'under the terms of|in satisfaction of)\b',re.I)
DISCLOSURE = re.compile(r'\b(?:disclos\w*|furnish\w*|produc\w*|share|public records disclosure)\b',re.I)


def possibly_compelled(view):
    """Give a lexical coverage warning, never a positive duty judgment."""
    spans = [' '.join(s.split()) for s in span_inventory(view) if s.strip()]
    for i, span in enumerate(spans):
        if not AUTHORITY.search(span):
            continue
        if COMPULSION.search(span) and DISCLOSURE.search(span):
            return True
        following = spans[i+1] if i+1<len(spans) else ''
        if COMPULSION.search(span+ ' '+following) and (DISCLOSURE.search(span) or DISCLOSURE.search(following)):
            return True
    return False


def guarded(modes, evidence, possible):
    linked = modes['linked']
    if linked['answer']=='NotMentioned' and modes['original']['answer']!='NotMentioned' and possible and not (
            evidence['same_clause'] or evidence['linked']):
        linked = modes['original']
    return {**modes, 'coverage_guarded':linked}


def inputs(partition, archived):
    if partition=='train':
        active=read(TRAIN)
        assert ROOT/active['artifact_root']==archived
        checkpoint = ROOT/read(BOOTSTRAP)['artifact_root']
        binding=read(checkpoint/'binding.json')
        all_sources = [s for batch in load_roster(binding) for s in batch]
        _, stage, _=bound_stage(FIRST)
        grade = stage['native_grade_paths'][DATASET]
    else:
        stage,binding,_=bound_stage(dev_pointer(8))
        bootstrap=read(ROOT/binding['checkpoint_root']/'binding.json')
        public_root = ROOT/binding['b0_dev_data_root']
        all_sources=read(public_root/'public_DEV_sources.json')
        assert digest(all_sources)==read(public_root/'binding.json')['DEV_public_sha256']
        assert sha(stage/'terminal.json')==read(archived/'binding.json')['original_DEV_terminal_sha256']
        grade = bootstrap['grading_paths'][DATASET]
    assert partition in Path(grade).parts
    return {row['key']:view_for(row) for row in all_sources
            if row['dataset']==DATASET and row['project_split']==partition}, ROOT/grade


def run(partition, archived):
    parent=read(archived/'binding.json')
    assert archived.name==digest(parent)
    terminal=read(archived/'terminal.json')
    encoded=archived/'predictions.json'
    assert sha(encoded)==terminal['predictions_sha256'] and terminal['new_calls']==0
    previous=read(encoded)
    before=previous['incoming' if partition=='train' else 'predictions']
    views,grade=inputs(partition,archived)
    assert len(views)==(24 if partition=='train' else 16)
    assert views.keys()==previous['scope'].keys()
    evidence = {key:possibly_compelled(view) for key,view in views.items()}
    bank={a:{k:guarded(m,previous['scope'][k],evidence[k]) for k,m in rows.items()} for a,rows in before.items()}
    lock={'scope':partition,'archived_terminal_sha256':sha(archived/'terminal.json'),
          'runner_sha256':sha(Path(__file__)),'native_grade_sha256':parent['native_grade_sha256'],
          'guard_decisions_sha256':digest(evidence)}
    out=HOME/'coverage_guard'/partition/digest(lock)
    immutable_json(out/'binding.json',lock)
    immutable_json(out/'predictions.json',bank)
    assert sha(grade)==lock['native_grade_sha256']
    grades=read(grade)
    result={'partition':partition,'new_calls':0,'rule_reviewed_after_fixed_DEV_feedback':True,
            'returned_to_original':{a:sum(m['coverage_guarded']['answer']!=m['linked']['answer'] for m in rows.values()) for a,rows in bank.items()},
            'by_arm':{a:estimate(views,rows,grades) for a,rows in bank.items()},'predictions_sha256':sha(out/'predictions.json')}
    immutable_json(out/'terminal.json',result)
    print(json.dumps({'artifact_root':str(out.relative_to(ROOT)),**result},sort_keys=True),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('partition',choices=('train','dev'))
    parser.add_argument('archived',type=Path)
    args=parser.parse_args()
    run(args.partition, args.archived.resolve())
