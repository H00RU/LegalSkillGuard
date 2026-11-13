"""Frozen strong simple control, not source semantics or a learned C/U asset.

Uses only a single supplied native view. Native outputs and lexical negatives
are permitted here as a direct baseline, never treated as core source facts.
"""
PROGRAM = '''def apply(inputs,premises):
    text=inputs['source_text'].casefold()
    if inputs['task_id']=='Knowledge Definition-Answer':
        if re.search(r'after\\s+(?:reasonable|due|diligent|appropriate)\\s+inquir|reasonable\\s+investigation|after\\s+inquiry|should\\s+have\\s+known|would\\s+have\\s+known',text):
            return {'handled':True,'answer':'Constructive knowledge'}
        if 'actual knowledge' in text:
            return {'handled':True,'answer':'Actual knowledge'}
        return {'handled':False,'answer':None}
    if re.search(r'covid|pandemic|coronavirus',text):
        return {'handled':True,'answer':'Yes'}
    return {'handled':True,'answer':'No'}
'''
