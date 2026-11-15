"""Learned observation relations and a shared forward/backward transduction.

Only finite positive conjunctive views are needed for the current family/service
path. Rule meanings, schemas and copying requirements are acquired assets. This
module supplies joins, source-witness transport and lossless key-based splitting.
It does not supply a legal rule, a factual value or a model-error correction.
"""
from copy import deepcopy
import json

import jsonschema

from .native import record_schema
from .objects import digest
from .relational_rules import canonical, validate_language
from .span_compiler import occurrences


def _variable(value):
    return value.get('var') if isinstance(value, dict) and set(value)=={'var'} else None


def validate(contract, kernel):
    groups = {r['name']:r for r in contract['relations']}
    if len(groups)!=len(contract['relations']) or contract['enumerator'] not in groups:
        raise ValueError('Distinct observation relations and an actual key enumerator required')
    signatures = {}
    for name,group in groups.items():
        fields = [f['name'] for f in group['fields']]
        if len(set(fields))!=len(fields) or group['key'] not in fields:
            raise ValueError('A relation has distinct fields and one shared source-record key')
        if group['key'] != groups[contract['enumerator']]['key']:
            raise ValueError('Split relations share the same source-record key')
        if any(f.get('normalizer') not in (None,'literal_date') for f in group['fields']):
            raise ValueError('Only the existing exact calendar transport is supported')
        signatures[name] = {'kind':'observed','arguments':['scalar']*len(fields)}
    for rule in contract['rules']:
        head = rule['head']
        if head['predicate'] not in kernel['fact_arities']:
            raise ValueError('A transduction can emit public factual predicates only')
        signatures[head['predicate']] = {'kind':'output',
            'arguments':['scalar']*kernel['fact_arities'][head['predicate']]}
        if any(a['predicate'] not in groups or a['sign']!='positive' for a in rule['body']):
            raise ValueError('Transduction bodies are positive observation relations, without recursion')
    validate_language({'signatures':signatures,'constants':{'scalar':contract['constants']},'rules':contract['rules']})
    if not set(contract['covered_families']) <= {p for p,a in kernel['fact_arities'].items() if a==1}:
        raise ValueError('A family scan names only public unary input predicates')
    if not set(contract['covered_properties']) <= {p for p,a in kernel['fact_arities'].items() if a==2}:
        raise ValueError('A property scan names only public binary input predicates')
    for predicate in contract['covered_families']+contract['covered_properties']:
        if not any(r['head']['predicate']==predicate for r in contract['rules']):
            raise ValueError('Coverage needs an actual acquired transduction, not an empty default')
    return contract


def schema(contract, names=None):
    chosen = set(names) if names is not None else {g['name'] for g in contract['relations']}
    result = {}
    witness = record_schema({'field':{'const':'facts'},'quote':{'type':'string','minLength':1}})
    for group in contract['relations']:
        if group['name'] not in chosen:
            continue
        fields = {f['name']:{'type':[f.get('type','string'),'null'] if f.get('nullable',False)
                               else f.get('type','string')} for f in group['fields']}
        for field in group['fields']:
            if 'enum' in field:
                fields[field['name']]['enum']=list(field['enum'])+([None] if field.get('nullable',False)and None not in field['enum'] else [])
        fields[group['key']] = {'type':'string','minLength':1}
        common = {'witnesses':{'type':'array','minItems':1,'items':witness}}
        result[group['name']] = {'anyOf':[
            record_schema({**common,'status':{'const':'complete'},'records':{'type':'array','items':record_schema(fields)}}),
            record_schema({**common,'status':{'const':'unread'},'records':{'type':'null'}})]}
    if chosen-set(result):
        raise ValueError('Reading request names an unknown observation relation')
    return record_schema(result)


