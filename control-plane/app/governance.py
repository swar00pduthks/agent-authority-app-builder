"""The app builder's only door to Agent Authority.

Every call to Agent Authority goes through this module, so the contract lives in one
place (see docs/agent-authority-contract.md). Endpoints used here are the ones agreed
in Agent Authority's Joint architecture section:

    POST /api/authority/check                  policy decision before each action
    POST /api/authority/catalog/{kind}/{id}    register tools, MCP servers, skills, models
    PUT  /api/authority/agents/{id}/card       register a generated agent's A2A card
    GET  /api/authority/branding               tenant branding for the shell

The response shapes are parsed in `_parse_decision` and nowhere else; adjust them
there if the server's shape differs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

import httpx


class Verdict(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REVIEW = "review"  # needs a human approval before the action runs


@dataclass(frozen=True)
class Decision:
    verdict: Verdict
    reasons: tuple[str, ...] = ()
    policy_ids: tuple[str, ...] = ()


@dataclass
class Action:
    """One thing the agent wants to do, described for the policy check."""

    session_id: str
    agent_id: str
    kind: str  # "call_tool" | "call_model" | "export"
    resource: str  # tool name, model id or export target
    person: str  # Entra object id of the user the session acts for
    data_classes: frozenset[str] = frozenset()
    context: dict[str, Any] = field(default_factory=dict)


class GovernanceUnavailable(RuntimeError):
    """Agent Authority couldn't be reached or answered badly. Callers must fail closed."""


class Governance(Protocol):
    def check(self, action: Action) -> Decision: ...

    def register_catalog(self, kind: str, item_id: str, entry: dict[str, Any]) -> None: ...

    def register_card(self, agent_id: str, card: dict[str, Any]) -> None: ...

    def branding(self) -> dict[str, Any] | None: ...


def _parse_decision(body: dict[str, Any]) -> Decision:
    raw = str(body.get("decision", body.get("verdict", ""))).lower()
    mapping = {
        "allow": Verdict.ALLOW,
        "permit": Verdict.ALLOW,
        "deny": Verdict.DENY,
        "forbid": Verdict.DENY,
        "blocked": Verdict.DENY,
        "review": Verdict.REVIEW,
        "needs_approval": Verdict.REVIEW,
        "needs-approval": Verdict.REVIEW,
    }
    if raw not in mapping:
        # An answer we don't understand is not permission.
        raise GovernanceUnavailable(f"unrecognised policy decision: {raw!r}")
    return Decision(
        verdict=mapping[raw],
        reasons=tuple(body.get("reasons", ())),
        policy_ids=tuple(body.get("policies", body.get("policy_ids", ()))),
    )


class AgentAuthorityClient:
    """HTTP client for Agent Authority, authenticated with the control plane's ingest key."""

    def __init__(self, base_url: str, ingest_key: str, timeout_s: float = 5.0,
                 transport: httpx.BaseTransport | None = None) -> None:
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {ingest_key}"},
            timeout=timeout_s,
            transport=transport,
        )

    def check(self, action: Action) -> Decision:
        payload = {
            "sessionId": action.session_id,
            "agentId": action.agent_id,
            "action": action.kind,
            "resource": action.resource,
            "principal": action.person,
            "dataClasses": sorted(action.data_classes),
            "context": action.context,
        }
        try:
            resp = self._http.post("/api/authority/check", json=payload)
            resp.raise_for_status()
            return _parse_decision(resp.json())
        except (httpx.HTTPError, ValueError) as exc:
            raise GovernanceUnavailable(str(exc)) from exc

    def register_catalog(self, kind: str, item_id: str, entry: dict[str, Any]) -> None:
        try:
            self._http.post(f"/api/authority/catalog/{kind}/{item_id}", json=entry).raise_for_status()
        except httpx.HTTPError as exc:
            raise GovernanceUnavailable(str(exc)) from exc

    def register_card(self, agent_id: str, card: dict[str, Any]) -> None:
        try:
            self._http.put(f"/api/authority/agents/{agent_id}/card", json=card).raise_for_status()
        except httpx.HTTPError as exc:
            raise GovernanceUnavailable(str(exc)) from exc

    def branding(self) -> dict[str, Any] | None:
        """Branding is cosmetic: on any failure return None and let the shell use defaults."""
        try:
            resp = self._http.get("/api/authority/branding")
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, ValueError):
            return None
