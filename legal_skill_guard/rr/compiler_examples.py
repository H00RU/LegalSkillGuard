"""Validated earlier-TRAIN compiler examples, shared by every inference arm.

An example teaches the source IR format. Its program is never used as the
current prediction, and it neither discharges source coverage nor resolves a
current factual observation.
"""
from copy import deepcopy

from .coverage import digest


def validate_compiler_example(example):
    from .compiler_contract import decode_compiler_response
    from .source_inference import _decode
    from .source_program import compile_source
    if set(example) != {'source', 'program_json', 'origin', 'example_hash'}:
        raise ValueError('Compiler example needs exact public source, program and provenance')
    value = {k: example[k] for k in ('source', 'program_json', 'origin')}
    if digest(value) != example['example_hash']:
        raise ValueError('Compiler example content hash differs')
    source = example['source']
    if source['content_hash'] != digest(source['public']):
        raise ValueError('Compiler example public input hash differs')
    if set(source) & {'answer', 'targets', 'grade', 'score', 'reference_program', 'reference_arguments'}:
        raise ValueError('Compiler examples contain public inputs and programs only')
    if example['origin']['role'] != 'teacher' or not example['origin']['call_id']:
        raise ValueError('Compiler example needs its preserved TRAIN teacher origin')
    wire = _decode(example['program_json'])
    canonical = decode_compiler_response(wire, source)
    compiled = compile_source(source, canonical)
    return source, wire, compiled


def compiler_examples_for_source(library, source):
    from .source_format import native_schema
    examples = []
    for example in (library or {}).get('compiler_examples', []):
        previous, wire, compiled = validate_compiler_example(example)
        if previous['key'] == source['key']:
            raise ValueError('A compiler example cannot supply the current source program')
        if native_schema(previous['dataset']) != native_schema(source['dataset']):
            continue
        structure = compiled['structure']
        examples.append({'example_hash': example['example_hash'], 'dataset': previous['dataset'],
            'units': [{'id': c.id, **structure.roles[c.id],
                       'text': structure.ledger.text[c.start:c.end]}
                      for c in structure.ledger.clauses],
            'program': deepcopy(wire)})
    return examples