def source_copy_schema(contract, names, facts):
    """Compile existing finite copy obligations into the generation grammar.

    This restricts spelling only. It never picks an entity, a relation or a
    semantic attachment. Null/unread and every source-present choice remain.
    The normal forward checker still validates witnesses and event semantics.
    """
    result = schema(contract, names)
    for group in contract['relations']:
        if group['name'] not in result['properties']:
            continue
        fields = result['properties'][group['name']]['anyOf'][0]['properties']['records']['items']['properties']
        for field in group['fields']:
            if not field.get('copy') or 'enum' not in field:
                continue
            present = [v for v in field['enum'] if v is not None and occurrences(facts,str(v))]
            if field.get('nullable'):
                present.append(None)
            # Empty-domain relations may still return unread or a complete
            # empty scan. Leave their grammar unchanged rather than inventing
            # a value or treating a lexical absence as a semantic empty scan.
            if present:
                fields[field['name']]['enum'] = present
    return result


def _match(pattern, values, environment):
    binding = dict(environment)
    for term,value in zip(pattern,values):
        variable = _variable(term)
        if variable:
            if variable in binding and canonical(binding[variable])!=canonical(value):
                return None
            binding[variable] = value
        elif canonical(term)!=canonical(value):
            return None
    return binding


def forward(contract, observation, public, kernel):
    validate(contract,kernel)
    actual_schema = schema(contract)
    actual_schema['required'] = []
    jsonschema.validate(observation,actual_schema)
    groups = {g['name']:g for g in contract['relations']}
    tables, witnesses, keys, complete = {}, [], {}, set()
    for name,value in observation.items():
        for witness in value['witnesses']:
            if not occurrences(public['facts'],witness['quote']):
                raise ValueError('An observation witness must quote the actual current facts')
            if witness not in witnesses:
                witnesses.append(deepcopy(witness))
        if value['status']!='complete':
            continue
        group = groups[name]
        keys[name] = [r[group['key']] for r in value['records']]
        if len(set(keys[name]))!=len(keys[name]):
            raise ValueError('An observation relation is functional in its source-record key')
        tables[name] = []
        for row in value['records']:
            values = []
            for field in group['fields']:
                item = row[field['name']]
                if field.get('copy',False) and item is not None and not any(
                    occurrences(w['quote'],str(item)) for w in value['witnesses']):
                    raise ValueError('A copy field cannot contain a normalized or invented source value')
                if item is not None and field.get('normalizer')=='literal_date':
                    from .sara_statute_kernel import literal_date
                    item=literal_date(item)
                values.append(contract['key_domain']+'::'+item if field['name']==group['key'] else item)
            tables[name].append(values)
        complete.add(name)
    if keys:
        expected = set(next(iter(keys.values())))
        if any(set(v)!=expected for v in keys.values()):
            raise ValueError('Complete split relations must enumerate the same source keys')
    facts, uses, potential_subjects = [], [], {}
    for rule in contract['rules']:
        bindings = [{}]
        for atom in rule['body']:
            bindings = [merged for prior in bindings for row in tables.get(atom['predicate'],[])
                        if (merged:=_match(atom['arguments'],row,prior)) is not None]
        for binding in bindings:
            values = [binding[_variable(a)] if _variable(a) else a for a in rule['head']['arguments']]
            if values and values[0] is not None:
                potential_subjects.setdefault(rule['head']['predicate'],set()).add(values[0])
            if any(v is None for v in values):
                continue  # Complete scans may state that an optional property is absent.
            fact = {'predicate':rule['head']['predicate'],'arguments':values}
            if fact not in facts:
                facts.append(fact)
            uses.append({'rule':rule['id'],'fact':fact,'observation_relations':[a['predicate'] for a in rule['body']]})
    scans, properties = [], []
    subjects = {f['arguments'][0] for f in facts if kernel['fact_arities'][f['predicate']]==1}
    for predicate in contract['covered_families']+contract['covered_properties']:
        needed = {a['predicate'] for r in contract['rules'] if r['head']['predicate']==predicate for a in r['body']}
        if not needed<=complete or contract['enumerator'] not in complete:
            continue
        if predicate in contract['covered_families']:
            scans.append(predicate)
        else:
            referents=potential_subjects.get(predicate,set())
            if predicate!='country_':referents=referents|subjects
            properties.extend({'event':event,'predicate':predicate} for event in sorted(referents))
    return {'facts':facts,'negative_givens':[],'witnesses':witnesses,'complete':True,'reasons':[],
        'scope_contract':{'family_scans':scans,'event_properties':properties},
        'unread_relations':sorted(set(groups)-complete),'derivations':uses,
        'explicit_scopes_not_whole_case_completeness':True,'contract_sha256':digest(contract)}


