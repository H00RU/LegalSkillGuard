"""One fixed TRAIN failure: propose an exact, fuller source-context version.

No model client, reference-graph repair, grading call or heldout input. The
original source,177 reviews,outputs and scope/label facts remain unchanged.
The new input is a diagnostic proposal, not an independent new test case.
"""
from copy import deepcopy
import json
from pathlib import Path
import re
import sqlite3
from types import SimpleNamespace
import zipfile

from experiments.two_method_annotate import inputs
from experiments.two_method_graph_corpus import BASE, ROOT, read, sha
from experiments.two_method_reference_chain_audit import PREFLIGHT
from legal_skill_guard.paired_interfaces.control_answers import source_bundle
from legal_skill_guard.paired_interfaces.formal_actors import InterfaceActor
from legal_skill_guard.paired_interfaces.formal_training import ReferenceRegistry
from legal_skill_guard.paired_interfaces.source_context import enclosing_section
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.data import MAUD_ARCHIVE_SHA256
from legal_skill_guard.skill_evolution.objects import digest

TARGET='MAUD:2ae909b923008fa9f293069a959276b3f7c3c61e355e75092dd1ea6d14eb4db8'
TASK='Ordinary Course Covenant includes carve-out for Pandemic responses-Answer (Y/N)'


def revised_source(source,task,text,receipt):
    """Create an explicit new input version; preserve original declaration facts."""
    result=deepcopy(source)
    views=[v for v in result['views'] if v['id']==task]
    if len(views)!=1:raise ValueError('The target native task must exist exactly once')
    original=digest(source)
    views[0]['public']['source_text']=text
    result['source_context_revision']={'protocol':receipt['protocol'],
        'original_source_public_sha256':original,
        'original_runtime_actor_views_sha256':source.get('runtime_actor_views_sha256'),
        'original_declared_task_input_hash':source.get('declared_task_input_hash'),
        'revised_task':task,'source_context_receipt_sha256':digest(receipt),
        'exact_original_native_input':False,'new_independent_mother_or_blind_test':False,
        'cross_reference_or_native_task_closure_certified':False}
    # Original declaration hashes describe the old input, not the proposal.
    result.pop('declared_task_input_hash',None)
    result['runtime_actor_views_sha256']=digest(result['views'])
    return result


