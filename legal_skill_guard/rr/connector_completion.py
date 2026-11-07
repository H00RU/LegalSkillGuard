"""A selected connector program evaluated in each source-completion world.

The connector hypothesis pool is not a semantic completion space. This query
exists only after a concrete executable graph has been selected; source scope,
residual observations and the completion proof remain independent obligations.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass


@dataclass(frozen=True)
class ConnectorQuery:
    graph: dict
    projection: dict

    def __rr_state__(self):
        return {"kind": "selected_connector_query", "graph": self.graph,
                "projection": self.projection}

    def execute(self, env):
        from .coverage import Unsupported
        from .engine import connector_output
        from .interfaces import Connector, InterfaceError
        try:
            # Allowances are consumable within a world, never across worlds.
            slots = deepcopy(env)
            value = Connector(self.graph).execute(slots)
            answer = connector_output(value, self.projection, slots, exact=True)
            state = {name: value.__rr_state__() for name, value in slots.items()
                     if hasattr(value, '__rr_state__')}
            return {'answer': answer, 'execution_state': state}
        except (ValueError, TypeError, KeyError, InterfaceError) as exc:
            raise Unsupported("Selected connector completion failed: " + str(exc)) from exc

    def evaluate(self, env):
        return self.execute(env)['answer']
