"""Complexity router: decides how much model a step deserves.

The harness scores each step and asks for a preference (cost, balanced or quality).
It never names a model. Agent Authority's /route turns the preference into a model from
the tenant's permitted set, applying data classes and budgets, and the LiteLLM gateway
executes it. So a complexity hint can raise quality but can never reach a model the
tenant hasn't approved, or send client data to an external model.

Escalation: when the judge fails a step, the next attempt goes one tier up.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

TIERS = ("cost", "balanced", "quality")

_HARD_SIGNALS = re.compile(
    r"\b(auth|oauth|entra|permission|migration|schema|concurren|transaction|payment|"
    r"reconcil|encrypt|security|regulat|audit|multi-?tenant|performance|race)\w*",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RouteHint:
    preference: str  # one of TIERS; sent to the gateway as routing metadata
    score: float  # 0..1, kept for evals so routing quality can be measured
    reasons: tuple[str, ...]


def score_step(request: str, files_touched: int = 0, prior_failures: int = 0) -> RouteHint:
    reasons: list[str] = []
    score = 0.0

    words = len(request.split())
    if words > 150:
        score += 0.25
        reasons.append("long request")
    elif words > 50:
        score += 0.1

    hard = sorted({m.group(0).lower() for m in _HARD_SIGNALS.finditer(request)})
    if hard:
        score += min(0.4, 0.15 * len(hard))
        reasons.append("hard topics: " + ", ".join(hard[:4]))

    if files_touched > 8:
        score += 0.25
        reasons.append(f"{files_touched} files")
    elif files_touched > 3:
        score += 0.1

    score = min(score, 1.0)
    tier = 0 if score < 0.25 else 1 if score < 0.55 else 2

    if prior_failures:
        tier = min(tier + prior_failures, len(TIERS) - 1)
        reasons.append(f"escalated after {prior_failures} failed attempt(s)")

    return RouteHint(TIERS[tier], round(score, 2), tuple(reasons))


def gateway_metadata(hint: RouteHint, data_classes: frozenset[str], session_id: str,
                     agent_id: str) -> dict:
    """Metadata for each LiteLLM call. Mirrors Agent Authority's gateway_metadata()."""
    return {
        "metadata": {
            "preference": hint.preference,
            "data_classes": sorted(data_classes),
            "session_id": session_id,
            "agent_id": agent_id,
        }
    }
