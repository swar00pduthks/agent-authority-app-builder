"""Built-in judgement: deterministic checks first, then a rubric judge.

1. Deterministic checks (tests, lint, type check, build) are facts. Any failure fails
   the step, and the judge model isn't asked.
2. Only if they pass, a judge model scores the result against a rubric. Its scores are
   opinions, so they gate retries and learning but never override a failed test.

Every result is returned as an EvalResult and recorded with the session, so Agent
Authority can compare agent versions on quality, not just failure rate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

RUBRIC: dict[str, str] = {
    "meets_request": "Does the change do what the builder asked, and nothing they didn't?",
    "safe_data_handling": "Does it avoid logging, exporting or hard-coding sensitive data?",
    "maintainable": "Is it plain React/Python a bank's engineers could own without us?",
}

PASS_THRESHOLD = 0.7

# A judge takes (request, diff, rubric) and returns a 0..1 score per rubric key.
JudgeFn = Callable[[str, str, dict[str, str]], dict[str, float]]


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class EvalResult:
    passed: bool
    checks: list[CheckResult]
    scores: dict[str, float] = field(default_factory=dict)
    reason: str = ""

    @property
    def score(self) -> float:
        return min(self.scores.values()) if self.scores else 0.0

    def as_facet(self) -> dict:
        """Shape recorded on the session's lineage for version comparison."""
        return {
            "passed": self.passed,
            "checks": {c.name: c.passed for c in self.checks},
            "scores": self.scores,
            "minScore": self.score,
            "reason": self.reason,
        }


def evaluate(request: str, diff: str, checks: list[CheckResult], judge: JudgeFn | None) -> EvalResult:
    failed = [c for c in checks if not c.passed]
    if failed:
        return EvalResult(False, checks, reason="failed checks: " + ", ".join(c.name for c in failed))

    if judge is None:
        return EvalResult(True, checks, reason="deterministic checks passed; no judge configured")

    raw = judge(request, diff, RUBRIC)
    # Missing or out-of-range scores count as 0: a judge that doesn't answer doesn't pass work.
    scores = {k: max(0.0, min(1.0, float(raw.get(k, 0.0)))) for k in RUBRIC}
    weakest = min(scores, key=scores.get)
    if scores[weakest] < PASS_THRESHOLD:
        return EvalResult(False, checks, scores, reason=f"judge: {weakest} scored {scores[weakest]:.2f}")
    return EvalResult(True, checks, scores, reason="checks and judge passed")
