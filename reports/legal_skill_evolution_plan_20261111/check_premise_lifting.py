"""Constructed finite semantics only. No models, native benchmark labels, or new dataset."""
from pathlib import Path
import json
OUT=Path(__file__).resolve().parent
# Explicitly defined toy source provisions, not claims about any actual statute.
SOURCES={"A":{"ceiling":100,"scope":"basic"},"B":{"ceiling":60,"scope":"total"}}
CASES=[(40,30),(70,5),(20,20),(30,50)]
def evaluate(basic,additional,ceiling,scope):
 return min(basic,ceiling)+additional if scope=="basic" else min(basic+additional,ceiling)
def toy_source_read(source):
 # Exact fixture reader. It is NOT a measured Qwen extraction capability.
 return dict(SOURCES[source])
def predict(source,case,lifted):
 bound={"ceiling":100,"scope":"basic"}
 read=toy_source_read(source)
 for name in lifted:bound[name]=read[name]
 return evaluate(*case,**bound)
variants={"fixed_original":(),"lift_ceiling_only":("ceiling",),"lift_scope_only":("scope",),"coupled_lift":("ceiling","scope"),"generic_joint_repair":("ceiling","scope"),"all_ports_bound":("ceiling","scope")}
rows=[]
for src in SOURCES:
 for case in CASES:
  gold=evaluate(*case,**SOURCES[src])
  row={"source":src,"case":list(case),"specified_output":gold,"predictions":{k:predict(src,case,v) for k,v in variants.items()}}
  rows.append(row)
summary={k:{src:sum(r["predictions"][k]==r["specified_output"] for r in rows if r["source"]==src) for src in SOURCES} for k in variants}
assert summary["fixed_original"]=={"A":4,"B":1}
assert summary["lift_ceiling_only"]=={"A":4,"B":1}
assert summary["lift_scope_only"]=={"A":4,"B":1}
assert summary["coupled_lift"]=={"A":4,"B":4}
assert summary["generic_joint_repair"]==summary["coupled_lift"]==summary["all_ports_bound"]
result={"purpose":"demonstrate coupled premise dependence; not a benchmark or evidence of novelty/performance", "source":"author-defined finite provisions A/B", "reader":"exact fixture, not an LLM", "cases_per_source":4,"summary":summary,"rows":rows,"honest_comparison":"Generic joint repair and binding all relevant ports also solve this example. The example disproves sufficiency of one-at-a-time lifting, not sufficiency of generic synthesis.","external_calls":0}
(OUT/"PREMISE_LIFTING_FINITE_CHECK.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(summary,indent=2))
