"""Actual terminal TRAIN record: source whitespace repair, no model or labels."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import source_spans
from legal_skill_guard.skill_evolution.scoped_grammar import material_public
from legal_skill_guard.skill_evolution.scoped_source_program import run_source
from legal_skill_guard.skill_evolution.span_compiler import execute_json, execution_source_spans


def main(root):
    run = root / 'artifacts/legal_skill_evolution_scoped_acquisition_v5_20261113'
    assert (run / 'NoFactor/completed.json').exists()
    read = lambda p: json.loads(p.read_text())
    db = sqlite3.connect(root / 'artifacts/rr_v2_preflight/research_ledger.sqlite3')
    before = list(db.execute('select * from calls order by id'))
    assert not any(x[6] == 'reserved' for x in before)
    public = read(root / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')
    source = next(x for x in public if x['key'] ==
        'ContractNLI:62fda7e904de3c7f48fe38d41908127e324a6a8da77d21d4465816e57cf90f54')
    spans = source_spans(material_public(source['views'][0]['public']))
    raw_spans = deepcopy(spans)
    folded = execution_source_spans(spans)
    assert spans == raw_spans
    assert [{k:v for k,v in s.items() if k != 'text'} for s in spans] == [
        {k:v for k,v in s.items() if k != 'text'} for s in folded]
    method = read(run / 'phase2/ScopedGrammar/adapted_proposal.json')
    grammar = read(run / 'phase2/ScopedGrammar/induced_grammar.json')
    raw = execute_json(method['source_program'],
        {'source_text': source['views'][0]['public']['source_text'], 'source_spans': spans}, {},
        allow_helpers=True)
    saved = read(run / 'phase2/ScopedGrammar/results' / (source['key'].replace(':','_')+'.json'))
    assert raw == saved['interpretation']['source_program_output']
    adapted, _ = run_source(method['source_program'], method['grammar'], grammar, source)
    added = [s for s in adapted['source_program_output']['statements'] if s not in raw['statements']]
    assert any(s['term'][0] == 'prohibition' and s['support_ids'] == [31,32] for s in added)
    free = read(run / 'phase2/IndependentFree/teacher.json')['value']['program']
    free_checks = []
    for task in ('nda-5','nda-7'):
        view = next(v for v in source['views'] if v['id'] == task)
        inputs = {'task_id':task, 'question':view['public']['question']}
        def evaluate(ss):
            return execute_json(free, inputs, {'source_text':source['views'][0]['public']['source_text'],
                                               'source_spans':ss}, allow_helpers=True)
        a,b = evaluate(spans),evaluate(folded)
        assert a == b
        free_checks.append({'task':task,'before':a,'after':b,'unchanged':True})
    after = list(db.execute('select * from calls order by id'));assert before == after
    receipt = {'source':source['key'],'native_labels_loaded':False,'new_physical_requests':0,
        'raw_replay_identical_to_frozen_result':True,'raw_spans_and_provenance_unchanged':True,
        'raw_statement_count':len(raw['statements']),
        'adapted_statement_count':len(adapted['source_program_output']['statements']),
        'added_statements':added,'raw_support_text':[spans[i] for i in (31,32)],
        'execution_support_text':[folded[i] for i in (31,32)],
        'free_same_adapter_checks':free_checks,
        'source_semantics_observation':'Spans31-32 actually state the joint recipient/representative prohibition. This receipt repairs whitespace only; it does not certify the entire IR or the unused definition.',
        'old_scientific_results_unchanged':True,'new_innovation_claimed':False,
        'ledger_rows_unchanged':len(before),
        'ledger_sha256':hashlib.sha256(json.dumps(before,ensure_ascii=False,separators=(',',':')).encode()).hexdigest(),
        'source_snapshot':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in [
            'legal_skill_guard/skill_evolution/span_compiler.py',
            'legal_skill_guard/skill_evolution/scoped_source_program.py',
            'experiments/legal_skill_evolution_scoped_acquisition.py',
            str(Path(__file__).resolve().relative_to(root))]}}
    out=root/'reports/legal_skill_evolution_run_20261111/source_compiler_followup/whitespace_regression.json'
    immutable_json(out,receipt)
    print(json.dumps({k:v for k,v in receipt.items() if k not in (
        'source_snapshot','raw_support_text','execution_support_text','free_same_adapter_checks')},ensure_ascii=False))


if __name__=='__main__':
    main(Path(__file__).resolve().parents[1])
