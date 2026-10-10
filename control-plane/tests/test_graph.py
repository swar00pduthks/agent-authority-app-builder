from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.governance import GovernanceUnavailable, Verdict
from app.harness.graph import Workers, build_graph
from app.harness.judge import CheckResult
from app.harness.learning import SkillProposal

from conftest import FakeGovernance


def workers(check_results=None, judge_scores=None, written=None, calls=None):
    written = written if written is not None else {}
    calls = calls if calls is not None else []
    results = list(check_results or [[CheckResult("tests", True)]])

    def generate(request, preference, meta):
        calls.append(preference)
        return {"files": {"src/App.tsx": "export default () => null"}, "diff": "+app"}

    def run_checks():
        return results.pop(0) if len(results) > 1 else results[0]

    return Workers(
        generate=generate,
        write_file=lambda path, content: written.__setitem__(path, content),
        run_checks=run_checks,
        judge=(lambda r, d, rubric: judge_scores) if judge_scores is not None else None,
        distil=lambda r, d, s: SkillProposal("react-form", "simple data-entry forms", ("scaffold", "validate"), s),
    )


def run(graph, payload, thread="sess-1"):
    cfg = {"configurable": {"thread_id": thread}}
    state = graph.invoke(payload, cfg)
    return state, graph.get_state(cfg)


def test_happy_path_writes_checks_and_proposes_skill(make_ctx):
    gov = FakeGovernance()
    written = {}
    g = build_graph(make_ctx(gov), workers(judge_scores={"meets_request": 0.95, "safe_data_handling": 0.9,
                                                          "maintainable": 0.9}, written=written),
                    InMemorySaver())
    state, _ = run(g, {"request": "a form to log client calls", "attempts": 0})
    assert state["status"] == "passed"
    assert written == {"src/App.tsx": "export default () => null"}
    assert state["learned_skill"].startswith("react-form@")
    assert gov.catalog[("skill", state["learned_skill"])]["origin"] == "learned"
    assert [c.kind for c in gov.checks] == ["call_tool", "call_tool"]


def test_denied_tool_stops_without_running(make_ctx):
    gov = FakeGovernance({("call_tool", "write_file"): Verdict.DENY})
    written = {}
    g = build_graph(make_ctx(gov), workers(written=written), InMemorySaver())
    state, _ = run(g, {"request": "x", "attempts": 0})
    assert state["status"] == "blocked"
    assert written == {}


def test_needs_approval_pauses_then_resumes_with_approver(make_ctx):
    gov = FakeGovernance({("call_tool", "run_checks"): Verdict.REVIEW})
    g = build_graph(make_ctx(gov), workers(), InMemorySaver())
    _, snap = run(g, {"request": "x", "attempts": 0})
    assert snap.interrupts and snap.interrupts[0].value["tool"] == "run_checks"

    state, snap = run(g, Command(resume={"approved": True, "by": "bob"}))
    assert not snap.interrupts
    assert state["status"] == "passed"
    approved = [o for o in state["tool_outcomes"] if o["tool"] == "run_checks"][0]
    assert approved["approved_by"] == "bob"


def test_rejected_approval_blocks(make_ctx):
    gov = FakeGovernance({("call_tool", "run_checks"): Verdict.REVIEW})
    g = build_graph(make_ctx(gov), workers(), InMemorySaver())
    run(g, {"request": "x", "attempts": 0})
    state, _ = run(g, Command(resume={"approved": False, "by": "bob"}))
    assert state["status"] == "blocked"


def test_fail_closed_when_authority_unreachable(make_ctx):
    gov = FakeGovernance(down=True)
    written = {}
    g = build_graph(make_ctx(gov), workers(written=written), InMemorySaver())
    try:
        run(g, {"request": "x", "attempts": 0})
        raise AssertionError("expected GovernanceUnavailable")
    except GovernanceUnavailable:
        pass
    assert written == {}


def test_failed_checks_retry_with_escalated_model_then_give_up(make_ctx):
    calls = []
    failing = [[CheckResult("tests", False, "2 failed")]]
    g = build_graph(make_ctx(FakeGovernance()), workers(check_results=failing, calls=calls), InMemorySaver())
    state, _ = run(g, {"request": "a form", "attempts": 0})
    assert state["status"] == "failed"
    assert calls == ["cost", "balanced", "quality"]


def test_weak_judge_score_does_not_teach(make_ctx):
    gov = FakeGovernance()
    g = build_graph(make_ctx(gov), workers(judge_scores={"meets_request": 0.75, "safe_data_handling": 0.8,
                                                          "maintainable": 0.8}), InMemorySaver())
    state, _ = run(g, {"request": "x", "attempts": 0})
    assert state["status"] == "passed"
    assert state["learned_skill"] is None
    assert not [k for k in gov.catalog if k[0] == "skill"]
