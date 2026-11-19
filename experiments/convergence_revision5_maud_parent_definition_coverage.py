"""Recover linked ordinary-course definitions from exact MAUD TRAIN parent bytes."""

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
from zipfile import ZipFile

from experiments.convergence_formal_b1_observe import load_roster
from experiments.convergence_formal_bootstrap import POINTER as BOOTSTRAP
from experiments.convergence_formal_train_observe import pointer as observe_pointer
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.paired_interfaces.source_context import PAGE
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE/'revision5_MAUD_parent_definition_coverage_20261119'
ARCHIVE = Path('/media/sangfor/vdb/legal-skill-data/legal_skill_evolution_20261111/maud_data.zip')
ARM = 'common_teacher_skill_learning'
ORDINARY = 'Ordinary Course Covenant includes carve-out for Pandemic responses-Answer (Y/N)'
NEGATIVE = 'Negative Interim Covenant includes carveout for pandemic responses-Answer (Y/N)'
TERM = re.compile(r'[“"]\s*(Ordinary Course(?: of Business)?)\s*[”"]\s+(?:shall mean|means)\b\s*,?', re.I)
NEXT_TERM = re.compile(r'[“"][^“”"\n]{1,100}[”"]\s+(?:(?:shall )?mean[s]?\b|has the meaning|is defined|refers to)', re.I)
PANDEMIC = re.compile(r'covid|pandemic|epidemic|public health|sars|disease outbreak', re.I)
DEEMING = re.compile(r'\bshall be deemed to be in the Ordinary Course of Business\b', re.I)
ORDINARY_ONLY = re.compile(
    r'COVID-19 Measures being deemed to be in the ordinary course of business consistent with past practice',
    re.I,
)
# Review-only anchors for the two residual native reference exceptions.
LOCAL_DESCRIPTIONS = {
    (6,1): ('regulatory COVID-relief guidelines', 'shall not be a violation of this Section 5.2(b)'),
    (8,1): ('except for such temporary closures', 'access', 'COVID- 19'),
}


def unpage(text):
    without_pages = re.sub(r'\(Pages\s+\d+[-–]\d+\)\s*$', '', PAGE.sub('', text))
    # One released excerpt joins the disjunction and the following defined
    # token. Restore that token boundary for alignment only.
    return ' '.join(re.sub(r'\bor(?=COVID-19\b)', 'or ', without_pages).split())


def ordinary_use(header, term):
    name=re.escape(term)
    return re.search(r'\b(?:conduct|carry on|operate)\b[^.;]{0,180}\bin\s+(?:the\s+)?'+name+r'\b',
                     header,re.I)


def find_definition(parent, visible):
    """Resolve only a unique quoted definition already referenced by the native duty."""
    public_matches=list(TERM.finditer(visible))
    parent_matches=list(TERM.finditer(parent))
    if len(public_matches)>1 or len(parent_matches)>1:
        raise ValueError('This adapter requires a unique ordinary-course definition')
    if not public_matches:
        return None
    offered,=public_matches
    first,=parent_matches
    if offered.group(1).casefold()!=first.group(1).casefold():
        raise ValueError('The displayed definition must refer to the exact same term')
    if not ordinary_use(unpage(visible[:offered.start()]),offered.group(1)):
        raise ValueError('The originating ordinary covenant must use the defined term')
    following=NEXT_TERM.search(parent,first.end())
    if following is None:
        raise ValueError('The exact parent definition needs a subsequent definition boundary')
    body=parent[first.start():following.start()].rstrip()
    if parent.count(body)!=1:
        raise ValueError('The complete definition must bind one location')
    original=unpage(visible[offered.start():])
    full=unpage(body)
    if not full.startswith(original):
        raise ValueError('The native excerpt is not a literal prefix of its own parent definition')
    is_truncated=original!=full
    if is_truncated and not original.endswith(';'):
        raise ValueError('Review the new definition boundary before restoring a continuation')
    certified = bool(is_truncated and PANDEMIC.search(full) and DEEMING.search(full)
                     and not PANDEMIC.search(original))
    tail=full[len(original):].strip()
    return {'incomplete_native_definition':is_truncated,
            'new_pandemic_deeming_witness':certified,
            'definition_parent_span':[first.start(),first.start()+len(body)],
            'definition_text_sha256':digest(body),
            'original_definition_sha256':digest(original),
            'missing_continuation_sha256':digest(tail),
            'definition_parent_tokens':len(full.split()), 'native_definition_tokens':len(original.split())}


def native_predictions(db, journal, arm, b, source, receipt):
    key=source['key']
    stored=read(journal.directory(arm,b)/'predictions'/(digest(key)+'.json'))
    assert digest(stored)==receipt['predictions'][key]
    result=stored['result']
    trace,=result['reads'][0]['execution']['traces']
    row=db.execute('select status,role,source,purpose,result from calls where id=?',
                   (trace['physical_call_id'],)).fetchone()
    assert row[:4]==('completed','executor',key,'skill_actor')
    assert json.loads(row[4])['content']==trace['raw_content']
    return trace['physical_call_id'], {k:result['native'][k]['answer'] for k in (ORDINARY,NEGATIVE)}


