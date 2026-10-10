"""FastAPI control plane.

POST /sessions                 start a build session (session id = LangGraph thread_id)
POST /sessions/{id}/approval   answer a needs-approval card from the chat pane
GET  /branding                 tenant branding for the shell (defaults if unavailable)
GET  /healthz
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from langgraph.types import Command
from pydantic import BaseModel

from app.config import get_settings
from app.data_classes import SessionDataClasses, project_classes_for
from app.governance import AgentAuthorityClient, Governance, GovernanceUnavailable
from app.harness.context import RunContext
from app.harness.graph import Workers, build_graph, make_checkpointer

app = FastAPI(title="Governed AI App Builder control plane")

_checkpointer = make_checkpointer("")  # replaced at startup in deployed environments
_sessions: dict[str, RunContext] = {}


def get_governance() -> Governance:
    s = get_settings()
    return AgentAuthorityClient(s.authority_url, s.authority_ingest_key, s.authority_timeout_s)


def get_workers() -> Workers:
    raise HTTPException(503, "workers not configured: wire the gateway and sandbox clients")


def current_user() -> str:
    # Entra token validation goes here (app/auth.py, next step). Until then the
    # endpoint refuses to run outside dev.
    if get_settings().environment != "dev":
        raise HTTPException(401, "Entra sign-in not wired yet")
    return "dev-user"


class StartSession(BaseModel):
    project: str
    request: str
    agent_id: str = "app-builder"
    project_classes: list[str] = []


class Approval(BaseModel):
    approved: bool


def _run(graph, payload: Any, thread_id: str) -> dict:
    config = {"configurable": {"thread_id": thread_id}}
    try:
        state = graph.invoke(payload, config)
    except GovernanceUnavailable as exc:
        # Fail closed: nothing ran past the failed check. The chat pane shows this and retries.
        return {"sessionId": thread_id, "status": "paused", "reason": "governance unreachable",
                "detail": str(exc)}
    pending = graph.get_state(config).interrupts
    if pending:
        return {"sessionId": thread_id, "status": "needs_approval",
                "approval": pending[0].value}
    return {"sessionId": thread_id, "status": state.get("status"), "eval": state.get("eval"),
            "learnedSkill": state.get("learned_skill")}


@app.post("/sessions")
def start_session(body: StartSession, user: str = Depends(current_user),
                  gov: Governance = Depends(get_governance),
                  workers: Workers = Depends(get_workers)) -> dict:
    session_id = str(uuid.uuid4())
    ctx = RunContext(session_id, body.agent_id, user,
                     SessionDataClasses(project_classes_for(body.project, frozenset(body.project_classes))),
                     gov)
    _sessions[session_id] = ctx
    return _run(build_graph(ctx, workers, _checkpointer), {"request": body.request, "attempts": 0},
                session_id)


@app.post("/sessions/{session_id}/approval")
def answer_approval(session_id: str, body: Approval, user: str = Depends(current_user),
                    workers: Workers = Depends(get_workers)) -> dict:
    ctx = _sessions.get(session_id)
    if ctx is None:
        raise HTTPException(404, "unknown session")
    graph = build_graph(ctx, workers, _checkpointer)
    # The approver is the signed-in user, never a value from the request body.
    return _run(graph, Command(resume={"approved": body.approved, "by": user}), session_id)


@app.get("/branding")
def branding(gov: Governance = Depends(get_governance)) -> dict:
    return gov.branding() or {"source": "defaults"}


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "environment": get_settings().environment}
