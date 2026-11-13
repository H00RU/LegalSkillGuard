from pathlib import Path
import json
from legal_skill_guard.rr.checkpoint import immutable_json
from experiments import legal_skill_evolution_positive_binding_acquisition as e

checks=[
 ('4607',[28,32],['disclosure_conditions_28','disposal_binding_32'],
  [{'field':'disclosure confidentiality safeguard','verdict':'omitted','reason':'Clause28 makes permission expressly subject to this Confidentiality Agreement; need_to_know_only omits that safeguard.'},
   {'field':'disposal action/trigger/copy binding','verdict':'supported_on_reviewed_fields','reason':'Clause32 binds demand to return all information/copies, with destruction only on express written authorization.'}]),
 ('78ad',[18,20],['disclosure_conditions_18','disposal_binding_20'],
  [{'field':'disclosure recipient/need/confidentiality binding','verdict':'supported_on_reviewed_fields','reason':'Clause18 expressly covers employees or contractors with need to know and written confidentiality agreements.'},
   {'field':'disposal written authorization','verdict':'unsupported_added_qualification','reason':'Clause20 says return all copies or certify destruction upon request; no separate written authorization is stated, unlike the selected profile meaning.'}]),
 ('6fce',[10,12,15,16,20,21,24,26],['disclosure_roles_12','disposal_binding_15','disposal_binding_21','disposal_binding_24','disposal_binding_26'],
  [{'field':'disposal action/trigger and backup at anchor15','verdict':'supported_on_reviewed_fields','reason':'Clauses15/16 explicitly bind request to return and Project end to destruction, with backup/archival qualification.'},
   {'field':'disposal trigger/action at anchors21/24/26','verdict':'wrong_profile','reason':'These windows also carry Agreement-termination return duties and a legal-department record-copy qualification. They are repeatedly reduced to Project-end destruction/backup profile, losing the actual association or additional retention qualifier.'},
   {'field':'disclosure role at anchor12','verdict':'wrong_profile','reason':'Representatives in clause10 include the party employees and consultants; actual choice controlled-company employees/professionals is not that source class.'}]),
 ('e82b',[42,45],['disposal_binding_42','disposal_binding_45'],
  [{'field':'disposal action connection','verdict':'wrong_alternative_and_authorization','reason':'Clause42 says return information/copies AND clause45 destroy copies made by the receiver and recipients. The selected profile instead states return OR destruction only with written authorization.'}])]
rows=[]
for prefix,unit_ids,qids,judgments in checks:
 path=next((e.OUT/'acquisition/ConstraintAcquire').glob('ContractNLI_'+prefix+'*.json'));record=e.read(path);v=record['observation']['visible_inputs']
 lib=e.read(e.OUT/'ConstraintAcquire/learned.json')
 op={o['name']:o for o in lib['operations']}
 answers=[]
 for a in v['answers']:
  if a['id'] in qids:
   meanings={c['name']:c['meaning'] for c in op[a['operation']]['choices']}
   answers.append({**a,'actual_declared_choice_meaning':meanings.get(a['choice'],'unknown')})
 actual=e.read(e.OUT/'ConstraintAcquire/fitted_execution'/path.name)
 rows.append({'source':record['source'],'actual_source_units':[u for u in v['units'] if u['id'] in unit_ids],
  'actual_answers':answers,'actual_positive_roots':[s for s in actual['execution']['source_output']['statements'] if s['term'][0].startswith('bound_')],
  'field_judgments':judgments,'complete_source_semantics_certified':False})
result={'scope':'Post-generation review of four lawful acquisition TRAIN mothers; no future4 material/labels.',
 'reviews':rows,'new_model_requests':0,'model_programs_or_scores_changed':False,
 'not_in_current_frozen_fit_or_reuse_inputs':True,'goal_complete':False,
 'conclusion':'Real positive binding is exercised, with some source-supported field bindings; native gain cannot certify all generated norms. Current multi-field profile choices still conflate distinctions actually present in the sources.'}
immutable_json(e.OUT/'live_analysis/actual_source_review.json',result)
print('Saved four-source actual-reading and program-path review; 0 new model calls.')
