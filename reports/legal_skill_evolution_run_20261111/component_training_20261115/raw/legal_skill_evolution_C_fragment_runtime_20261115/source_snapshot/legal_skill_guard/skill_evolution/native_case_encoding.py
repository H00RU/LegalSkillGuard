"""The shared author-native case encoding used by current generic readers.

Statutory givens describe explicit premises from the case, never the target
answer. Roles/types come from the same declarations as schema and execution.
"""
from .sara_statute_kernel import GIVENS

EVENT_ENCODING = 'Shared factual encoding from the author statute program:\nservice_(event), agent_(service,worker), patient_(service,employer).\npayment_(event), agent_(payment,payer), patient_(payment,payee),\npurpose_(payment,service_event), amount_(payment,amount).\npurpose_(service,"domestic service"|"agricultural labor") is a stated service kind.\nmarriage_(event) has an agent_ fact for EACH spouse.\ndeath_(event) has agent_(event,deceased), start_(event,actual_death_date).\nenrollment_(event) has agent_(event,student), patient_(event,institution).\nattending_classes_(event) has agent_(event,student), location_(event,institution).\neducational_institution_(event) has agent_(event,institution).\nincome_(event) has agent_(event,recipient), amount_(event,amount).\nstart_/end_ describe the dates/period of that SAME event, not arbitrary dates\nbelonging to a different event. A stated annual income can be represented over\nits stated calendar year with canonical year bounds; this does not invent the\ndate of an instantaneous payment. Never allocate a cross-year payment or give\nit a payment date copied from a service period without support.\n'

STATUTORY_ENCODING = '\nExplicit source-stated intermediate legal givens, with ordered arguments:\n' + '\n'.join(name + '(' + ','.join(arg['role'] + ':' + arg['type'] for arg in fields) + ')' for name, fields in GIVENS.items()) + '\nKeep source polarity and taxpayer/beneficiary direction. A151(d) statement is not automatically a151(b)/(c) fact. Never assert the target predicate or infer unstated ages, deaths or relationships. This is shared infrastructure, not learned legal knowledge.'

FACTUAL_ENCODING = EVENT_ENCODING + STATUTORY_ENCODING