def run():
    if (BASE/'formal_study_v1/active_study.json').exists():
        raise ValueError('Preserve the active frozen study before proposing source changes')
    original_public=ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
    lock=read(BASE/'prepared/source_lock.json')
    if sha(original_public)!=lock['prepared_sha256']['train']['public']:
        raise ValueError('The preserved original TRAIN bytes changed')
    delivery=read(BASE/'revision_20261117/delivery.json')
    study=read(ROOT/delivery['preflight']['artifact_root']/'protocol.json')
    registry_path=ROOT/study['registry_path'];registry=read(registry_path)
    roles=read(registry_path.parent/'roles.json');role=next(r for r in roles if r['source']==TARGET)
    if role['role'] not in ('development','calibration'):
        raise ValueError('This fixed diagnostic may access only its existing TRAIN D/C mother')
    original_sources={s['key']:s for s in read(original_public)}
    source=original_sources[TARGET]
    if source['split']!='train' or source['dataset']!='MAUD' or not re.fullmatch(r'contract_\d+',source['parent_id']):
        raise ValueError('The pinned TRAIN parent binding is invalid')
    old_view=next(v for v in source['views'] if v['id']==TASK)
    old_excerpt=old_view['public']['source_text']
    archive=Path('/media/sangfor/vdb/legal-skill-data/legal_skill_evolution_20261111/maud_data.zip')
    if sha(archive)!=MAUD_ARCHIVE_SHA256:raise ValueError('The pinned official archive changed')
    member='data/contracts/'+source['parent_id']+'.txt'
    with zipfile.ZipFile(archive) as z:
        raw=z.read(member)  # Exactly this existing TRAIN mother; no other case is opened.
    from hashlib import sha256
    if sha256(raw).hexdigest()!=source['fulltext_raw_sha256']:
        raise ValueError('The original TRAIN full-parent digest differs')
    parent=raw.decode('utf-8-sig')
    text,receipt=enclosing_section(parent,old_excerpt,max_characters=32768)
    revised=revised_source(source,TASK,text,receipt)
    executor=SimpleNamespace(config=registry['executor'])  # Has no generate or ledger methods.
    actor=InterfaceActor(executor,BASE/'unused_context_metadata_actor',
        plan_assets=read(PREFLIGHT/'plan_assets.json'),source_inputs=inputs,
        pipeline_binding=registry['production_alignment_source_sha256'])
    views=actor.views(revised)
    new_view=next(v for v in views if TASK in v['native_tasks'])
    original_view=next(v for v in actor.views(source) if TASK in v['native_tasks'])
    card_entry=next(r for r in registry['reviews'] if r['source']==TARGET and r['view']==original_view['view'])
    old_card=read(ROOT/card_entry['path'])
    if digest(original_view['source_units'])!=old_card['source_units_sha256']:
        raise ValueError('The original reviewed input has changed')
    assert digest(new_view['source_units'])!=old_card['source_units_sha256']
    try:
        ReferenceRegistry(ROOT,registry,roles,{**original_sources,TARGET:revised},actor)
    except ValueError as error:
        if 'per-source public bindings' not in str(error):raise
        stale_gold_rejection=str(error)
    else:
        raise AssertionError('Old reference registry accepted changed source context')
    # Both actor families receive the very same proposed public task text.
    controls=source_bundle(revised)
    control_task=next(v for v in controls['public']['native_views'] if v['id']==TASK)
    assert control_task['public']==new_view['native_public'][TASK]
    assert digest(source['views'])==source['runtime_actor_views_sha256']
    protocol={'name':'fixed-TRAIN-MAUD-context-restoration-v1','source':TARGET,'role':role['role'],
        'task':TASK,'original_source_public_sha256':digest(source),
        'original_TRAIN_public_sha256':sha(original_public),'source_lock_sha256':sha(BASE/'prepared/source_lock.json'),
        'original_native_excerpt_sha256':digest(old_excerpt),
        'archive_sha256':MAUD_ARCHIVE_SHA256,'exact_parent_member':member,
        'parent_raw_sha256':source['fulltext_raw_sha256'],
        'prior_reference_entry':card_entry,'prior_M1_audit_root':delivery['M1_artifact_root'],
        'selection_scope':'the single already-recorded TRAIN native mismatch; not outcome-blind case selection',
        'context_extraction_receives_no_answer_or_pandemic_keyword':True,
        'new_model_or_teacher_calls':0,'no_reference_graph_or_native_score_created':True,
        'original_source_contexts_and_177_reference_cards_unchanged':True,
        'source_sha256':{str(p.relative_to(ROOT)):sha(p) for p in [
            Path(__file__).resolve(),ROOT/'legal_skill_guard/paired_interfaces/source_context.py',
            ROOT/'experiments/two_method_annotate.py',ROOT/'legal_skill_guard/paired_interfaces/control_answers.py',
            ROOT/'legal_skill_guard/paired_interfaces/formal_actors.py',
            ROOT/'legal_skill_guard/paired_interfaces/formal_training.py',
            ROOT/'legal_skill_guard/paired_interfaces/graph_interface.py',
            ROOT/'legal_skill_guard/skill_evolution/objects.py']}}
    out=BASE/'maud_scope_revision_20261117'/digest(protocol)
    immutable_json(out/'protocol.json',protocol)
    immutable_json(out/'context_receipt.json',receipt)
    immutable_json(out/'proposed_TRAIN_public_source.json',revised)
    immutable_json(out/'stale_reference_reuse_rejection.json',{
        'error':stale_gold_rejection,'actual_ReferenceRegistry_rejected_changed_public_source':True,
        'original_source_unit_digest':old_card['source_units_sha256'],
        'proposed_source_unit_digest':digest(new_view['source_units'])})
    immutable_json(out/'proposed_shared_control_bundle.json',controls)
    immutable_json(out/'proposed_interface_read_inputs.json',[{k:v[k] for k in
        ('view','native_tasks','source_units','read_input','scope')} for v in views])
    for name,expected in protocol['source_sha256'].items():
        target=out/'source_snapshot'/name;target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists():target.write_bytes((ROOT/name).read_bytes())
        assert sha(target)==expected
    ledger=ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3'
    with sqlite3.connect('file:'+str(ledger)+'?mode=ro',uri=True) as db:
        total=db.execute('select count(*) from calls').fetchone()[0]
        reserved=db.execute("select count(*) from calls where status='reserved'").fetchone()[0]
    # Verify originals again after writing all proposed outputs.
    assert sha(original_public)==protocol['original_TRAIN_public_sha256']
    assert all(sha(ROOT/e['path'])==e['sha256'] for e in registry['reviews'])
    summary={'artifact_root':str(out.relative_to(ROOT)),'source':TARGET,'role':role['role'],
        'original_excerpt_characters':len(old_excerpt),'proposed_source_characters':len(text),
        'syntactic_section_number':receipt['section_number'],
        'original_offered_units':len(original_view['source_units']),
        'proposed_offered_units':len(new_view['source_units']),
        'unique_literal_parent_anchor':True,'proposed_text_is_exact_parent_slice':True,
        'shared_public_context_matches_interface_and_control_actors':True,
        'old_reference_units_binding_matches_proposal':False,
        'old_registry_actual_reuse_rejected':True,
        'old177_references_not_promoted_to_new_context_gold':True,
        'restored_context_is_not_original_native_input_or_fresh_test':True,
        'no_new_native_prediction_score_or_mechanism_effect_claim':True,
        'graph_and_task_closure_still_require_a_new_source_only_review':True,
        'context_char_budget_is_not_a_token_or_model_capacity_certificate':True,
        'default_formal_input_not_switched':True,'new_model_or_teacher_requests':0,
        'continuous_physical_requests':total,'reserved':reserved,'goal_complete':False}
    immutable_json(out/'summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False),flush=True)
    return out,summary


if __name__=='__main__':run()
