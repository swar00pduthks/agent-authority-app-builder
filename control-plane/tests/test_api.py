from fastapi.testclient import TestClient

from app import main
from app.governance import Verdict

from conftest import FakeGovernance
from test_graph import workers


def client(gov):
    main.app.dependency_overrides[main.get_governance] = lambda: gov
    main.app.dependency_overrides[main.get_workers] = lambda: workers()
    return TestClient(main.app)


def test_session_pauses_when_governance_unreachable():
    r = client(FakeGovernance(down=True)).post("/sessions", json={"project": "ops", "request": "x"})
    assert r.json()["status"] == "paused" and r.json()["reason"] == "governance unreachable"


def test_approval_round_trip_records_signed_in_user():
    gov = FakeGovernance({("call_tool", "run_checks"): Verdict.REVIEW})
    c = client(gov)
    first = c.post("/sessions", json={"project": "ops", "request": "x"}).json()
    assert first["status"] == "needs_approval"
    done = c.post(f"/sessions/{first['sessionId']}/approval", json={"approved": True}).json()
    assert done["status"] == "passed"


def test_kyc_project_marks_checks_as_client_data():
    gov = FakeGovernance()
    client(gov).post("/sessions", json={"project": "kyc-review", "request": "x"})
    assert all("client-data" in a.data_classes for a in gov.checks)


def test_branding_defaults_when_unavailable():
    assert client(FakeGovernance()).get("/branding").json() == {"source": "defaults"}
