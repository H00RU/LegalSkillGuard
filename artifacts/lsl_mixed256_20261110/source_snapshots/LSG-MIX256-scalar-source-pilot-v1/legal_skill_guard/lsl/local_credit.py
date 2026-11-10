"""M1 cross-completion local credit and exact same-information controls.

Only independently scored TRAIN losses/execution signatures enter this code.
Unknown/unexecutable cells must be masked by the native adapter, never encoded
as legal negatives. Native task/structure/evidence training is separate.
"""
import torch
from torch.nn import functional as F


def preference(loss_table,*,independently_fixed=False,exhaustive=False):
    """Rows are common completions, columns are the same two local choices."""
    values=torch.as_tensor(loss_table,dtype=torch.float64)
    if values.ndim!=2 or values.shape[1]!=2 or not len(values) or not torch.isfinite(values).all():raise ValueError('Invalid independent native loss table')
    if len(values)<2 and not (independently_fixed or exhaustive):
        return {'status':'insufficient_common_contexts','weight':0.,'preferred':None,'minimum':None,'maximum':None}
    difference=values[:,1]-values[:,0];lower=float(difference.min());upper=float(difference.max())
    if lower>0:return {'status':'stable','weight':lower,'preferred':0,'minimum':lower,'maximum':upper}
    if upper<0:return {'status':'stable','weight':-upper,'preferred':1,'minimum':lower,'maximum':upper}
    status='conflict' if lower<0<upper else 'zero_or_context_occluded'
    return {'status':status,'weight':0.,'preferred':None,'minimum':lower,'maximum':upper}


def robust_loss(local_log_scores,table,**kwargs):
    decision=preference(table,**kwargs)
    if decision['preferred'] is None:return local_log_scores.sum()*0,decision
    good=decision['preferred'];bad=1-good
    return decision['weight']*F.softplus(local_log_scores[bad]-local_log_scores[good]),decision


def weak_loss(mode,log_scores,losses,execution_vectors=None):
    """Normalized candidate mass; all controls see the same execution table.

    ExecutionFilter uses execution-vector majority centrality among successful
    candidates, following the cited filtering approach, then retains MML mass.
    It does not treat the majority as an independent semantic oracle.
    """
    errors=torch.as_tensor(losses,device=log_scores.device)
    positive=errors==0
    if not bool(positive.any()):return log_scores.sum()*0,{'status':'no_answer_consistent_candidate','retained':[]}
    if mode=='hard_em':
        index=torch.where(positive,log_scores.detach(),torch.full_like(log_scores,-torch.inf)).argmax()
        return -F.log_softmax(log_scores,0)[index],{'status':'updated','retained':[int(index)]}
    if mode=='execution_filter':
        if execution_vectors is None:raise ValueError('Same execution vectors required for filtering control')
        signatures=[tuple(x) for x in execution_vectors]
        success=[i for i in range(len(signatures)) if bool(positive[i])]
        # Majority/medoid center, ties retain all equally central candidates.
        distances={i:sum(sum(a!=b for a,b in zip(signatures[i],signatures[j])) for j in success) for i in success}
        best=min(distances.values());positive=torch.tensor([i in distances and distances[i]==best for i in range(len(signatures))],device=log_scores.device)
    elif mode!='mml':raise ValueError(mode)
    loss=torch.logsumexp(log_scores,0)-torch.logsumexp(log_scores[positive],0)
    return loss,{'status':'updated','retained':positive.nonzero().flatten().tolist()}


def prior_loss(local_scores,reference_scores):
    reference=F.softmax(reference_scores.detach(),-1)
    return F.kl_div(F.log_softmax(local_scores,-1),reference,reduction='sum')
