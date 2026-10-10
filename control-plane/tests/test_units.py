import httpx
import pytest

from app.data_classes import DowngradeRefused, SessionDataClasses, project_classes_for
from app.export import SESSION_MARKER, GeneratedAgent, pr_body, register_export
from app.governance import AgentAuthorityClient, GovernanceUnavailable, Verdict, Action
from app.harness.judge import CheckResult, evaluate
from app.harness.learning import SkillProposal, usable_skills
from app.harness.router import gateway_metadata, score_step

from conftest import FakeGovernance


# --- router ---------------------------------------------------------------

def test_simple_request_routes_cheap():
    assert score_step("Add a title to the page").preference == "cost"


def test_hard_topics_route_to_quality():
    hint = score_step("Add Entra auth, a schema migration and audit logging for payment reconciliation",
                      files_touched=10)
    assert hint.preference == "quality"
    assert any("hard topics" in r for r in hint.reasons)


def test_escalation_caps_at_quality():
    assert score_step("tiny", prior_failures=5).preference == "quality"


def test_gateway_metadata_carries_data_classes():
    meta = gateway_metadata(score_step("x"), frozenset({"pii"}), "s", "a")["metadata"]
    assert meta["data_classes"] == ["pii"] and meta["preference"] == "cost"


# --- judge ----------------------------------------------------------------

def test_failed_check_fails_without_asking_judge():
    asked = []
    res = evaluate("r", "d", [CheckResult("tests", False)], lambda *a: asked.append(1) or {})
    assert not res.passed and asked == []


def test_missing_judge_scores_count_as_zero():
    res = evaluate("r", "d", [CheckResult("tests", True)], lambda *a: {"meets_request": 1.0})
    assert not res.passed


# --- data classes ---------------------------------------------------------

def test_data_classes_are_sticky_and_cannot_be_lowered():
    dc = SessionDataClasses(project_classes_for("kyc-onboarding", frozenset()))
    assert "client-data" in dc.current
    dc.absorb({"pii"})
    assert dc.current == {"client-data", "pii"}
    with pytest.raises(DowngradeRefused):
        dc.remove("pii")


# --- learning -------------------------------------------------------------

def test_only_allowed_skills_reach_the_agent():
    a = SkillProposal("a", "w", ("s",), "s1")
    b = SkillProposal("b", "w", ("s",), "s1")
    gov = FakeGovernance({("use_skill", b.skill_id): Verdict.REVIEW})
    assert usable_skills(gov, [a, b], "s", "ag", "p", frozenset()) == [a]


def test_editing_a_skill_changes_its_version():
    a = SkillProposal("a", "w", ("s",), "s1")
    assert a.skill_id != SkillProposal("a", "w", ("s", "extra"), "s1").skill_id


# --- export ---------------------------------------------------------------

def test_pr_marker_on_its_own_line():
    assert f"\n{SESSION_MARKER} run-123\n" in pr_body("Adds the form", "run-123")


def test_export_registers_card_and_tools():
    gov = FakeGovernance()
    agent = GeneratedAgent("ag-1", "Calls log", "d", "1.0.0", "team-ops", "alice", "medium", "ops",
                           "sess-1", "app", allowed_tools=("sql.read",))
    card = register_export(gov, agent, "https://apps.example/ag-1")
    params = card["capabilities"]["extensions"][0]["params"]
    assert params["builtBySession"] == "sess-1" and gov.cards["ag-1"] == card
    assert ("tool", "sql.read") in gov.catalog


# --- HTTP client fails closed --------------------------------------------

def _client(handler):
    return AgentAuthorityClient("http://aa", "k", transport=httpx.MockTransport(handler))


def _action():
    return Action("s", "a", "call_tool", "write_file", "p")


def test_client_parses_review():
    c = _client(lambda req: httpx.Response(200, json={"decision": "needs_approval", "reasons": ["prod"]}))
    assert c.check(_action()).verdict is Verdict.REVIEW


def test_client_unknown_decision_is_not_permission():
    c = _client(lambda req: httpx.Response(200, json={"decision": "maybe"}))
    with pytest.raises(GovernanceUnavailable):
        c.check(_action())


def test_client_server_error_fails_closed():
    c = _client(lambda req: httpx.Response(503))
    with pytest.raises(GovernanceUnavailable):
        c.check(_action())


def test_branding_falls_back_quietly():
    assert _client(lambda req: httpx.Response(500)).branding() is None
