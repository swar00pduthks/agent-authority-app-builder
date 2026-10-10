"""Export: the pull request that closes the chain of authority, and the agent card.

The PR carries the session marker so Agent Authority's merge webhook records the named
human who approved it. Each generated agent or app gets an A2A Agent Card with
Agent Authority's governance extension, signed with a Key Vault key (hardening phase)
and registered with PUT /api/authority/agents/{id}/card.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.governance import Governance

GOVERNANCE_EXTENSION = "https://github.com/swar00pduthks/agent-authority/spec/a2a-governance/v1"
SESSION_MARKER = "agent-authority-session:"


@dataclass(frozen=True)
class GeneratedAgent:
    agent_id: str
    name: str
    description: str
    version: str
    owner: str
    accountable_person: str
    risk_tier: str
    namespace: str
    built_by_session: str
    kind: str  # "app" | "agent"
    data_classes: tuple[str, ...] = ()
    allowed_models: tuple[str, ...] = ()
    allowed_tools: tuple[str, ...] = ()


def pr_body(summary: str, root_run_id: str) -> str:
    """The marker line must stay on its own line: the webhook parses it."""
    return f"{summary.rstrip()}\n\n{SESSION_MARKER} {root_run_id}\n"


def agent_card(agent: GeneratedAgent, url: str) -> dict:
    return {
        "name": agent.name,
        "description": agent.description,
        "url": url,
        "version": agent.version,
        "capabilities": {"extensions": [{
            "uri": GOVERNANCE_EXTENSION,
            "required": True,
            "params": {
                "owner": agent.owner,
                "accountablePerson": agent.accountable_person,
                "riskTier": agent.risk_tier,
                "dataClasses": list(agent.data_classes),
                "allowedModels": list(agent.allowed_models),
                "allowedTools": list(agent.allowed_tools),
                "namespace": agent.namespace,
                "builtBySession": agent.built_by_session,
                "kind": agent.kind,
            },
        }]},
    }


def register_export(governance: Governance, agent: GeneratedAgent, url: str) -> dict:
    """Register the card and the tools the agent ships with, as agreed for export."""
    card = agent_card(agent, url)
    governance.register_card(agent.agent_id, card)
    for tool in agent.allowed_tools:
        governance.register_catalog("tool", tool, {"owner": agent.owner, "shippedBy": agent.agent_id})
    return card