def run():
    stage=ROOT/read(BOOTSTRAP)['artifact_root']
    study=read(stage/'binding.json')
    roster=load_roster(study)
    journal=TrainingJournal(stage,study,roster)
    parent_receipt=read(BASE/'postfreeze_M2_MAUD_source_scope_20261119'/'terminal.json')['parent_reference_audit']
    official_hash=sha(ARCHIVE)
    if official_hash!=parent_receipt['official_archive_sha256']:
        raise ValueError('Use the already verified local official parent archive')
    ground={}
    resolved={}
    ids=set()
    with ZipFile(ARCHIVE) as parent_zip, sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        db.execute('begin')
        ledger=dict(db.execute('select status,count(*) from calls group by status'))
        assert not ledger.get('reserved')
        for batch,rows in enumerate(roster,1):
            receipt=journal._observations(ARM,batch)
            for index,source in enumerate(x for x in rows if x['dataset']=='MAUD'):
                assert source['project_split']=='train'
                raw=parent_zip.read('data/contracts/'+source['parent_id']+'.txt')
                assert sha256(raw).hexdigest()==source['fulltext_raw_sha256']
                parent=raw.decode('utf-8-sig')
                views={v['id']:v['public']['source_text'] for v in source['views']}
                pos=batch,index
                key=source['key']
                support=find_definition(parent,views[ORDINARY])
                if pos in LOCAL_DESCRIPTIONS:
                    window=' '.join(views[NEGATIVE].split())
                    assert all(phrase in window for phrase in LOCAL_DESCRIPTIONS[pos])
                # A negative-covenant view may repeat an ordinary-covenant sentence.
                # Count this only when every pandemic cue is in that exact
                # deeming clause. Other nested or referenced scopes stay open.
                negative=views[NEGATIVE]
                ordinary_only=ORDINARY_ONLY.search(negative)
                excludes_negative=bool(ordinary_only and all(
                    ordinary_only.start()<=m.start()<ordinary_only.end() for m in PANDEMIC.finditer(negative)))
                cue={k:bool(PANDEMIC.search(views[k])) for k in (ORDINARY,NEGATIVE)}
                if excludes_negative:
                    assert ORDINARY_ONLY.search(views[ORDINARY])
                ground[key]={'parent_raw_sha256':source['fulltext_raw_sha256'],
                             'source_definition':support,'literal_cues':cue,
                             'negative_cues_belong_to_ordinary_qualification':excludes_negative,
                             'nested_case_has_unresolved_native_scope':pos in LOCAL_DESCRIPTIONS}
                physical,prediction=native_predictions(db,journal,ARM,batch,source,receipt)
                ids.add(physical)
                resolved[key]=prediction
    assert len(ground)==len(ids)==24
    coverage=Counter()
    for r in ground.values():
        defn=r['source_definition']
        if defn:
            coverage['verified_term_links']+=1
            coverage['partially_displayed_definitions']+=defn['incomplete_native_definition']
            coverage['omitted_positive_deeming_rules']+=defn['new_pandemic_deeming_witness']
        coverage['negative_view_repeats_only_ordinary_pandemic_rule']+=r['negative_cues_belong_to_ordinary_qualification']
    assert coverage=={'verified_term_links':6,'partially_displayed_definitions':1,
                      'omitted_positive_deeming_rules':1,
                      'negative_view_repeats_only_ordinary_pandemic_rule':1}
    immutable_json(HOME/'source_inventory.json',ground)

    # Compare original scoped evidence before reading the original TRAIN grades.
    binding=read(ROOT/read(observe_pointer(3))['artifact_root']/'binding.json')
    grade_path=binding['native_grade_paths']['MAUD']
    assert sha(ROOT/grade_path)==binding['native_grade_sha256'][grade_path]
    grades=read(ROOT/grade_path)
    scores={name:Counter() for name in ('stored_native_program','mention_anywhere','scope_and_definition_direct')}
    restored=[]
    discordances=[]
    for key,r in ground.items():
        defn=r['source_definition']
        for k in (ORDINARY,NEGATIVE):
            present=r['literal_cues'][k]
            lexical='Yes' if present else 'No'
            direct=lexical
            if k==ORDINARY and defn and defn['new_pandemic_deeming_witness']:
                direct='Yes'
                restored.append({'source_cell':'ordinary_covenant','definition_receipt':defn,
                                 'stored_answer':resolved[key][k],'direct_answer':direct,
                                 'native_label':grades[key][k]['answer']})
            if k==NEGATIVE and r['negative_cues_belong_to_ordinary_qualification']:
                direct='No'
            target=grades[key][k]['answer']
            for name,value in (('stored_native_program',resolved[key][k]),('mention_anywhere',lexical),
                               ('scope_and_definition_direct',direct)):
                scores[name]['correct']+=value==target
                scores[name]['units']+=1
            if direct!=target:
                discordances.append({'target_covenant':'ordinary' if k==ORDINARY else 'negative',
                                     'direct_answer':direct,'reference_label':target,
                                     'source_scope':'explicit_nested_loan_or_facility_exception'
                                                    if r['nested_case_has_unresolved_native_scope'] else 'unconfirmed'})
    assert len(restored)==1 and restored[0]['stored_answer']=='No' and restored[0]['native_label']=='Yes'
    assert len(discordances)==2 and all(d['source_scope']=='explicit_nested_loan_or_facility_exception'
                                     for d in discordances)
    t={'TRAIN_parent_archive_sha256':official_hash,'matching_TRAIN_parents':len(ground),
       'physical_responses_verified':len(ids),'source_coverage':dict(coverage),
       'scope_direct_is_retrospective_and_not_a_rule_for_unseen_contracts':True,
       'score_on_original_48_TRAIN_covenant_cells':{k:dict(v) for k,v in scores.items()},
       'recovered_definition':restored[0],'remaining_reference_differences':discordances,
       'native_question_text_source_or_manifest_modified':False,
       'same_information_direct_evidence_resolves_recovered_definition':True,
       'new_model_requests':0,'DEV_or_TEST_opened':False,'ledger_rows':sum(ledger.values()),
       'source_inventory_sha256':sha(HOME/'source_inventory.json'),'bound_runner_sha256':sha(Path(__file__))}
    immutable_json(HOME/'terminal.json',t)
    print(json.dumps(t,sort_keys=True),flush=True)


if __name__=='__main__':
    run()
