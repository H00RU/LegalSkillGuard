"""Measure MAUD readers using same-definition source anchors and matched controls."""

import argparse
from collections import defaultdict
import json
from pathlib import Path
import re
import sqlite3

from experiments.convergence_formal_b1_observe import load_roster
from experiments.convergence_formal_bootstrap import POINTER as BOOTSTRAP
from experiments.convergence_formal_train_observe import pointer as observe
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import indexed_relational_read as indexed
from legal_skill_guard.paired_interfaces import maud_knowledge_relational as knowledge
from legal_skill_guard.paired_interfaces.formal_actors import InterfaceActor
from legal_skill_guard.paired_interfaces.production_decode import decode_response
from legal_skill_guard.paired_interfaces.relational_program import template_version
from legal_skill_guard.paired_interfaces.residual import encode
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE/'revision5_MAUD_definition_scope_20261119'
POINTER = HANDOFF/'revision5_MAUD_definition_scope_current.json'
DONE = 'completed_revision5_MAUD_definition_scope_TRAIN'
REGISTRY_POINTER = ROOT/'artifacts/two_method_followthrough_20261116/handoff/current_checkpoint.json'
QUOTED_TERM = re.compile(r'[“"]knowledge(?: of [^”"\r\n]{1,65})?[”"]',re.I)
DEFINITION_VERB = re.compile(r'\bmeans?\b',re.I)
SENTENCE_END = re.compile(r'[.!?](?=\s|$)')
TRAILING_PAGE = re.compile(r'\s*\(Page\s+\d+\)\s*$',re.I)
POSITIVE = {'reasonable_inquiry_required','due_inquiry_required'}
ACTUAL = 'Actual knowledge'
CONSTRUCTIVE = 'Constructive knowledge'


def definition_sites(text):
    """Keep role lists and shared qualifiers together inside a public definition sentence."""
    page = TRAILING_PAGE.search(text)
    end_of_source = page.start() if page else len(text)
    candidates = {}
    covered_end = 0
    for term in QUOTED_TERM.finditer(text,0,end_of_source):
        if term.start() < covered_end:
            continue
        stop = SENTENCE_END.search(text,term.end(),end_of_source)
        end = stop.end() if stop else end_of_source
        if not DEFINITION_VERB.search(text,term.end(),end):
            continue
        candidates['d'+str(len(candidates)+1)] = [term.start(),end]
        covered_end = end
    return candidates


def plan_pair(source):
    selected, view = knowledge.build(source)
    text = view['relational_public_source']['source_text']
    sites = definition_sites(text)
    if not sites:
        raise ValueError('The comparison is scoped to a recoverable quoted operative definition')
    view['relational_public_source']['indexed_ranges'] = sites
    view = indexed.reformat(view,factorized=True)
    for plan in view['plans']:
        system = (plan['system'] + '\nThe indexed evidence contains the complete observed sentence or fragment '
                  'starting at the quoted defining term. Match the inquiry condition to that definition and to '
                  'the party or group it qualifies. Semicolons can separate members of one list. Keep the full '
                  'source for context. Preserve unknown when the exact attachment or effect remains unresolved.')
        plan['system'] = system
        plan['reader_template_sha256'] = template_version(
            plan['relational_program'],system=system,public_rules='same-definition anchor',
            protocol='maud_same_definition_scope_v1')
        plan['version'] = digest({k:v for k,v in plan.items() if k!='version'})
    return selected,view


def source_review(card,text):
    graph = card['graph']
    nodes = {n['id']:n for n in graph['nodes']}
    inquiry = [nodes[r['arguments'][1]]['quote'] for r in graph['relations']
               if r['predicate']=='condition'
               and nodes[r['arguments'][0]]['concept']=='knowledge_definition'
               and nodes[r['arguments'][1]]['concept'] in POSITIVE]
    actual = [nodes[r['arguments'][1]]['quote'] for r in graph['relations']
              if r['predicate']=='standard'
              and nodes[r['arguments'][0]]['concept']=='knowledge_definition'
              and nodes[r['arguments'][1]]['concept']=='explicit_actual_wording']
    definitions = [r['quote'] for r in nodes.values() if r['concept']=='knowledge_definition']
    exceptions = [r['quote'] for r in nodes.values() if r['concept']=='no_inquiry_required']
    if not definitions or any(q not in text for q in (*inquiry,*actual,*definitions,*exceptions)):
        return None
    if inquiry:
        kind = 'limited_exception' if exceptions else 'operative_inquiry'
        return kind,CONSTRUCTIVE,set([*definitions,*inquiry])
    if graph['scope_complete'] and actual and not exceptions:
        return 'closed_actual',ACTUAL,set([*definitions,*actual])
    return None


