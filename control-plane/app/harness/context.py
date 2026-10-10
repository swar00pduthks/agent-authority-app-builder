from __future__ import annotations

from dataclasses import dataclass

from app.data_classes import SessionDataClasses
from app.governance import Governance


@dataclass
class RunContext:
    """What every node needs to act on someone's behalf, governed."""

    session_id: str  # also the LangGraph thread_id: pause and resume stay one session
    agent_id: str
    person: str  # Entra object id of the builder
    data: SessionDataClasses
    governance: Governance
