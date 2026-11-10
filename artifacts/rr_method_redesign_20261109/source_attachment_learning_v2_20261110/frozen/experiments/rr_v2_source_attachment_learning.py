"""Obtain shared source forests, then fit partial-feedback attachment models.

No native DEV/TEST text or annotations are read. A new run identity records this
different experiment within the same Goal and persistent cumulative ledger.
"""
import argparse
import hashlib
import json
import re
import sqlite3
from pathlib import Path
import jsonschema

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.contract_compiler_runtime import run
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.method_client import MethodExecutor
from legal_skill_guard.rr.method_ledger import MethodLedger
from legal_skill_guard.rr.semantic_frames import obj
from legal_skill_guard.rr.source_attachment_learning import HEADS, validate_forest, problem, fit, choose, project, native_answers
from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues

ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'artifacts/rr_method_redesign_20261109'
OLD=BASE/'contract_attachment_update_v1_20261110';RUN='source_attachment_learning_v2_20261110';STAGE=BASE/RUN
PROTOCOL=ROOT/'reports/method_redesign_20261109/source_attachment_learning_protocol.md'
S={'type':'string'};A=lambda t:{'type':'array','items':t};E=lambda v:{'type':'string','enum':v}
READING=obj({'head_kind':E(HEADS),'negation_scope':E(['none','head','action']),
 'modal':E(['none','shall','may']),'head_quote':S,'action_quote':S,'negation_quote':S,
 'actor_quote':S,'object_quote':S,'exception_target':{'anyOf':[S,{'type':'null'}]},'conditions':A(S),'references':A(S)})
SCHEMA=obj({'rules':A(obj({'rule_id':S,'readings':A(READING)}))})


def source_schema(material):
 """Required claim keys and literal action anchors, with no semantic repair."""
 stems={'share':['disclos','divulg','reveal','communicat','share','transfer','access'],
        'return_or_destroy':['return','destroy','deliver','eras','delet'],
        'retain':['retain','keep','archiv','cop','maintain']}
 ids=[r['id'] for r in material['graph']['rules']];properties={};anchors={}
 for rule in material['graph']['rules']:
  words=list(dict.fromkeys(re.findall(r"\b[\w’'-]+\b",' '.join(rule['source_quotes']))))
  terms=[w for w in words if any(w.casefold().startswith(s) for s in stems[rule['action']])]
  if not terms:raise ValueError('No literal action anchor for '+rule['id'])
  anchors[rule['id']]=terms
  fields=dict(READING['properties']);fields['action_quote']=E(terms)
  other=[k for k in ids if k!=rule['id']]
  fields['exception_target']={'anyOf':[E(other),{'type':'null'}]} if other else {'type':'null'}
  properties[rule['id']]={'type':'array','minItems':1,'maxItems':3,'items':obj(fields)}
 return obj(properties),anchors


