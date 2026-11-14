def subterms(value):
    out = []
    todo = [value]
    while todo:
        item = todo.pop()
        if isinstance(item, list) and item:
            out.append(item)
            i = 1
            while i < len(item):
                if isinstance(item[i], list):
                    todo.append(item[i])
                i += 1
    return out

def has_tag(value, name):
    for item in subterms(value):
        if item[0] == name:
            return True
    return False

def owner_ok(value):
    return isinstance(value, list) and bool(value) and (value[0] in ('receiving_party', 'party', 'named_recipient'))

def class_tags(x, definitions):
    tags = set()
    todo = [x]
    seen = set()
    while todo:
        value = todo.pop()
        if not isinstance(value, list) or not value:
            continue
        name = value[0]
        if name == 'representatives_of':
            key = str(value[1]) if len(value) > 1 else ''
            if key not in seen:
                seen.add(key)
                for owner, members in definitions:
                    if str(owner) == key or (isinstance(owner, list) and owner and (owner[0] == 'party')):
                        todo.append(members)
            continue
        if name == 'internal_personnel_of' and len(value) > 1 and owner_ok(value[1]):
            tags.add('employees_of')
        if name in ('employees_of', 'directors_of', 'officers_of', 'legal_advisors_of', 'financial_advisors_of', 'professional_advisors_of', 'accountants_of', 'consultants_of', 'agents_of', 'independent_contractors_of', 'lenders_of'):
            if len(value) > 1 and owner_ok(value[1]):
                tags.add(name)
            continue
        if name == 'third_parties':
            tags.add(name)
            continue
        i = 1
        while i < len(value):
            if isinstance(value[i], list):
                todo.append(value[i])
            i += 1
    return tags

def unique(values):
    out = []
    for value in values:
        if value not in out:
            out.append(value)
    return out

def apply(inputs,premises):
    task=inputs.get('task_id')
    if task not in ('nda-5','nda-7','nda-16','nda-20'):
        return {'handled':False,'answer':None,'used_nodes':[]}
    entries=d_entries(premises)
    definitions=[]
    definition_roots=[]
    permissions=[]
    prohibitions=[]
    disposals=[]
    retention_permissions=[]
    retention_prohibitions=[]
    residual=[]
    absence_disclosure=[]
    absence_disposal=[]
    absence_retention=[]
    for term,root in entries:
        if term[0]=='define_representative' and len(term)==3:
            definitions.append([term[1],term[2]])
            definition_roots.append(root)
        elif term[0]=='complete_source_no_disclosure_permission':
            absence_disclosure.append(root)
        elif term[0]=='complete_source_no_disposal_obligation':
            absence_disposal.append(root)
        elif term[0]=='complete_source_no_retention_effect':
            absence_retention.append(root)
        elif term[0]=='source_residual_observation_v3':
            residual.append(root)
        elif term[0]=='disposal_obligation' and len(term)==5:
            disposals.append([term,root])
        elif term[0] in ('retention_permission','retention_exception'):
            retention_permissions.append(root)
        elif term[0] in ('retention_prohibition','absolute_retention_prohibition'):
            retention_prohibitions.append(root)
    for term,root in entries:
        if term[0] not in ('permission','prohibition') or len(term)<3:
            continue
        action=term[2]
        if not isinstance(action,list) or len(action)!=3 or action[0]!='disclose' or not d_has(action[1],'confidential_information'):
            continue
        item=[root,d_role_tags(action[2],definitions),action[2]]
        if term[0]=='permission':
            permissions.append(item)
        else:
            prohibitions.append(item)
    if task in ('nda-5','nda-7'):
        relevant=[]
        for root,tags,recipient in permissions:
            relevant.append(root)
            if task=='nda-5' and 'employees' in tags:
                used=[root]
                if d_has(recipient,'representatives_of'):
                    used.extend(definition_roots)
                return {'handled':True,'answer':'Entailment','used_nodes':d_unique(used)}
            if task=='nda-7' and tags.intersection({'professionals','third_parties'}):
                used=[root]
                if d_has(recipient,'representatives_of'):
                    used.extend(definition_roots)
                return {'handled':True,'answer':'Entailment','used_nodes':d_unique(used)}
        for root,tags,recipient in prohibitions:
            relevant.append(root)
            if d_has(recipient,'outsiders_to') or d_has(recipient,'acquired_recipient_class_v3'):
                continue
            if task=='nda-5' and 'employees' in tags:
                return {'handled':True,'answer':'Contradiction','used_nodes':[root]}
            if task=='nda-7' and tags.intersection({'professionals','third_parties'}):
                return {'handled':True,'answer':'Contradiction','used_nodes':[root]}
        if relevant or absence_disclosure:
            return {'handled':True,'answer':'NotMentioned','used_nodes':d_unique(relevant+definition_roots+absence_disclosure)}
        if residual:
            return {'handled':False,'answer':None,'used_nodes':[]}
        return {'handled':False,'answer':None,'used_nodes':[]}
    if task=='nda-16':
        endpoint=[]
        relevant=[]
        for term,root in disposals:
            if d_has(term[2],'return_to') or d_has(term[2],'destroy'):
                relevant.append(root)
                if d_endpoint_trigger(term[3]):
                    endpoint.append(root)
        if endpoint:
            return {'handled':True,'answer':'Entailment','used_nodes':d_unique(endpoint)}
        if absence_disposal and not relevant:
            return {'handled':True,'answer':'NotMentioned','used_nodes':d_unique(absence_disposal)}
        if residual:
            return {'handled':False,'answer':None,'used_nodes':[]}
        if relevant:
            return {'handled':True,'answer':'NotMentioned','used_nodes':d_unique(relevant)}
        return {'handled':False,'answer':None,'used_nodes':[]}
    if retention_permissions:
        return {'handled':True,'answer':'Entailment','used_nodes':d_unique(retention_permissions)}
    if retention_prohibitions:
        return {'handled':True,'answer':'Contradiction','used_nodes':d_unique(retention_prohibitions)}
    relevant=[]
    full_return=[]
    for term,root in disposals:
        if d_has(term[2],'return_to') or d_has(term[2],'destroy'):
            relevant.append(root)
            if d_full_return_only(term[2]):
                full_return.append(root)
    if full_return:
        return {'handled':True,'answer':'Contradiction','used_nodes':d_unique(full_return)}
    if absence_retention:
        return {'handled':True,'answer':'NotMentioned','used_nodes':d_unique(absence_retention)}
    if residual:
        return {'handled':False,'answer':None,'used_nodes':[]}
    if relevant:
        return {'handled':True,'answer':'NotMentioned','used_nodes':d_unique(relevant)}
    return {'handled':False,'answer':None,'used_nodes':[]}

