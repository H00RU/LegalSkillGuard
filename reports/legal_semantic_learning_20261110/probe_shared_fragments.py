"""Native TRAIN only; exact text sharing and role deltas, not learned results."""
import json, hashlib, collections, argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--data', required=True)
parser.add_argument('--output', default=str(ROOT/'shared_fragment_feasibility.json'))
args=parser.parse_args()
raw=Path(args.data).read_bytes()
data=json.loads(raw)
manifest=json.loads((ROOT/"data_manifest/normbench_candidate_split_v1.json").read_bytes())
assert hashlib.sha256(raw).hexdigest()==manifest["source_sha256"]
ids={r["item_id"] for r in manifest["items"] if r["split"]=="train"}
def leaves(n):
 if "op" in n:
  for c in n["items"]: yield from leaves(c)
 else: yield n
counts=collections.Counter(); examples=[]
for x in data["items"]:
 if x["item_id"] not in ids: continue
 counts["train_sources"]+=1
 by=collections.defaultdict(list); state={}; deltas=[]
 for ui,u in enumerate(x["gold"]["units"]):
  unit_roles=collections.defaultdict(set)
  for bi,b in enumerate(u["branches"]):
   counts["branches"]+=1
   counts["nonempty_depends_on_units"]+=bool(b.get("depends_on_units"))
   for leaf in leaves(b["conditions"]):
    text=leaf["text"];tag=leaf["tag"]
    by[text].append((ui,bi,tag));unit_roles[text].add(tag)
  # The neutral key does not encode branch or tree path. Source identity remains per item.
  for text,roles in sorted(unit_roles.items()):
   old=state.get(text,set()); new=roles-old
   if text in state and new:
    deltas.append({"unit_index":ui,"content":text,"old_roles":sorted(old),"added_roles":sorted(new),"literal_in_target":text in x["input"]["rule_text"]})
   state[text]=old|roles
 repeated={k:v for k,v in by.items() if len({(a,b) for a,b,t in v})>1 and any(t!="主体" for a,b,t in v)}
 multitag={k:v for k,v in repeated.items() if len({t for a,b,t in v})>1}
 counts["sources_with_shared_non_subject_content"]+=bool(repeated)
 counts["shared_non_subject_content_classes"]+=len(repeated)
 counts["sources_with_multiple_roles_for_shared_content"]+=bool(multitag)
 counts["multiple_role_content_classes"]+=len(multitag)
 counts["sources_with_cross_unit_role_revision"]+=bool(deltas)
 counts["cross_unit_role_revisions"]+=len(deltas)
 counts["literal_cross_unit_role_revisions"]+=sum(z["literal_in_target"] for z in deltas)
 counts["leaf_occurrences"]+=sum(len(v) for v in by.values())
 counts["unique_content_classes"]+=len(by)
 counts["unique_typed_content_classes"]+=sum(len({t for a,b,t in v}) for v in by.values())
 if deltas: examples.append({"item_id":x["item_id"],"deltas":deltas})
result={"purpose":"TRAIN-only availability and exact deterministic projection, not novelty or learned improvement", "source_sha256":hashlib.sha256(raw).hexdigest(),"counts":dict(counts),"identity_rule":"Exact leaf text within one item, not legal entity/coreference equivalence; no branch/parent ID in key", "exposure":"whole native units in released order; no claim of word-level semantic availability", "cross_unit_examples":examples}
Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding="utf-8")
print(json.dumps(result["counts"],ensure_ascii=False,indent=2))
