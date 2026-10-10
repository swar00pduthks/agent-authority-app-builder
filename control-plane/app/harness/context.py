from __future__ import annotations

from dataclasses import dataclass, field

from app.data_classes import SessionDataClasses
from app.estate import Dataset
from app.governance import Governance


@dataclass
class RunContext:
    """What every node needs to act on someone's behalf, governed."""

    session_id: str  # also the LangGraph thread_id: pause and resume stay one session
    agent_id: str
    person: str  # Entra object id of the builder
    data: SessionDataClasses
    governance: Governance
    # Every dataset the session read through an approved connector. Feeds the app's
    # manifest at export, so declared inputs can't leave out what the agent really read.
    reads: list[Dataset] = field(default_factory=list)

    def record_read(self, dataset: Dataset) -> None:
        self.data.absorb(dataset.data_classes)
        self.reads.append(dataset)