def disclosure_decision(task, entries):
    definitions = []
    definition_roots = []
    permissions = []
    prohibitions = []
    relevant = []
    absence = []
    for term, root in entries:
        if term[0] == 'complete_source_no_disclosure_permission':
            absence.append(root)
        if term[0] == 'define_representative' and len(term) == 3:
            definitions.append((term[1], term[2]))
            definition_roots.append(root)
    for term, root in entries:
        if term[0] not in ('permission', 'prohibition') or len(term) < 3:
            continue
        action = term[2]
        if not isinstance(action, list) or len(action) != 3 or action[0] != 'disclose':
            continue
        if not has_tag(action[1], 'confidential_information'):
            continue
        relevant.append(root)
        tags = class_tags(action[2], definitions)
        if term[0] == 'permission':
            permissions.append((root, tags, action[2]))
        else:
            prohibitions.append((root, tags, action[2]))
    wanted = {'employees_of'} if task == 'nda-5' else {'third_parties', 'consultants_of', 'agents_of', 'legal_advisors_of', 'financial_advisors_of', 'professional_advisors_of', 'accountants_of', 'independent_contractors_of'}
    for root, tags, recipient in permissions:
        if tags.intersection(wanted):
            used = [root]
            if has_tag(recipient, 'representatives_of'):
                used.extend(definition_roots)
            return {'handled': True, 'answer': 'Entailment', 'used_nodes': unique(used)}
    for root, tags, recipient in prohibitions:
        if has_tag(recipient, 'outsiders_to'):
            continue
        if tags.intersection(wanted):
            return {'handled': True, 'answer': 'Contradiction', 'used_nodes': [root]}
    if relevant or absence:
        return {'handled': True, 'answer': 'NotMentioned', 'used_nodes': unique(relevant + definition_roots + absence)}
    return {'handled': False, 'answer': None, 'used_nodes': []}

def collect_entries(premises):
    nodes = premises.get('nodes', [])
    roots = premises.get('roots', [])
    by_id = {}
    for node in nodes:
        if isinstance(node, dict):
            by_id[node.get('id')] = node
    out = []
    for root in roots:
        todo = [root]
        seen = set()
        while todo:
            node_id = todo.pop()
            if node_id in seen or node_id not in by_id:
                continue
            seen.add(node_id)
            node = by_id[node_id]
            for term in all_subterms(node.get('term')):
                out.append((term, root))
            for child in node.get('child_ids', []):
                todo.append(child)
    return out

