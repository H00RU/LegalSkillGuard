"""Shared native-question compiler and literal evidence gate for the finite pilot.

These are public components for every arm, not learned legal rules. Rejected
model queries/facts remain rejected. New queries are compiled from public text
and source-learned role signatures, never repaired using an answer label.
"""
from copy import deepcopy
import re

PERSON_ROLES={'person','claimant','subject','other_taxpayer'}

def citation(text):
 m=re.search(r'(?:[Ss]ection\s+|§\s*)(\d+(?:\([A-Za-z0-9]+\))*)',text)
 if not m:raise ValueError('Question/authority outside the finite native citation grammar')
 return m.group(1)

def compile_question(text,program):
 authority=citation(text);rules=[r for r in program['rules'] if citation(r['authority'])==authority and r['head']['positive']]
 preds={p['name']:p for p in program['predicates']};year=re.findall(r'(?:for (?:the )?(?:year )?|in )(20\d\d|19\d\d)\b',text)
 if not year or len(set(year))!=1:raise ValueError('No unique original query year')
 binding={'year':year[0]}
 amount=re.search(r'(?:equal to|is)\s+(\$[0-9,]+)',text)
 claim=re.search(r'([A-Z][a-z]+) can claim an exemption with ([A-Z][a-z]+) the dependent',text)
 applies=re.search(r'applies to ([A-Z][a-z]+)',text)
 owner=re.search(r"([A-Z][a-z]+)'s",text)
 if amount:
  choices=[r for r in rules if preds[r['head']['predicate']]['functional']]
  if owner is None:raise ValueError('Amount question has no explicit subject')
  binding.update(subject=owner[1],amount=amount[1])
 elif claim:
  choices=[r for r in rules if r['head']['predicate'].endswith('_applies')]
  binding.update(claimant=claim[1],subject=claim[2])
 elif applies:
  choices=[r for r in rules if r['head']['predicate'].endswith('_applies')]
  binding['subject']=applies[1]
 else:raise ValueError('Unsupported native question template, no fallback answer')
 names={r['head']['predicate'] for r in choices}
 if len(names)!=1:raise ValueError('Question target is not unique under the learned signatures')
 name=next(iter(names));roles=preds[name]['roles'];arguments=[]
 for role in roles:
  if role in binding:arguments.append(binding[role])
  elif role in PERSON_ROLES:arguments.append(None)
  else:raise ValueError('No public query binding for learned role '+role)
 return {'predicate':name,'arguments':arguments,'positive':True}

def ground_case(raw,source,program):
 preds={p['name']:p for p in program['predicates']};facts=[];rejected=[]
 for i,row in enumerate(raw['facts']):
  a=row['atom'];p=preds[a['predicate']]
  if a['predicate']=='case_subject_year':continue  # neutral keys use public input independently
  missing=[term for role,term in zip(p['roles'],a['arguments']) if role in PERSON_ROLES and re.search(r'\b'+re.escape(term)+r'\b',row['quote']) is None]
  if missing or row['quote'] not in source['facts']:
   rejected.append({'row_index':i,'row':deepcopy(row),'reason':'unsupported participant/evidence','missing_participants':missing});continue
  facts.append(deepcopy(row))
 # Domain enumeration asserts no legal status. All people/year strings occur in
 # original input or in a verified relation; names are not replaced or invented.
 people=set();years=set(re.findall(r'(?<![\w$])((?:19|20)\d\d)\b',source['facts']+' '+source['query']))
 for row in raw['facts']:
  for role,term in zip(preds[row['atom']['predicate']]['roles'],row['atom']['arguments']):
   if role in PERSON_ROLES and re.search(r'\b'+re.escape(term)+r'\b',source['facts']+' '+source['query']):people.add(term)
 query=compile_question(source['query'],program)
 for role,term in zip(preds[query['predicate']]['roles'],query['arguments']):
  if role in PERSON_ROLES and term is not None:people.add(term)
 for person in sorted(people):
  for year in sorted(years):facts.append({'atom':{'predicate':'case_subject_year','arguments':[person,year],'positive':True},'quote':source['facts']+' '+source['query']})
 # Equality-based duplicate elimination changes no assertion, polarity or scope.
 unique=[];seen=set()
 for row in facts:
  a=row['atom'];k=(a['predicate'],tuple(a['arguments']),a['positive'])
  if k not in seen:seen.add(k);unique.append(row)
 return {'ordinal':raw['ordinal'],'facts':unique,'query':query,'unresolved':list(raw['unresolved'])}, {
   'original_model_query':deepcopy(raw['query']),'new_query_from_original_public_text':query,
   'model_query_replaced_as_a_path_not_semantically_adapted':raw['query']!=query,
   'rejected_model_rows':rejected,'neutral_enumeration_asserts_no_legal_relation':True,
   'supported_observed_status_rows':sum(r['atom']['predicate']!='case_subject_year' for r in unique)}
