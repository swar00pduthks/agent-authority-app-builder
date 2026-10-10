"""Policy check before every tool call, with LangGraph's interrupt() for approvals.

This is the app builder's shim for Agent Authority's governed_tools(): the same
contract (check before each tool; needs-approval becomes interrupt(); the person who
resumes is recorded). Swap the body for the SDK's governed_tools() once its version is
pinned; callers don't change.

Note on interrupt(): when a graph resumes, LangGraph re-runs the interrupted node from
the top. The check runs again and returns review again, and this time interrupt()
returns the resume value instead of pausing. That is why there is no extra state here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from langgraph.types import interrupt

from app.governance import Action, Verdict
from app.harness.context import RunContext


@dataclass
class ToolOutcome:
    tool: str
    ran: bool
    result: Any = None
    verdict: str = ""
    approved_by: str | None = None
    reasons: tuple[str, ...] = ()


def governed_call(ctx: RunContext, tool: str, fn: Callable[..., Any], /, **kwargs: Any) -> ToolOutcome:
    # GovernanceUnavailable is deliberately not caught: the run stops (fail closed)
    # and the API marks the session "paused: governance unreachable".
    decision = ctx.governance.check(Action(
        session_id=ctx.session_id,
        agent_id=ctx.agent_id,
        kind="call_tool",
        resource=tool,
        person=ctx.person,
        data_classes=ctx.data.current,
        context={"args": sorted(kwargs)},  # argument names only; values may be sensitive
    ))

    if decision.verdict is Verdict.DENY:
        return ToolOutcome(tool, ran=False, verdict="deny", reasons=decision.reasons)

    approved_by = None
    if decision.verdict is Verdict.REVIEW:
        answer = interrupt({
            "type": "approval",
            "tool": tool,
            "reasons": list(decision.reasons),
            "policies": list(decision.policy_ids),
        })
        if not (isinstance(answer, dict) and answer.get("approved") and answer.get("by")):
            return ToolOutcome(tool, ran=False, verdict="rejected", reasons=decision.reasons)
        approved_by = str(answer["by"])

    return ToolOutcome(tool, ran=True, result=fn(**kwargs), verdict=decision.verdict.value,
                       approved_by=approved_by, reasons=decision.reasons)
