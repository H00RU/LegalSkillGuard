"""Offline exhaustive structural diagnostics for the literal failed response."""
import json
from pathlib import Path
from legal_skill_guard.rr.legal_predicate_skills import var,validate
ROOT=Path(__file__).resolve().parents[2]
STAGE=ROOT/'artifacts/rr_method_redesign_20261109/legal_relations_exceptions_native_v1_20261109'

def diagnose(v,sources):
 p={x['name']:x for x in v['predicates']};issues=[]
 def emit(path,expected,actual):issues.append({'path':path,'expected':expected,'actual':actual})
 for i,r in enumerate(v['rules']):
  prefix=f'rules[{i}]';bound={x for a in r['body'] for x in a['arguments'] if var(x)}
  used={x for x in r['head']['arguments'] if var(x)}|{x for d in r['different'] for x in d.values() if var(x)}
  if used-bound:emit(prefix+'.variables','head/distinct variables bound by body',sorted(used-bound))
  for j,a in enumerate([r['head']]+r['body']):
   path=prefix+('.head' if j==0 else f'.body[{j-1}]')
   if a['predicate'] not in p:emit(path+'.predicate','declared predicate',a['predicate'])
   elif len(a['arguments'])!=len(p[a['predicate']]['roles']):emit(path+'.arguments',len(p[a['predicate']]['roles']),len(a['arguments']))
   elif j and p[a['predicate']]['functional']:emit(path+'.predicate','nonfunctional body relation',a['predicate'])
  for f in ('guard_quote','quote'):
   if not r[f] or not any(r[f] in s for s in sources):emit(prefix+'.'+f,'nonempty exact public source span',r[f])
  # Never infer missing clause truth to repair these circular dependencies.
  for j,a in enumerate(r['body']):
   if any('applies' in a['predicate'].lower() and t==r['id'] for t in a['arguments']):
    emit(prefix+f'.body[{j}]','source condition, not an external assertion that this very rule applies',a)
 graph={r['id']:set() for r in v['rules']}
 for i,a in enumerate(v['priorities']):
  if a['higher'] not in graph or a['lower'] not in graph:emit(f'priorities[{i}]','existing rule endpoints',a)
  else:graph[a['higher']].add(a['lower'])
 for x in graph:
  frontier=list(graph[x]);seen=set()
  while frontier:
   y=frontier.pop()
   if y==x:emit('priorities','acyclic source priority',x);break
   if y not in seen:seen.add(y);frontier.extend(graph[y])
 return issues

def main():
 s=json.loads((STAGE/'seal.json').read_text());rows=[]
 for name in ('executor_program','teacher_program'):
  path=STAGE/(name+'.json')
  if not path.exists():continue
  x=json.loads(path.read_text());issues=diagnose(x['value'],[p['rules'] for p in s['policies']]);w=x['physical_response']
  rows.append({'role':name,'literal_validation':x['validation'],'issues':issues,
   'finish_reason':w.get('finish_reason'),'usage':w.get('usage'),'elapsed_seconds':w.get('elapsed_seconds'),
   'new_model_calls_from_audit':0,'semantic_repairs_applied':False})
 out={'cases':rows,'source_fidelity_is_not_proved_by_no_structural_errors':True,'new_calls':0}
 (ROOT/'reports/method_redesign_20261109/legal_interface_failure_audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps([{ 'role':x['role'],'issues':len(x['issues']),'literal_validation':x['literal_validation']} for x in rows],ensure_ascii=False))
if __name__=='__main__':main()
