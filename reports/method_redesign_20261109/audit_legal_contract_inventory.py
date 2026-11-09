"""Inventory literal cross-policy reuse in fixed TRAIN; no case/label inference."""
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[2]
REPORT=ROOT/'reports/method_redesign_20261109'


def normalize(text,section):
    text=re.sub(r'\bthis section\b','section '+section,text,flags=re.I)
    return re.sub(r'\s+',' ',text.lower()).strip()


def main():
    packet=ROOT/'data/packets/rr_v2/public_train.json'
    rows=json.loads(packet.read_text())['sources']
    seal=json.loads((ROOT/'artifacts/rr_method_redesign_20261109/legal_support_teacher_v1_20261110/seal.json').read_text())
    allowed=set(seal['sources']['train'])
    policies={}
    for row in rows:
        if row['key'] not in allowed or row['dataset']!='SARA_v2_Binary':continue
        text=row['public']['rules']
        section=re.search(r'§\s*(\d+)',text)[1]
        key=(section,hashlib.sha256(text.encode()).hexdigest())
        policies.setdefault(key,{'section':section,'text':text,'fixed_TRAIN_sources':[]})['fixed_TRAIN_sources'].append(row['key'])
    program=json.loads((ROOT/'artifacts/rr_method_redesign_20261109/legal_library_runtime_v1_20261109/frozen_library.json').read_text())['program']
    matches=[]
    for rule in program['rules']:
        section=re.search(r'§\s*(\d+)',rule['authority'])[1]
        guard=normalize(rule['guard_quote'],section)
        for policy in policies.values():
            if policy['section']==section:continue
            if guard in normalize(policy['text'],policy['section']):
                matches.append({'source_rule':rule['id'],'source_authority':rule['authority'],
                                'guard_quote':rule['guard_quote'],'target_policy':policy['section'],
                                'guard_word_count':len(rule['guard_quote'].split()),
                                'target_existing_TRAIN_sources':policy['fixed_TRAIN_sources'],
                                'literal_match_only_not_role_or_effect_semantics':True})
    out={'fixed_TRAIN_source_count':len(allowed),
         'SARA_TRAIN_source_count':sum(len(p['fixed_TRAIN_sources']) for p in policies.values()),
         'unique_policy_texts':len(policies),'policy_sections':sorted({p['section'] for p in policies.values()}),
         'existing_source_program_rules_checked':len(program['rules']),
         'public_packet_sha256':hashlib.sha256(packet.read_bytes()).hexdigest(),
         'cross_policy_literal_guard_matches':matches,
         'interpretation':'Literal occurrences only. Generic short phrases and repeated rules are not independent transfer successes. Nonliteral transfer cannot be ruled out by a substring inventory.',
         'case_facts_queries_or_grading_read_by_this_inventory':False,
         'new_model_calls':0,'new_sources_added':0,'DEV_or_TEST_packets_opened':False,
         'goal_complete':False}
    (REPORT/'legal_contract_reuse_inventory.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:out[k] for k in ('SARA_TRAIN_source_count','unique_policy_texts','policy_sections','existing_source_program_rules_checked')},ensure_ascii=False))
    print(json.dumps([{'rule':m['source_rule'],'target':m['target_policy'],'words':m['guard_word_count']} for m in matches],ensure_ascii=False))


if __name__=='__main__':main()