def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def snapshot():
 with sqlite3.connect('file:'+str(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3')+'?mode=ro',uri=True) as c:
  return {t:c.execute('select * from '+t+' order by 1').fetchall() for t in ['calls','meta','oracle_views']}


def prepare():
 if (STAGE/'seal.json').exists():return read(STAGE/'seal.json')
 old=read(OLD/'training_seal.json');prior=read(BASE/'contract_compiler_induction_v1_20261110/training_seal.json')
 pub={p['key']:p for p in read(ROOT/'data/packets/rr_v2/public_train.json')['sources']}
 reserved=[]
 for i in [114,116,117,118]:
  source=old['sources']['train'][i-1];p=pub[source];assert p['dataset']=='ContractNLI'
  reserved.append({'ordinal':i,'source':source,'group':p['group'],'document_sha256':hashlib.sha256(p['public']['document'].encode()).hexdigest()})
 immutable_json(STAGE/'source_only_reuse_plan.json',{'original_TRAIN_mothers_fixed_before_new_generation':[114,116,117,118],
  'sources':reserved,'native_hypothesis_pairs_or_labels_added':0,'prior_diagnostic_112_not_blind':True})
 # These are author-checked partial source annotations, not new native NLI
 # labels or full gold source trees. Both learners/controls receive them.
 feedback={
  'p15':[{'kind':'source_head','rule_id':'rule-4','equals':{'negation_scope':'none'},'meaning_formula':['prohibition','action'],
   'contains':{'head_quote':'prohibited','action_quote':'disclos'},'list_contains':{'references':'Except as provided herein'}}],
  'p20':[{'kind':'source_head','rule_id':'rule-2','equals':{'head_kind':'breach','negation_scope':'head'},
   'contains':{'head_quote':'breached','action_quote':'disclosed'},'list_contains':{'conditions':'if the Confidential Information is disclosed'}}],
  'p111':[{'kind':'joint_exception_binding','rule_id':'rule-6','target_rule_id':'rule-5','qualification_contains':'archival'}]}
 shared=('Produce a compact source-grounded forest of genuinely plausible interpretations of the existing source claims. '
  'Read the full original contract. The listed claims identify current actions/receiver scopes to interpret, not trusted effect labels. '
  'For EVERY listed rule_id give 1..3 readings, ranked best first. Do not manufacture unlikely corruptions to fill a quota; one clear reading is allowed. '
  'Each reading distinguishes the actual semantic predicate head from embedded conduct and preserves where negation applies. '
  'head_kind is action, permission, obligation, prohibition, restriction, breach, possibility, or other. '
  'restriction covers a predicate that restricts/precludes conduct; head negation negates that predicate, not its embedded action. '
  'breach is a legal consequence, not a conduct ban. possibility/causal descriptions are not permissions. '
  'For an action head modal shall/may represents the source modal; otherwise none is normally appropriate. '
  'negation_scope none/head/action records the source construction, not an answer-label convention. '
  'head_quote/action_quote/negation_quote must be exact source substrings sufficiently specific to locate the relevant predicate/conduct/polarity. '
  'actor_quote and object_quote are canonical SOURCE QUOTES identifying the subject and information object of THIS claim. '
  'Resolve such/its/their only when supported by the actual contract; an earlier fully qualified source phrase may be the canonical anchor. '
  'Include the information owner in the object anchor where stated. Agreement existence, related discussions, identity and Confidential Information may be different objects. '
  'An unresolved binding must be empty, not invented. All nonempty quote/condition/reference strings must occur literally in this document. '
  'conditions preserve all actual qualifications of this interpretation, and references preserve its source exception/reference phrases. '
  'exception_target is another listed rule_id ONLY for an actual source-supported exception/qualification relationship; it may cross actions. '
  'A reference to exceptions elsewhere is not itself a grant. Do not assume every permission overrides every prohibition. '
  'No native questions, feedback or expected answers are provided. Preserve uncertainty as alternatives rather than arbitrarily inventing a complete rule. '
  'Return the fixed JSON object with EVERY rule_id as a required property. Each value is the ranked reading array. '
  'action_quote must select an actual verb anchor from the provided menu for that rule, never the action category name. '
  'Use null when there is no supported exception target, never an empty string. Do not enumerate all negation values as distractors. '
  'Keep other quotes concise, and do not restate whole paragraphs when a precise source phrase suffices. ')
 paths=['experiments/rr_v2_source_attachment_learning.py','legal_skill_guard/rr/source_attachment_learning.py',
  'legal_skill_guard/rr/contract_scope_learning.py','legal_skill_guard/rr/contract_compiler_runtime.py',
  'legal_skill_guard/rr/method_client.py','legal_skill_guard/rr/method_ledger.py','legal_skill_guard/rr/client.py']
 files={p:sha(ROOT/p) for p in paths}
 seal={'run_id':RUN,'config':old['config'],'sources':old['sources'],'training':old['documents'],
  'partial_source_feedback':feedback,'feedback_supervision':'Author-refined source spans/edges on existing TRAIN15/20/111; shared by all controls; not native NLI labels',
  'annotation_units':{'source_mothers':3,'partial_constraints':3,'source_head_constraints':2,'joint_binding_constraints':1},
  'system':shared,'schema_template':READING,'files':files,'binding':{'code_hash':digest(files),'config_hash':digest(old['config'])},
  'protocol_sha256':sha(PROTOCOL),'original_seed_code':prior['training'] and read(BASE/'contract_compiler_induction_v1_20261110/ordinary_program_learned.json')['physical_response']['value']['code'],
  'original_pair_supervision_reused_no_new_native_views':True,'DEV_text_labels_loaded':False,'goal_complete':False}
 for m in old['documents']:assert strict_output_schema_issues(source_schema(m)[0])==[]
 immutable_json(STAGE/'seal.json',seal)
 for p in files:
  out=STAGE/'frozen'/p;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes((ROOT/p).read_bytes())
 return seal


def ledger(s):
 return MethodLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,binding=s['binding'],sources=s['sources'],
  authorization_hash=s['protocol_sha256'],question='Can source-aligned partial feedback update reusable attachment/binding preferences beyond a shared lexical/typed parsing prior and ordinary same-information controls, without whole-clause regex patches? Exact latent interpretation learning on existing TRAIN; no DEV/TEST or new native pairs.')


def generate(key):
 out=STAGE/(key+'_forest.json')
 if out.exists():print(json.dumps({'existing':True,'key':key,'no_redispatch':True}));return
 s=prepare()
 for p,h in s['files'].items():assert sha(ROOT/p)==h,p
 material=next((x for x in s['training'] if x['key']==key),None)
 if material is None:
  selected=next(x for x in read(STAGE/'source_only_reuse_plan.json')['sources'] if 'p'+str(x['ordinal'])==key)
  assert (STAGE/'reuse_freeze.json').exists(),'Learned method and all controls must freeze before reserved source execution'
  pub={p['key']:p for p in read(ROOT/'data/packets/rr_v2/public_train.json')['sources']};document=pub[selected['source']]['public']['document']
  assert hashlib.sha256(document.encode()).hexdigest()==selected['document_sha256']
  code=s['original_seed_code']+'\n\ndef infer(document, query):\n    return _compile_graph(document)\n'
  material={'key':key,'source':selected['source'],'document':document,'graph':run(code,document,[None])[0]['value'],'examples':[]}
 # Do not tell the common parser original effect labels or corrective feedback.
 claims=[{'rule_id':r['id'],'action':r['action'],'scope':next(x for x in material['graph']['scopes'] if x['id']==r['scope_id']),
           'support_quotes':r['source_quotes']} for r in material['graph']['rules']]
 schema,anchors=source_schema(material)
 messages=[{'role':'system','content':s['system']},{'role':'user','content':json.dumps({'document':material['document'],'claims':claims,'literal_action_anchors':anchors},ensure_ascii=False)}]
 e=MethodExecutor(ledger(s),STAGE,s['config']['executor']);e.readiness()
 wire=e.generate(RUN+':forest:'+key,source=material['source'],purpose='method_train_synthesis',messages=messages,thinking=False,schema=schema)
 result={'key':key,'material':material,'wire':wire,'core_learning_success_not_claimed':True}
 try:
  value=json.loads(wire['content']);jsonschema.validate(value,schema)
  forest={'rules':[{'rule_id':r['id'],'readings':value[r['id']]} for r in material['graph']['rules']]}
  validate_forest(forest,material)
  p=problem(material,forest,s['partial_source_feedback'].get(key,[]))
  result.update(forest=forest,accepted=True,assignments=len(p['choices']),type_valid=int(p['valid'].sum()),compatible=int(p['compatible'].sum()),prior=choose(None,p))
 except Exception as exc:result.update(accepted=False,error=type(exc).__name__+': '+str(exc))
 immutable_json(out,result)
 print(json.dumps({k:v for k,v in result.items() if k not in ['wire','material','forest']},ensure_ascii=False),flush=True)


def learn():
 s=prepare();rows={x['key']:read(STAGE/(x['key']+'_forest.json')) for x in s['training']}
 if not all(r['accepted'] for r in rows.values()):raise ValueError('First localize actual invalid/missing forest; no implicit fallback')
 problems=[problem(r['material'],r['forest'],s['partial_source_feedback'].get(key,[])) for key,r in rows.items()]
 models={m:fit(problems,mode=m) for m in ['marginal','hard_em']}
 output={'models':models,'training_choices':{m:{p['key']:choose(model,p) for p in problems} for m,model in models.items()},
  'prior_choices':{p['key']:choose(None,p) for p in problems},'partial_source_feedback':s['partial_source_feedback'],
  'no_claim_of_new_CRF_mathematics':True,'new_model_calls_for_parameter_learning':0,'goal_complete':False}
 immutable_json(STAGE/'learned_attachment_parameters.json',output)
 print(json.dumps({'accepted':{m:x['accepted'] for m,x in models.items()},'new_model_calls':0,'goal_complete':False}))


if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action');a=p.parse_args()
 if a.action=='prepare':prepare();print(json.dumps({'prepared':True,'new_model_calls':0}))
 elif a.action=='learn':learn()
 else:generate(a.action)
