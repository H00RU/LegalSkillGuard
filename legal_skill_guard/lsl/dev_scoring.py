"""Evaluator-only native DEV metrics and explicit method-path accounting."""
import ast
from collections import Counter

from .evaluation import score_source,f1
from .composition_data import gold_graph
from .horn_codec import normalize as normalize_horn,rules_key,theory_key
from .projection import compact


def score(record,execution,*,graph=None,output=None,error=None):
    d=record['dataset'];valid=bool(execution and execution.get('valid'))
    if d=='NormBench':return score_source(graph if valid else None,gold_graph(record['native_record']),error)
    result={'source':record['key'],'dataset':d,'valid':valid,'error':error}
    if d=='ContractNLI':
        pred=execution.get('answer',{}) if valid else {};ev=execution.get('evidence',{}) if valid else {}
        correct={k:pred.get(k)==y for k,y in record['grade']['answers'].items()}
        result.update(native_accuracy=sum(correct.values())/17,native_query_correct=correct,native_queries=17)
        evidence=[];tp=pp=gg=0;by_query={}
        for k,expected in record['grade']['evidence'].items():
            p=set(ev.get(k,[]));g=set(expected);overlap=len(p&g)
            value=f1(overlap,len(p),len(g))if g else None
            if value is not None:evidence.append(value)
            by_query[k]={'tp':overlap,'pred':len(p),'gold':len(g),'f1':value}
            tp+=overlap;pp+=len(p);gg+=len(g)
        result.update(evidence_query_macro_F1=sum(evidence)/len(evidence)if evidence else None,
            evidence_tp=tp,evidence_pred=pp,evidence_gold=gg,evidence_annotated_queries=len(evidence),
            evidence_by_query=by_query,
            NotMentioned_evidence_masked=True)
        return result
    answer=execution.get('answer')if valid else None;expected=record['grade']['answer']
    result.update(native_answer=answer,native_expected=expected,native_correct=valid and answer==expected)
    if d=='ProofWriter_OWA_depth5':
        reference=normalize_horn(record['grade']['horn'])
        try:
            program=normalize_horn(output['program'])
            a=Counter(compact(x)for x in program['facts']);b=Counter(compact(x)for x in reference['facts'])
            r=Counter(rules_key(program['rules']));s=Counter(rules_key(reference['rules']))
            result.update(native_fact_F1=f1(sum((a&b).values()),sum(a.values()),sum(b.values())),
                native_rule_F1=f1(sum((r&s).values()),sum(r.values()),sum(s.values())),
                native_query_exact=program['query']==reference['query'],
                native_program_exact_up_to_codec_and_alpha=theory_key(program)==theory_key(reference))
        except Exception:
            result.update(native_fact_F1=0.,native_rule_F1=0.,native_query_exact=False,native_program_exact_up_to_codec_and_alpha=False)
    elif d in ('SARA_v2_Binary','RuleArena_Airline') and output and 'program'in output:
        try:
            tree=ast.parse(output['program']);solve=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='solve')
            body=[n for n in solve.body if not(isinstance(n,ast.Expr)and isinstance(n.value,ast.Constant)and isinstance(n.value.value,str))]
            result['literal_only_return']=len(body)==1 and isinstance(body[0],ast.Return) and isinstance(body[0].value,ast.Constant)
            result['has_comparison_or_arithmetic']=any(isinstance(n,(ast.Compare,ast.BinOp))for n in ast.walk(tree))
            result['full_source_rule_equivalence_oracle_available']=False
        except Exception:result['program_audit_error']=True
    return result


def summarize(rows):
    if not rows:raise ValueError('Native evaluation needs the complete source denominator')
    d=rows[0]['dataset'];total=len(rows)
    result={'dataset':d,'sources':total,'main_valid':sum(r['main_path_valid']for r in rows),
        'fallback_sources':sum(r['fallback_used']for r in rows),'fallback_ratio':sum(r['fallback_used']for r in rows)/total,
        'M2_executed_sources':sum(r.get('composition',{}).get('directed_head_used',False)for r in rows)}
    if d=='NormBench':
        result.update(node_span_F1=sum(r['score']['node_span']['f1']for r in rows)/total,
            typed_content_F1=sum(r['score']['typed_content']['f1']for r in rows)/total,
            parent_scope_F1=sum(r['score']['parent_edges']['f1']for r in rows)/total,
            whole_graph_exact=sum(r['score']['canonical_whole_graph_exact']for r in rows)/total)
    elif d=='ContractNLI':
        result['native_contract_macro_accuracy']=sum(r['score']['native_accuracy']for r in rows)/total
        ev=[r['score']['evidence_query_macro_F1']for r in rows if r['score']['evidence_query_macro_F1']is not None]
        result['evidence_query_macro_F1']=sum(ev)/len(ev)if ev else None
        tp=sum(r['score']['evidence_tp']for r in rows);p=sum(r['score']['evidence_pred']for r in rows);g=sum(r['score']['evidence_gold']for r in rows)
        result['evidence_micro_F1']=f1(tp,p,g);result['evidence_annotated_sources']=len(ev)
        labels={k for r in rows for k in r['score']['evidence_by_query']};label_scores=[]
        for label in labels:
            values=[r['score']['evidence_by_query'][label]for r in rows if label in r['score']['evidence_by_query']]
            t=sum(v['tp']for v in values);p=sum(v['pred']for v in values);g=sum(v['gold']for v in values)
            if g:label_scores.append(f1(t,p,g))
        result['official_macro_label_micro_doc_evidence_F1']=sum(label_scores)/len(label_scores)if label_scores else None
        result['official_metric_reference']='stanfordnlp/contract-nli-bert@058c56fd:contract_nli/evaluation.py'
    else:
        result['native_accuracy']=sum(r['score']['native_correct']for r in rows)/total
        result['main_path_native_correct']=sum(r['main_path_valid']and not r['fallback_used']and r['score']['native_correct']for r in rows)
        if d=='ProofWriter_OWA_depth5':
            result.update(native_fact_F1=sum(r['score']['native_fact_F1']for r in rows)/total,
                native_rule_F1=sum(r['score']['native_rule_F1']for r in rows)/total,
                native_program_exact=sum(r['score']['native_program_exact_up_to_codec_and_alpha']for r in rows)/total)
    return result
