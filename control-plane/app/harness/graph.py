"""The build graph: route -> draft -> apply -> evaluate -> (learn | retry | stop).

  route     scores the step and picks a model preference (escalates after failures)
  draft     asks the model for the change, through the gateway with routing metadata
  apply     writes files and runs checks in the sandbox, each tool call policy-checked
  evaluate  deterministic checks, then the rubric judge
  learn     proposes a skill to the catalog when the run was clearly good

Draft and apply are separate nodes on purpose: an approval interrupt in apply re-runs
only apply on resume (idempotent file writes), never the model call in draft.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from app.harness.context import RunContext
from app.harness.governed import governed_call
from app.harness.judge import CheckResult, EvalResult, JudgeFn, evaluate
from app.harness.learning import SkillProposal, propose, should_learn
from app.harness.router import RouteHint, gateway_metadata, score_step

MAX_ATTEMPTS = 3


class BuildState(TypedDict, total=False):
    request: str
    attempts: int
    hint: dict
    draft: dict  # {"files": {path: content}, "diff": str}
    tool_outcomes: list[dict]
    checks: list[dict]
    eval: dict
    learned_skill: Optional[str]
    status: str  # running | passed | failed | blocked


@dataclass
class Workers:
    """Everything the graph calls out to. Real implementations talk to LiteLLM and the
    sandbox; tests pass fakes."""

    # (request, preference, gateway_metadata) -> {"files": {...}, "diff": "..."}
    generate: Callable[[str, str, dict], dict]
    write_file: Callable[..., Any]
    run_checks: Callable[[], list[CheckResult]]
    judge: Optional[JudgeFn] = None
    distil: Optional[Callable[[str, str, str], SkillProposal]] = None


def build_graph(ctx: RunContext, workers: Workers, checkpointer: Any):
    def route(state: BuildState) -> BuildState:
        files = len((state.get("draft") or {}).get("files", {}))
        hint = score_step(state["request"], files_touched=files,
                          prior_failures=state.get("attempts", 0))
        return {"hint": asdict(hint), "status": "running"}

    def draft(state: BuildState) -> BuildState:
        hint = state["hint"]
        meta = gateway_metadata(RouteHint(hint["preference"], hint["score"], tuple(hint["reasons"])),
                                ctx.data.current, ctx.session_id, ctx.agent_id)
        return {"draft": workers.generate(state["request"], hint["preference"], meta)}

    def apply(state: BuildState) -> BuildState:
        outcomes = []
        for path, content in state["draft"].get("files", {}).items():
            out = governed_call(ctx, "write_file", workers.write_file, path=path, content=content)
            outcomes.append(asdict(out))
            if not out.ran:
                return {"tool_outcomes": outcomes, "status": "blocked"}
        out = governed_call(ctx, "run_checks", workers.run_checks)
        outcomes.append({**asdict(out), "result": None})
        if not out.ran:
            return {"tool_outcomes": outcomes, "status": "blocked"}
        return {"tool_outcomes": outcomes, "checks": [asdict(c) for c in out.result]}

    def judge(state: BuildState) -> BuildState:
        checks = [CheckResult(**c) for c in state.get("checks", [])]
        result = evaluate(state["request"], state["draft"].get("diff", ""), checks, workers.judge)
        attempts = state.get("attempts", 0) + (0 if result.passed else 1)
        return {"eval": result.as_facet(), "attempts": attempts,
                "status": "passed" if result.passed else "running"}

    def learn(state: BuildState) -> BuildState:
        ev = state["eval"]
        result = EvalResult(ev["passed"], [], ev["scores"], ev["reason"])
        if workers.distil is None or not should_learn(result):
            return {"learned_skill": None}
        proposal = workers.distil(state["request"], state["draft"].get("diff", ""), ctx.session_id)
        return {"learned_skill": propose(ctx.governance, proposal, owner=ctx.person)}

    def after_apply(state: BuildState) -> str:
        return END if state.get("status") == "blocked" else "evaluate"

    def after_eval(state: BuildState) -> str:
        if state["status"] == "passed":
            return "learn"
        return "route" if state.get("attempts", 0) < MAX_ATTEMPTS else "give_up"

    def give_up(state: BuildState) -> BuildState:
        return {"status": "failed"}

    g = StateGraph(BuildState)
    for name, fn in [("route", route), ("draft", draft), ("apply", apply),
                     ("evaluate", judge), ("learn", learn), ("give_up", give_up)]:
        g.add_node(name, fn)
    g.add_edge(START, "route")
    g.add_edge("route", "draft")
    g.add_edge("draft", "apply")
    g.add_conditional_edges("apply", after_apply, ["evaluate", END])
    g.add_conditional_edges("evaluate", after_eval, ["learn", "route", "give_up"])
    g.add_edge("learn", END)
    g.add_edge("give_up", END)
    return g.compile(checkpointer=checkpointer)


def make_checkpointer(database_url: str):
    """Postgres in deployed environments (agreed with Agent Authority); memory otherwise."""
    if database_url:
        # Optional dependency (pip install ".[postgres]"). from_conn_string is a context
        # manager, so the app opens it once at startup and closes it on shutdown.
        from langgraph.checkpoint.postgres import PostgresSaver

        return PostgresSaver.from_conn_string(database_url)
    from langgraph.checkpoint.memory import InMemorySaver

    return InMemorySaver()