def materials():
    pilot = ROOT/read(HANDOFF/'maud_knowledge_probe_current.json')['artifact_root']
    old = read(pilot/'binding.json')
    pilot_cases = read(pilot/'cases.json')
    if (digest(pilot_cases)!=old['cases_sha256'] or read(pilot/'terminal.json')['status']!='completed'
            or len(pilot_cases)!=4):
        raise ValueError('Preserve the four original MAUD TRAIN mothers')
    locked = {c['public_source']['key']:c['public_source'] for c in pilot_cases}
    registry = read(REGISTRY_POINTER)['formal_source_reference_registry']
    registry_path = ROOT/registry['path']
    if sha(registry_path)!=registry['sha256']:
        raise ValueError('Use the intact independent source review registry')
    entries = {e['source']:e for e in read(registry_path)['reviews'] if e['view']=='v0'}
    study = read(ROOT/read(BOOTSTRAP)['artifact_root']/'binding.json')
    roster = load_roster(study)
    cases, counts = [], defaultdict(int)
    for batch in roster:
        for source in batch:
            key = source['key']
            if source['dataset']!='MAUD' or key not in entries:
                continue
            path = ROOT/entries[key]['path']
            if sha(path)!=entries[key]['sha256']:
                raise ValueError('A stored source-only card changed')
            card = read(path)
            if (not card['source_semantic_truth_verified'] or card['native_answers_used_to_create_or_repair_graph']
                    or source['project_split']!='train'):
                raise ValueError('Use reviewed original TRAIN only')
            task, = (v for v in source['views'] if v['id']==knowledge.TASK)
            text = task['public']['source_text']
            reviewed = source_review(card,text)
            if reviewed is None:
                continue
            family,reference,quotes = reviewed
            if key not in locked and not (card['graph']['scope_complete']
                                           and family in ('closed_actual','limited_exception')):
                continue
            if key in locked and locked[key]['views']!=[task]:
                raise ValueError('An original pilot source changed')
            selected, view = plan_pair(source)
            sites = view['relational_public_source']['indexed_ranges']
            anchors = [k for k,(a,b) in sites.items() if all(q in text[a:b] for q in quotes)]
            if len(anchors)!=1:
                raise ValueError('Require one exact site preserving the independently reviewed definition relationships')
            anchor, = anchors
            before = any(all(q in text[a:b] for q in quotes) for a,b in indexed.source_spans(text).values())
            counts['original_pilot' if key in locked else family] += 1
            for plan in view['plans']:
                _, unit = indexed.indexed_unit(plan['relational_program'])
                fact = {'qualification_target':'target_definition',
                        'inquiry_effect':'required' if reference==CONSTRUCTIVE else 'absent',
                        'explicit_actual_restriction':True if reference==ACTUAL else None}
                values = encode(unit['asset']['features'],fact)
                code = '|'.join([anchor,*(indexed.symbol(v) for v in values.values())])
                r = decode_response(selected,view,plan,{'content':json.dumps(code),'finish_reason':'stop'})
                if r['production_errors'] or r['native'][knowledge.TASK]['answer']!=reference:
                    raise ValueError('The original consumer must accept the independently scoped witness')
            cases.append({'source':selected,'view':view,'reference':reference,'family':family,
                          'original_pilot':key in locked,'legacy_fragment_supported_definition':before,
                          'source_only_review_sha256':entries[key]['sha256']})
    if dict(counts)!={'original_pilot':4,'limited_exception':1,'closed_actual':4}:
        raise ValueError('The fixed cohort must contain the original pilot and the certified TRAIN contrasts')
    old_scalar = [ROOT/read(HANDOFF/f)['artifact_root'] for f in (
        'maud_indexed_knowledge_probe_current.json','maud_factorized_knowledge_recovery_current.json')]
    prior_reads = [read(path) for root in old_scalar for path in (root/'comparison_rows').glob('*.json')]
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        for row in prior_reads:
            status, body = db.execute('select status,result from calls where id=?',(row['physical_call_id'],)).fetchone()
            if status!='completed' or json.loads(body)['content']!='"unread"' or row['production_errors']:
                raise ValueError('The comparison targets measured reader abstention')
    if len(prior_reads)!=8:
        raise ValueError('Use all eight original settled responses')
    grade = read(ROOT/read(observe(8))['artifact_root']/'binding.json')
    grade_path = grade['native_grade_paths']['MAUD']
    if sha(ROOT/grade_path)!=grade['native_grade_sha256'][grade_path]:
        raise ValueError('Use the original TRAIN scorer')
    source_paths = {*old['source_sha256'],'legal_skill_guard/paired_interfaces/indexed_relational_read.py',
                    str(Path(__file__).resolve().relative_to(ROOT))}
    binding = {'study':'revision5_MAUD_same_definition_scope', 'executor':study['executor'],
               'cases_sha256':digest(cases), 'source_review_registry_sha256':registry['sha256'],
               'original_pilot_binding':pilot.name, 'old_eight_reads_executed_unread':len(prior_reads),
               'case_counts':dict(counts), 'TRAIN_grade_path':grade_path,'TRAIN_grade_sha256':sha(ROOT/grade_path),
               'fixed_and_synthesized_share_same_input':True,'planned_executor_calls':2*len(cases),
               'source_sha256':{name:sha(ROOT/name) for name in sorted(source_paths)},
               'TEST_and_DEV_opened':False}
    return binding,cases