def role_tags(value, definitions):
    tags = set()
    todo = [value]
    expanded = set()
    while todo:
        item = todo.pop()
        if not isinstance(item, list) or not item:
            continue
        name = item[0]
        if name == 'representatives_of' and len(item) > 1:
            key = str(item[1])
            if key not in expanded:
                expanded.add(key)
                for owner, members in definitions:
                    if str(owner) == key or (isinstance(owner, list) and owner and (owner[0] == 'party')):
                        todo.append(members)
        elif name == 'employees_of' and len(item) > 1:
            if contains(item[1], 'affiliates_of'):
                tags.add('controlled_employees')
            else:
                tags.add('recipient_employees')
        elif name == 'internal_personnel_of':
            tags.add('recipient_employees')
        elif name == 'independent_contractors_of':
            tags.add('contractors')
        elif name == 'consultants_of':
            tags.add('consultants')
        elif name == 'agents_of':
            tags.add('agents')
        elif name in ('professional_advisors_of', 'legal_advisors_of', 'financial_advisors_of', 'accountants_of', 'lenders_of'):
            tags.add('professional_advisers')
        elif name == 'third_parties':
            tags.add('third_parties')
        i = 1
        while i < len(item):
            if isinstance(item[i], list):
                todo.append(item[i])
            i += 1
    return tags

def disclosure_answer(task, entries):
    definitions = []
    definition_roots = []
    permissions = []
    prohibitions = []
    relevant = []
    absence = []
    for term, root in entries:
        if term[0] == 'define_representative' and len(term) == 3:
            definitions.append((term[1], term[2]))
            definition_roots.append(root)
        if term[0] in ('complete_source_no_disclosure_permission', 'complete_source_rule_absence'):
            absence.append(root)
    for term, root in entries:
        if term[0] not in ('permission', 'prohibition') or len(term) < 3:
            continue
        action = term[2]
        if not isinstance(action, list) or len(action) != 3 or action[0] != 'disclose' or (not has_tag(action[1], 'confidential_information')):
            continue
        relevant.append(root)
        item = (root, role_tags(action[2], definitions), action[2])
        if term[0] == 'permission':
            permissions.append(item)
        else:
            prohibitions.append(item)
    wanted = {'employees_of'} if task == 'nda-5' else {'third_parties', 'consultants_of', 'agents_of', 'independent_contractors_of', 'legal_advisors_of', 'financial_advisors_of', 'professional_advisors_of', 'accountants_of'}
    for root, tags, recipient in permissions:
        if tags.intersection(wanted):
            used = [root]
            if has_tag(recipient, 'representatives_of'):
                used.extend(definition_roots)
            return {'handled': True, 'answer': 'Entailment', 'used_nodes': unique(used)}
    for root, tags, recipient in prohibitions:
        if has_tag(recipient, 'outsiders_to'):
            continue
        if tags.intersection(wanted):
            return {'handled': True, 'answer': 'Contradiction', 'used_nodes': [root]}
    if relevant or absence:
        return {'handled': True, 'answer': 'NotMentioned', 'used_nodes': unique(relevant + definition_roots + absence)}
    return {'handled': False, 'answer': None, 'used_nodes': []}

def all_subterms(value):
    out = []
    todo = [value]
    while todo:
        item = todo.pop()
        if isinstance(item, list) and item:
            out.append(item)
            i = 1
            while i < len(item):
                if isinstance(item[i], list):
                    todo.append(item[i])
                i += 1
    return out

def contains(value, name):
    for item in all_subterms(value):
        if item[0] == name:
            return True
    return False

def atoms_dec_subterms(value):
    out=[]
    todo=[value]
    while todo:
        item=todo.pop()
        if isinstance(item,list) and item:
            out.append(item)
            i=1
            while i<len(item):
                if isinstance(item[i],list):
                    todo.append(item[i])
                i+=1
    return out

def atoms_dec_has(value,name):
    for item in atoms_dec_subterms(value):
        if item[0]==name:
            return True
    return False

def atoms_dec_unique(values):
    out=[]
    for value in values:
        if value not in out:
            out.append(value)
    return out

def atoms_dec_entries(premises):
    nodes=premises.get('nodes',[])
    roots=premises.get('roots',[])
    by_id={}
    for node in nodes:
        if isinstance(node,dict):
            by_id[node.get('id')]=node
    out=[]
    for root in roots:
        todo=[root]
        seen=set()
        while todo:
            node_id=todo.pop()
            if node_id in seen or node_id not in by_id:
                continue
            seen.add(node_id)
            node=by_id[node_id]
            for term in atoms_dec_subterms(node.get('term')):
                out.append((term,root))
            for child in node.get('child_ids',[]):
                todo.append(child)
    return out

