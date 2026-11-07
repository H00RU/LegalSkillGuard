"""Current-purpose dispatch over the preserved wire clients and physical ledger."""
from .client import ExecutorClient,TeacherClient
from .ledger import BudgetError


class MethodExecutor(ExecutorClient):
    def validate_scope(self,source,purpose,thinking):
        if self.ledger is None:raise BudgetError('Read-only client cannot generate')
        self.ledger._source(source)
        if self.ledger.PURPOSES.get(purpose,(None,None))[1]!='executor' or type(thinking) is not bool:
            raise BudgetError('Current executor purpose/profile mismatch')
        if purpose!='method_thinking_comparison' and thinking is not self.config['enable_thinking']:
            raise BudgetError('Thinking differs from the current configured profile')


class MethodTeacher(TeacherClient):
    summary_purpose='method_train_compile'
