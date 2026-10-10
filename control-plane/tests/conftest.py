from __future__ import annotations

import pytest

from app.data_classes import SessionDataClasses
from app.governance import Action, Decision, GovernanceUnavailable, Verdict
from app.harness.context import RunContext


class FakeGovernance:
    """Answers checks from a table: {(kind, resource): Verdict}. Default allow."""

    def __init__(self, rules=None, down=False):
        self.rules = rules or {}
        self.down = down
        self.checks: list[Action] = []
        self.catalog: dict[tuple[str, str], dict] = {}
        self.cards: dict[str, dict] = {}

    def check(self, action: Action) -> Decision:
        if self.down:
            raise GovernanceUnavailable("connection refused")
        self.checks.append(action)
        verdict = self.rules.get((action.kind, action.resource), Verdict.ALLOW)
        return Decision(verdict, reasons=("test rule",))

    def register_catalog(self, kind, item_id, entry):
        self.catalog[(kind, item_id)] = entry

    def register_card(self, agent_id, card):
        self.cards[agent_id] = card

    def branding(self):
        return None


@pytest.fixture
def gov():
    return FakeGovernance()


@pytest.fixture
def make_ctx():
    def _make(governance, project_classes=frozenset()):
        return RunContext("sess-1", "app-builder", "alice", SessionDataClasses(frozenset(project_classes)),
                          governance)
    return _make
