from copy import deepcopy

def project(language,renderers):
 original=deepcopy((language,renderers));changes=[]
 for renderer in renderers:
  name=renderer['predicate'];signature=language['signatures'][name];used=set()
  def refs(v):
   if isinstance(v,dict):used.add(v.get('term_argument',v.get('scalar_argument')))
   else:
    for child in v[1:]:refs(child)
  refs(renderer['term'])
  for key in ('support_arguments','support_from_terms','support_from_queries'):used.update(renderer.get(key,[]))
  kept=sorted(used);removed=sorted(set(range(len(signature['arguments'])))-used)
  if not removed:continue
  assert not any(a['predicate']==name for r in language['rules'] for a in r['body'])
  remap={old:new for new,old in enumerate(kept)}
  def move(v):
   if isinstance(v,dict):return {k:remap[i] for k,i in v.items()}
   return [v[0],*[move(x) for x in v[1:]]]
  old_renderer=deepcopy(renderer);renderer['term']=move(renderer['term'])
  for key in ('support_arguments','support_from_terms','support_from_queries'):
   if key in renderer:renderer[key]=[remap[i] for i in renderer[key]]
  signature['arguments']=[signature['arguments'][i] for i in kept]
  for rule in language['rules']:
   if rule['head']['predicate']==name:rule['head']['arguments']=[rule['head']['arguments'][i] for i in kept]
  # Pointwise output substitution and provenance commute with projection;
  # the symbolic values distinguish every original argument.
  before=['ARG_'+str(i) for i in range(len(kept)+len(removed))];after=[before[i] for i in kept]
  def instantiate(v,args):
   if isinstance(v,dict):return [next(iter(v)),args[next(iter(v.values()))]]
   return [v[0],*[instantiate(x,args) for x in v[1:]]]
  assert instantiate(old_renderer['term'],before)==instantiate(renderer['term'],after)
  for key in ('support_arguments','support_from_terms','support_from_queries'):
   assert [before[i] for i in old_renderer.get(key,[])]==[after[i] for i in renderer.get(key,[])]
  changes.append({'predicate':name,'removed_unused_output_positions':removed,'pointwise_legal_term_and_provenance_exact':True,'output_predicate_never_used_as_body':True})
 for before,after in zip(original[0]['rules'],language['rules']):
  assert before['body']==after['body'] and before['id']==after['id'] and before['cost']==after['cost']
 return changes
