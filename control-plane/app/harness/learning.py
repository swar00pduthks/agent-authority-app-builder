"""Governed self-learning: the harness proposes skills, a human approves them.

After a build that passes its checks and the judge with room to spare, the harness
distils what worked into a reusable skill (when to use it, and the steps). It does not
start using it. The skill is registered in Agent Authority's catalog, where it waits as
pending until a tenant admin approves it; nobody approves their own. Every use of a
skill goes through the policy check, so a pending, blocked or changed skill can't run.

Skills are versioned by content hash: editing a skill makes it a new version that needs
a new approval. Skills are tenant-scoped and hold steps, never customer data.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

from app.governance import Action, Governance, Verdict
from app.harness.judge import EvalResult

LEARN_THRESHOLD = 0.85  # higher than the pass bar: only clearly good runs teach


@dataclass(frozen=True)
class SkillProposal:
    name: str
    when_to_use: str
    steps: tuple[str, ...]
    source_session: str

    @property
    def digest(self) -> str:
        body = json.dumps({"name": self.name, "when": self.when_to_use, "steps": self.steps},
                          sort_keys=True).encode()
        return hashlib.sha256(body).hexdigest()[:16]

    @property
    def skill_id(self) -> str:
        return f"{self.name}@{self.digest}"


def should_learn(result: EvalResult) -> bool:
    return result.passed and result.score >= LEARN_THRESHOLD


def propose(governance: Governance, proposal: SkillProposal, owner: str) -> str:
    """Register as pending. Agent Authority holds the lifecycle; we never mark it approved."""
    entry = {
        **asdict(proposal),
        "steps": list(proposal.steps),
        "owner": owner,
        "version": proposal.digest,
        "origin": "learned",
        "risk": {"changesState": False, "irreversible": False, "dataClasses": []},
    }
    governance.register_catalog("skill", proposal.skill_id, entry)
    return proposal.skill_id


def usable_skills(governance: Governance, candidates: list[SkillProposal], session_id: str,
                  agent_id: str, person: str, data_classes: frozenset[str]) -> list[SkillProposal]:
    """Only skills the policy check allows outright are put in the agent's context."""
    allowed = []
    for skill in candidates:
        decision = governance.check(Action(session_id, agent_id, "use_skill", skill.skill_id,
                                           person, data_classes))
        if decision.verdict is Verdict.ALLOW:
            allowed.append(skill)
    return allowed
