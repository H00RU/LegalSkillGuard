"""Same accepted model IR, strong ordinary connectors and library interventions.

No generation, grading packet or oracle access. Original artifacts are read only.
"""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from statistics import median
from time import perf_counter
from types import SimpleNamespace

from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.horn import closure as unify
from legal_skill_guard.rr.horn_connectors import execute_parsed_with_library, execute_parsed_with_standard_connectors
from legal_skill_guard.rr.learning import SkillLibrary
from legal_skill_guard.rr.model_horn import parse_model_horn

ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/'artifacts/rr_method_runtime_20261107/method_runtime_reference_v10_20261109'
REPORT=ROOT/'reports/method_efficacy_20261109'


def main():
    seal=json.loads((STAGE/'seal.json').read_text())
    public={s['key']:s for split in ('train','dev')
        for s in json.loads((ROOT/f'data/packets/rr_v2/public_{split}.json').read_text())['sources']}
    b1=SkillLibrary.restore(STAGE/'build/B1.frozen.json').export()
    b8=SkillLibrary.restore(STAGE/'build/B8.frozen.json').export()
    prefix=SkillLibrary(stage='formal_train');cases=[]
    for ordinal,source in enumerate(seal['sources']['train'],1):
        p=STAGE/'build/sources'/(digest(source)+'.json');record=json.loads(p.read_text())
        assert digest(prefix.export())==record['library_before_hash']
        pred=record['prediction']
        if pred['result']['program_status']=='model_Horn_IR_compiled' and not pred['result']['fallback_used']:
            cases.append(('TRAIN',ordinal,source,p,pred,prefix.export()))
        if record['learning'].get('learned_pattern'):
            prefix.add(record['learning']['learned_pattern'],source=source)
        for template in record.get('compiler_learning',{}).get('templates',[]):prefix.add_compiler_template(template)
    for ordinal,source in enumerate(seal['sources']['dev'],1):
        p=STAGE/'dev/predictions/M11'/(digest(source)+'.json');pred=json.loads(p.read_text())['prediction']
        if pred['result']['program_status']=='model_Horn_IR_compiled' and not pred['result']['fallback_used']:
            cases.append(('DEV',ordinal,source,p,pred,b8))
    assert Counter(c[0] for c in cases)=={'TRAIN':21,'DEV':7}
    rows=[];all_rule_instances=0
    for partition,ordinal,source,path,pred,library in cases:
        program=parse_model_horn(public[source],pred['model_horn_code'])
        assert not program.export()['missing_units']
        parsed=SimpleNamespace(facts=set(program.facts.values()),rules=program.rules,query=program.query)
        baseline_audit={};base=execute_parsed_with_standard_connectors(parsed,audit=baseline_audit)
        ordinary=unify(parsed.facts,parsed.rules,parsed.query)
        assert base['answer']==ordinary['answer']==pred['result']['answer']
        ordinary_facts=set(parsed.facts)|{r['atom'] for r in ordinary['trace']}
        assert ordinary_facts==set(baseline_audit['closure_facts'])
        variants={'actual_prefix':library}
        if partition=='DEV':
            variants.update(B1=b1,B8=b8,
                B8_first_only={**b8,'patterns':b8['patterns'][:1]},
                B8_second_only={**b8,'patterns':b8['patterns'][1:]})
        results={}
        for name,lib in variants.items():
            audit={};result=execute_parsed_with_library(parsed,lib,audit=audit)
            assert result['answer']==base['answer'] and result['status']==base['status']
            assert audit['closure_facts']==baseline_audit['closure_facts']
            assert audit['rule_instances']==baseline_audit['rule_instances']
            results[name]={'answer':result['answer'],'full_closure_and_rule_instances_equal_standard':True,
                'selected_patterns':dict(Counter(u['pattern_hash'] for u in result['pattern_uses'])),
                'stored_graph_calls':len(result['pattern_uses'])}
        all_rule_instances+=len(baseline_audit['rule_instances'])
        # Same implementation and inputs; time full execution, no trace capture.
        timings={'standard_connectors':[],'actual_library':[],'ordinary_unification':[]}
        functions={'standard_connectors':lambda:execute_parsed_with_standard_connectors(parsed),
            'actual_library':lambda:execute_parsed_with_library(parsed,library),
            'ordinary_unification':lambda:unify(parsed.facts,parsed.rules,parsed.query)}
        cold={}
        for name,fn in functions.items():
            start=perf_counter();fn();cold[name]=perf_counter()-start
        names=list(functions)
        for repeat in range(3):
            for name in names[repeat:]+names[:repeat]:
                start=perf_counter();result=functions[name]();timings[name].append(perf_counter()-start)
                assert result['answer']==base['answer']
        rows.append({'partition':partition,'source_ordinal':ordinal,'source':source,
            'original_record_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'actual_prefix_support_precedes_target':partition!='TRAIN' or all(
                set(p['evidence_sources'])<=set(seal['sources']['train'][:ordinal-1]) for p in library['patterns']),
            'model_program_units':len(program.represented),'rule_instances_compared':len(baseline_audit['rule_instances']),
            'all_backends_answer':base['answer'],'library_interventions':results,
            'cold_seconds':cold,'warm_samples_seconds':timings,
            'warm_median_seconds':{k:median(v) for k,v in timings.items()}})
    templates_equal=[p['template_hash'] for p in b1['compiler_templates']]==[p['template_hash'] for p in b8['compiler_templates']]
    value={'captured_utc':datetime.now(timezone.utc).isoformat(),'original_run':STAGE.name,
        'accepted_model_programs':len(rows),'partition_counts':dict(Counter(r['partition'] for r in rows)),
        'full_closure_and_every_rule_instance_equal':True,'rule_instances_compared':all_rule_instances,
        'original_predictions_and_libraries_unchanged':True,'original_labels_opened':False,
        'model_or_oracle_calls':0,'timing_repetitions_not_new_sources_seeds_or_model_trials':True,
        'B1_B8_compiler_templates_identical':templates_equal,
        'aggregate_warm_median_seconds':{k:sum(r['warm_median_seconds'][k] for r in rows)
            for k in ('standard_connectors','actual_library','ordinary_unification')},
        'rows':rows,
        'scope':'All accepted model-generated logic programs in the fixed TRAIN and DEV; not a claim about unavailable nonlogic IR',
        'structural_reason':'Selected learned join substitutes actual keys already determined by intersection of explicit model variable columns; canonical branch calls the identical natural-join primitive with these keys.'}
    REPORT.mkdir(exist_ok=True)
    (REPORT/'B_same_program_interventions.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in value.items() if k!='rows'},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