def pullback(contract, target, *, observed_keys=()):
    """All rule branches yield demands; desired values never become facts."""
    groups = {g['name']:g for g in contract['relations']}
    demands = []
    for rule in contract['rules']:
        if rule['head']['predicate']!=target['predicate']:
            continue
        binding = {}
        compatible = True
        for term,value in zip(rule['head']['arguments'],target['arguments']):
            if _variable(value) or value is None:
                continue
            variable = _variable(term)
            if variable:
                if variable in binding and canonical(binding[variable])!=canonical(value):
                    compatible=False
                binding[variable]=value
            elif canonical(term)!=canonical(value):
                compatible=False
        if not compatible:
            continue
        branch = []
        for atom in rule['body']:
            group = groups[atom['predicate']]
            pattern = {f['name']:binding.get(_variable(a),a) if _variable(a) else a
                       for f,a in zip(group['fields'],atom['arguments'])}
            key = pattern[group['key']]
            # Only an actually observed source key may narrow a factual reader.
            # Goal persons, dates and cue constants stay symbolic matching tests.
            prefix=contract['key_domain']+'::'
            source_key = key[len(prefix):] if isinstance(key,str) and key in observed_keys and key.startswith(prefix) else None
            branch.append({'relation':atom['predicate'],'observed_source_key':source_key,
                'required_fields':[f['name'] for f in group['fields']],
                'symbolic_match_after_reading':pattern,'do_not_prefill_desired_values':True})
        demands.append({'rule':rule['id'],'joined_demands':branch})
    return {'target':deepcopy(target),'branches':demands,'all_transduction_branches_preserved':True,
            'not_an_observation_or_answer':True}


def split(contract, relation, partitions):
    """Refine reading units, preserving the fully observed keyed relation.

    The partition is learned from real errors. This operator adds no semantic
    literal: it copies existing rules and drops only unused existential fields.
    """
    result = deepcopy(contract)
    original = next(g for g in result['relations'] if g['name']==relation)
    fields = {f['name']:f for f in original['fields']}
    key = original['key']
    flattened = [name for group in partitions for name in group['fields']]
    if len(flattened)!=len(set(flattened)) or set(flattened)!=set(fields)-{key}:
        raise ValueError('A split partitions every non-key field exactly once')
    replacements = [{**deepcopy(original),'name':part['name'],
        'fields':[deepcopy(fields[key])]+[deepcopy(fields[name]) for name in part['fields']],
        'prompt':part['prompt']} for part in partitions]
    result['relations'] = [g for g in result['relations'] if g['name']!=relation]+replacements
    if result['enumerator']==relation:
        result['enumerator']=replacements[0]['name']
    ordered = [f['name'] for f in original['fields']]
    for rule in result['rules']:
        body=[]
        for index,atom in enumerate(rule['body']):
            if atom['predicate']!=relation:
                body.append(atom)
                continue
            values=dict(zip(ordered,atom['arguments']))
            relevant={_variable(a) for a in rule['head']['arguments']}
            relevant.update(_variable(a) for j,other in enumerate(rule['body']) if j!=index for a in other['arguments'])
            variables=[_variable(a) for a in atom['arguments'] if _variable(a)]
            relevant.update(v for v in variables if variables.count(v)>1)
            for group in replacements:
                names=[f['name'] for f in group['fields']]
                needed=any(not _variable(values[n]) or _variable(values[n]) in relevant for n in names if n!=key)
                if needed or (len(names)==1):
                    body.append({'predicate':group['name'],'arguments':[values[n] for n in names],'sign':'positive'})
            if not any(a['predicate'] in {g['name'] for g in replacements} for a in body):
                group=replacements[0]
                body.append({'predicate':group['name'],'arguments':[values[f['name']] for f in group['fields']],'sign':'positive'})
        rule['body']=body
    result['update']={'operation':'shared_key_relation_split','parent_sha256':digest(contract),
        'relation':relation,'new_relations':[r['name'] for r in replacements],
        'semantic_literals_added':False,'full_read_equivalence_requires_identical_complete_key_domains':True}
    return result