def run(execute):
    if POINTER.exists() and read(POINTER)['status']==DONE:
        print(read(POINTER)['artifact_root'],flush=True)
        return
    spec,cases = materials()
    stage = HOME/digest(spec)
    if execute and (not POINTER.exists() or ROOT/read(POINTER)['artifact_root']!=stage):
        raise ValueError('Execute only the prepared comparison')
    immutable_json(stage/'binding.json',spec)
    immutable_json(stage/'cases.json',cases)
    if not execute:
        if POINTER.exists() and read(POINTER)['status']=='running':
            raise ValueError('Preserve the active comparison')
        write_status(stage,{'status':'prepared','planned_executor_calls':spec['planned_executor_calls']},POINTER)
        print(json.dumps({'path':str(stage.relative_to(ROOT)), 'families':spec['case_counts'],
                          'legacy_split_count':sum(not c['legacy_fragment_supported_definition'] for c in cases)}),
              flush=True)
        return
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        if db.execute("select 1 from calls where status='reserved'").fetchone():
            raise ValueError('Reconcile existing requests before dispatch')
    for name,expected in spec['source_sha256'].items():
        target = stage/'source_snapshot'/name
        target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists():
            with target.open('xb') as f:
                f.write((ROOT/name).read_bytes())
        if sha(target)!=expected:
            raise ValueError('Preserve the exact comparison inputs and code')
    run_id = 'convergence-revision5-MAUD-definition-'+stage.name[:16]
    ledger = EvolutionLedger(LEDGER,run_id=run_id,sources={'train':[c['source']['key'] for c in cases],
                             'dev':[],'test':[]},binding=spec)
    executor = FrozenExecutor(ledger,stage,spec['executor'])
    executor.readiness()
    actor = InterfaceActor(executor,stage,plan_assets={},source_inputs=None,pipeline_binding=spec['source_sha256'])
    results = defaultdict(list)
    write_status(stage,{'status':'running','finished_pairs':0},POINTER)
    for index,case in enumerate(cases,1):
        for role,plan in zip(('fixed','synthesized'),case['view']['plans'],strict=True):
            results[role].append(actor.measure(case['source'],case['view'],plan,'skill_actor'))
        write_status(stage,{'status':'running','finished_pairs':index},POINTER)
    immutable_json(stage/'native_reads.json',dict(results))
    grades = read(ROOT/spec['TRAIN_grade_path'])
    metrics = {}
    for role,rows in results.items():
        groups = defaultdict(lambda:{'mothers':0,'native_correct':0,'source_supported_correct':0,'unresolved':0})
        for c,r in zip(cases,rows,strict=True):
            task, = c['source']['views']
            answer = r['native'][task['id']]['answer']
            stat = groups['original_pilot' if c['original_pilot'] else c['family']]
            stat['mothers'] += 1
            stat['native_correct'] += int(grade_view('MAUD',task,grades[c['source']['key']][task['id']],answer)['grade'])
            stat['source_supported_correct'] += answer==c['reference']
            stat['unresolved'] += answer is None
        metrics[role] = dict(groups)
    with ledger.transaction() as db:
        calls = db.execute('select status,result from calls where id like ?',(run_id+':%',)).fetchall()
    if len(calls)!=spec['planned_executor_calls'] or any(s!='completed' for s,_ in calls):
        raise ValueError('Seal the full fixed cohort of actual paired requests')
    terminal = {'status':DONE,'metrics':metrics,'executor_calls':len(calls),
                'executor_tokens':sum(json.loads(r)['usage']['total_tokens'] for _,r in calls),
                'teacher_calls':0,'TRAIN_only':True}
    immutable_json(stage/'terminal.json',terminal)
    write_status(stage,{'status':DONE,'executor_calls':len(calls)},POINTER)
    print(json.dumps(terminal,sort_keys=True),flush=True)


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=('prepare','run'))
    run(parser.parse_args().phase=='run')
