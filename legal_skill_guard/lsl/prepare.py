"""Create the fixed first empirical data package; never emits TEST bodies."""
from collections import Counter
from pathlib import Path
import json

from .data import NativeDataset,family_alias_audit,load_json,metadata_audit,source_audit,sha,text_sha,nonspace,write_json
from .projection import examples,max_view_count,compact,messages,target_for
from .composition_data import gold_graph,node_text,children_of
from .semantic_witness import mine_training


def prepare(raw,packet,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);packet=Path(packet)
    d=NativeDataset(raw,packet/'data_manifest/normbench_candidate_split_v1.json')
    train=d.split('train');dev=d.split('dev');audit={
        'metadata':metadata_audit(d.metadata),
        'family_alias_review':family_alias_audit(load_json(packet/'data_manifest/normbench_family_mapping_v1.json')),
        'train_native_quality':source_audit(train),'dev_native_quality':source_audit(dev)}
    if any(audit[s]['invalid'] for s in ('train_native_quality','dev_native_quality')):raise ValueError('Resolve genuine source/schema mismatch before freeze')
    if audit['metadata']['family_ids_cross_splits'] or audit['metadata']['duplicate_target_or_full_article_hashes']:raise ValueError('Split leakage')
    # The candidate manifest hashes whitespace-normalized legal text.
    for record in train+dev:
        meta=d._metadata[record['item_id']]
        for field,sourcefield in [('target_sha256','rule_text'),('full_article_sha256','full_article_text')]:
            if text_sha(nonspace(record['input'][sourcefield]))!=meta[field]:raise ValueError('Selected text hash mismatch')
    data={'source_sha256':sha(raw),'train_examples':[e for r in train for e in examples(r)],
          'train_records':train,'dev_records':dev,
          'train_graphs':[gold_graph(r) for r in train],'dev_graphs':[gold_graph(r) for r in dev]}
    squares={};stats=Counter()
    for graph in data['train_graphs']:
        result=mine_training(graph);squares[graph['item_id']]=result
        stats['sources']+=1;stats['squares']+=len(result)
        stats['sources_with_squares']+=bool(result)
        stats['sources_with_nonzero_witness']+=any(s['nonzero_interaction_observed'] for s in result)
        stats['witnessed_negative_cells']+=sum(len(s['negative']) for s in result)
        stats['proven_equivalent_cells']+=sum(len(s['equivalent']) for s in result)
    data['train_squares']=squares
    data['maximum_train_view_count']=max_view_count(train)
    feature_texts=set();token_texts=set()
    for e in data['train_examples']:
        feature_texts.update(e['current']['p']+e['current']['u']+[e['source'],e['new_source']]);token_texts.add(e['new_source'])
    for r in dev:
        for e in examples(r):feature_texts.update([e['source'],e['new_source']]);token_texts.add(e['new_source'])
    for g in data['train_graphs']+data['dev_graphs']:
        feature_texts.add(g['source']);feature_texts.update(node_text(n) for n in g['nodes'])
    data['feature_texts']=sorted(feature_texts);data['token_texts']=sorted(token_texts)
    write_json(out/'dataset.json',data)
    audit.update({'data_frozen_for_training':True,'manifest_modified':False,'test_body_or_gold_returned':False,
                  'train_source_count':len(train),'dev_source_count':len(dev),
                  'exposure_examples':len(data['train_examples']),'exposure_schedule':'one source-only midpoint sentence prefix and final, no gold boundaries as inputs',
                  'maximum_train_view_count':data['maximum_train_view_count'],
                  'native_empty_AND_OR_nodes_preserved':sum(n['kind'] in ('AND','OR') and not children_of(g)[i] for g in data['train_graphs']+data['dev_graphs'] for i,n in enumerate(g['nodes'])),
                  'training_witness_cache':dict(stats),'feature_strings':len(feature_texts),
                  'review_scope':'all open TRAIN/DEV schema, source containment, provenance; all split family metadata; no TEST text inspection',
                  'family_review':'normalized title aliases and explicit implementation/application title links reviewed; no additional linkage found; no metadata memberships changed',
                  'human_legal_reannotation_claimed':False})
    write_json(out/'data_audit.json',audit)
    write_json(out/'data_freeze.json',{'raw_sha256':sha(raw),'candidate_manifest_sha256':sha(d.manifest_path),
        'dataset_sha256':sha(out/'dataset.json'),'selected_ids':{s:[m['item_id'] for m in d.metadata if m['split']==s] for s in ('train','dev')},
        'TEST_metadata_count':128,'TEST_opened_for_research_or_model':False})
    return audit