def atoms_dec_roles(value):
    tags=set()
    for item in atoms_dec_subterms(value):
        name=item[0]
        if name in ('employees_of','internal_personnel_of'):
            tags.add('employees')
            if len(item)>1 and atoms_dec_has(item[1],'controlled_entities_of'):
                tags.add('controlled_employees')
            else:
                tags.add('recipient_employees')
        elif name in ('independent_contractors_of','consultants_of','agents_of','professional_advisors_of','legal_advisors_of','financial_advisors_of','accountants_of','lenders_of'):
            tags.add('professionals')
        elif name=='third_parties':
            tags.add('third_parties')
    return tags

def atoms_dec_full_material(action):
    for item in atoms_dec_subterms(action):
        if item[0]=='source_scoped_disposal_material' and len(item)>1 and item[1] in ('confidential_information_and_copies','information_copies_and_derivatives','all_source_materials'):
            return True
        if item[0]=='information_bundle' and atoms_dec_has(item,'confidential_information') and atoms_dec_has(item,'copies_of'):
            return True
    return False

def d_subterms(value):
    out=[]
    todo=[value]
    while todo:
        item=todo.pop()
        if isinstance(item,list) and item:
            out.append(item)
            i=1
            while i<len(item):
                if isinstance(item[i],list):
                    todo.append(item[i])
                i+=1
    return out

def d_has(value,name):
    for item in d_subterms(value):
        if item[0]==name:
            return True
    return False

def d_unique(values):
    out=[]
    for value in values:
        if value not in out:
            out.append(value)
    return out

def d_entries(premises):
    nodes=premises.get('nodes',[])
    roots=premises.get('roots',[])
    by_id={}
    for node in nodes:
        if isinstance(node,dict):
            by_id[node.get('id')]=node
    out=[]
    for root in roots:
        todo=[root]
        seen=set()
        while todo:
            node_id=todo.pop()
            if node_id in seen or node_id not in by_id:
                continue
            seen.add(node_id)
            node=by_id[node_id]
            term=node.get('term')
            if isinstance(term,list) and term:
                out.append([term,root])
            for child in node.get('child_ids',[]):
                todo.append(child)
    return out

def d_role_tags(value,definitions):
    tags=set()
    todo=[value]
    expanded=set()
    while todo:
        item=todo.pop()
        if not isinstance(item,list) or not item:
            continue
        name=item[0]
        if name=='representatives_of' and len(item)>1:
            key=str(item[1])
            if key not in expanded:
                expanded.add(key)
                for owner,members in definitions:
                    if str(owner)==key or (isinstance(owner,list) and owner and owner[0]=='party'):
                        todo.append(members)
            continue
        if name in ('employees_of','internal_personnel_of'):
            if len(item)>1 and (d_has(item[1],'controlled_entities_of') or d_has(item[1],'affiliates_of')):
                tags.add('controlled_employees')
            else:
                tags.add('employees')
        elif name in ('consultants_of','agents_of','independent_contractors_of','professional_advisors_of','legal_advisors_of','financial_advisors_of','accountants_of','lenders_of'):
            tags.add('professionals')
        elif name=='third_parties':
            tags.add('third_parties')
        i=1
        while i<len(item):
            if isinstance(item[i],list):
                todo.append(item[i])
            i+=1
    return tags

def d_endpoint_trigger(value):
    names=('agreement_termination','project_termination','relationship_termination','service_termination','relationship_nonformation_deadline','purpose_completion')
    for item in d_subterms(value):
        if item[0] in names:
            return True
        if item[0] in ('source_local_trigger','acquired_trigger_v3') and len(item)>1:
            kind=str(item[1])
            if 'agreement_end' in kind or 'project_end' in kind or 'relationship_end' in kind or 'service_end' in kind or 'nonformation' in kind or 'affiliate_exit' in kind:
                return True
    return False

def d_full_return_only(action):
    if not d_has(action,'return_to') or d_has(action,'destroy'):
        return False
    for item in d_subterms(action):
        if item[0]=='acquired_material_v3' and len(item)>1 and item[1] in ('all_source_stated_materials','confidential_information_and_copies','information_copies_and_derivatives'):
            return True
        if item[0]=='source_scoped_disposal_material' and len(item)>1 and item[1] in ('all_source_materials','confidential_information_and_copies','information_copies_and_derivatives'):
            return True
        if item[0]=='information_bundle' and d_has(item,'confidential_information') and d_has(item,'copies_of'):
            return True
    return False
