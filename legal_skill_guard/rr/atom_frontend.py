"""Source-aligned formula generation with deterministic connective assembly.

Only explicit controlled-English if/and/then structure is moved to code.
Every atom, including its polarity and arguments, must still come from the
model. The independent whole-source semantics checker remains mandatory.
"""
import json
import re

from .compiler_templates import validate_template
from .model_horn import LogicTranslationError,parse_model_horn,_atoms,_equivalent_rule
from .public_horn import parse_rule
from .source_structure import inspect_source
from .strict_contract import obj
from .wire_validation import validate_wire


def atom_slots(source):
    structure=inspect_source(source);slots={};units={}
    if source['dataset']!='ProofWriter_OWA_depth5':raise LogicTranslationError('This atomic frontend covers the original ProofWriter contract')
    for c in structure.ledger.clauses:
        text=structure.ledger.text[c.start:c.end];role=structure.roles[c.id]['role'];keys=[]
        if role=='rule':
            conditional=re.fullmatch(r'If (.+) then (.+?)\.?',text.strip(),re.I)
            generic=re.fullmatch(r'(?:All )?(.+?) (?:people|things) are ((?:not )?[a-z]+)\.?',text.strip(),re.I)
            if conditional:
                fragments=[('premise',part) for part in re.split(' and ',conditional[1])]+[('conclusion',conditional[2])]
            elif generic:
                parts=re.split(r',\s*| and ',generic[1])
                if not all(re.fullmatch('[a-z]+',part,re.I) for part in parts):
                    raise LogicTranslationError('No unambiguous generic adjective conjunction',source=c.id)
                fragments=[('premise',part) for part in parts]+[('conclusion',generic[2])]
            else:raise LogicTranslationError('No unambiguous explicit conditional skeleton',source=c.id)
        else:fragments=[(role,text)]
        for index,(position,fragment) in enumerate(fragments):
            key=c.id+'_'+str(index);keys.append(key)
            slots[key]={'source':c.id,'position':position,'text':fragment,'context':text,
                'literal_polarity_hint':'negative' if re.search(r'\bnot\b',fragment,re.I) else 'positive'}
        units[c.id]={'role':role,'keys':keys}
    return slots,units


def atom_schema(source):return obj({key:{'type':'string'} for key in atom_slots(source)[0]})


def _render_atom(atom):
    def term(t):return t[1:].upper() if t.startswith('?') else repr(t)
    return ('' if atom.positive else '-')+atom.predicate+'('+','.join(term(t) for t in atom.arguments)+')'


def template_atom_values(item):
    parsed=validate_template(item);slots,units=atom_slots(item['source']);rules={r.source:r for r in parsed.rules};values={}
    for sid,row in units.items():
        if row['role']=='rule':
            # Alpha/order normalization of an already fully accepted teacher
            # rule only. This never supplies a target-source model formula.
            expected=parse_rule(slots[row['keys'][0]]['context'],sid)
            if not _equivalent_rule(rules[sid],expected):raise ValueError('Template rule semantics differ')
            atoms=[*expected.body,expected.head]
        elif row['role']=='query':atoms=[parsed.query]
        else:atoms=[parsed.facts[sid]]
        if len(atoms)!=len(row['keys']):raise ValueError('Template connective alignment differs')
        values.update({key:_render_atom(a) for key,a in zip(row['keys'],atoms)})
    return values


def decode_atom_response(source,value):
    validate_wire(value,atom_schema(source));slots,units=atom_slots(source);lines=[]
    for sid,row in units.items():
        atoms=[]
        for key in row['keys']:
            values=_atoms(value[key])
            if len(values)!=1:raise LogicTranslationError('Each aligned slot supplies exactly one atom',source=sid,actual=value[key])
            atoms.append(values[0])
        if row['role']=='rule':statement=_render_atom(atoms[-1])+' :- '+', '.join(_render_atom(a) for a in atoms[:-1])
        else:statement=('?- ' if row['role']=='query' else '')+_render_atom(atoms[0])
        lines.append(statement+'. % '+sid)
    code='\n'.join(lines)
    return parse_model_horn(source,code),code


def atom_prompt(source,library=None,*,feedback=None):
    slots,_=atom_slots(source)
    system=('Translate each CURRENT English fragment into exactly ONE first-order atom. Return the JSON fields in the schema. '
        'The compiler already preserves the explicit if/and/then connections from the original text. '
        'Write the actual property/relation and its actual arguments, never predicate/head placeholders or source IDs. '
        'Use lowercase adjectives or verbs (big, cold, kind, eats, needs, sees, visits, chases, likes), '
        'uppercase shared rule variables X for someone/they, Y for something/it, and quoted actual entities. '
        'Keep named subjects and objects as constants; a named dog or lion is not the variable X. '
        'Use a leading minus only for an actual not in that fragment. The source polarity hint is lexical, not a task answer. '
        'Do not turn a positive cold into -cold. Each rule has its own variable namespace. '
        'Use the full context to resolve an ellipsis. Do not output implication, conjunction, query markers, periods, comments or native answers inside a field. '
        'Earlier TRAIN examples use their own entities and source IDs; translate CURRENT fragments independently.')
    if any(re.fullmatch(r'(?:All )?.+? (?:people|things) are (?:not )?[a-z]+\.?',v['context'].strip(),re.I) for v in slots.values()):
        system+=' In generic people/things rules (with or without All), every listed adjective and its conclusion use the same universal X.'
    examples=[]
    for item in (library or {}).get('compiler_templates',[]):
        if item['source']['key']==source['key']:raise ValueError('A compiler template cannot provide the current program')
        if item['source']['dataset']!=source['dataset']:continue
        examples.append({'template_hash':item['template_hash'],'fragments':atom_slots(item['source'])[0],
                         'translation':template_atom_values(item)})
    payload={}
    if examples:payload['compiler_training_examples']=examples
    # As in the reference few-shot builders, the actual question follows the
    # demonstrations. Current source IDs never belong to an example namespace.
    payload['CURRENT_fragments']=slots
    payload['source_only_feedback']=feedback
    return [{'role':'system','content':system},{'role':'user','content':json.dumps(payload,ensure_ascii=False,separators=(',',':'))}]
