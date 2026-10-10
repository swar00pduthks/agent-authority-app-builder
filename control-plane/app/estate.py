"""The connected-apps estate: what every generated app reads, writes, calls and who can use it.

Every app the builder exports gets an AppManifest. Together the manifests are the data
for one estate-wide picture: data flow between apps, which app depends on which,
and who has access. The store of record is Agent Authority: the manifest
travels in the app's registered card and as OpenLineage inputs and outputs, so the
estate is one graph alongside the data pipelines, not a second database we keep.

Declared vs observed: the builder declares access and interfaces, but data inputs come
from the connectors the session actually used. A builder can't leave out a source the
agent read.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

SENSITIVE = {"client-data", "pii"}
BROAD_GROUPS = {"everyone", "all-users", "all-staff"}


@dataclass(frozen=True)
class Dataset:
    namespace: str  # OpenLineage namespace, e.g. "postgres://risk-db" or "app://calls-log"
    name: str
    data_classes: frozenset[str] = frozenset()
    connector: str = ""  # approved connector id it came through, if any


@dataclass(frozen=True)
class Interface:
    name: str
    kind: str  # "api" | "ui" | "event"


@dataclass(frozen=True)
class Dependency:
    app_id: str
    interface: str


@dataclass(frozen=True)
class AccessRule:
    entra_group: str  # Entra group object id or name
    role: str  # "user" | "viewer" | "admin"


class ManifestRejected(ValueError):
    pass


@dataclass
class AppManifest:
    app_id: str
    name: str
    owner: str
    accountable_person: str
    namespace: str
    environment: str
    inputs: list[Dataset] = field(default_factory=list)
    outputs: list[Dataset] = field(default_factory=list)
    exposes: list[Interface] = field(default_factory=list)
    depends_on: list[Dependency] = field(default_factory=list)
    access: list[AccessRule] = field(default_factory=list)

    @property
    def data_classes(self) -> frozenset[str]:
        out: set[str] = set()
        for d in self.inputs + self.outputs:
            out |= d.data_classes
        return frozenset(out)

    def validate(self) -> None:
        if not self.access:
            raise ManifestRejected("an app needs at least one Entra group with access")
        if self.data_classes & SENSITIVE:
            broad = [a.entra_group for a in self.access if a.entra_group.lower() in BROAD_GROUPS]
            if broad:
                raise ManifestRejected(f"apps with {sorted(self.data_classes & SENSITIVE)} "
                                       f"can't be open to {broad}")
        # Classification flows downstream: what an app writes carries what it read.
        upstream = frozenset().union(*(d.data_classes for d in self.inputs)) if self.inputs else frozenset()
        for out in self.outputs:
            missing = upstream - out.data_classes
            if missing:
                raise ManifestRejected(f"output {out.name} drops data classes {sorted(missing)}")

    def card_params(self) -> dict:
        """Extra params for the app's A2A card governance extension."""
        return {
            "environment": self.environment,
            "dataInputs": [_ds(d) for d in self.inputs],
            "dataOutputs": [_ds(d) for d in self.outputs],
            "exposes": [{"name": i.name, "kind": i.kind} for i in self.exposes],
            "dependsOn": [{"appId": d.app_id, "interface": d.interface} for d in self.depends_on],
            "access": [{"entraGroup": a.entra_group, "role": a.role} for a in self.access],
        }

    def openlineage_io(self) -> dict:
        """Inputs and outputs for the app's deploy run, so the estate is in the lineage graph."""
        return {
            "job": {"namespace": self.namespace, "name": self.app_id},
            "inputs": [{"namespace": d.namespace, "name": d.name} for d in self.inputs]
                      + [{"namespace": f"app://{d.app_id}", "name": d.interface} for d in self.depends_on],
            "outputs": [{"namespace": d.namespace, "name": d.name} for d in self.outputs]
                       + [{"namespace": f"app://{self.app_id}", "name": i.name} for i in self.exposes],
        }


def _ds(d: Dataset) -> dict:
    return {"namespace": d.namespace, "name": d.name, "dataClasses": sorted(d.data_classes),
            "connector": d.connector}


def observed_inputs(connector_reads: Iterable[Dataset]) -> list[Dataset]:
    """Deduplicate what the session actually read through connectors."""
    seen: dict[tuple[str, str], Dataset] = {}
    for d in connector_reads:
        key = (d.namespace, d.name)
        prev = seen.get(key)
        seen[key] = d if prev is None else Dataset(d.namespace, d.name, prev.data_classes | d.data_classes,
                                                   prev.connector or d.connector)
    return list(seen.values())


def estate_edges(manifests: Iterable[AppManifest]) -> list[tuple[str, str, str]]:
    """(from, to, kind) edges across all apps: data in, data out, app-to-app calls.

    Agent Authority draws the real estate view from lineage; this is the same picture
    computed locally, for tests and for the builder's 'what does this app touch' panel.
    """
    edges = []
    for m in manifests:
        node = f"app://{m.app_id}"
        edges += [(f"{d.namespace}/{d.name}", node, "reads") for d in m.inputs]
        edges += [(node, f"{d.namespace}/{d.name}", "writes") for d in m.outputs]
        edges += [(node, f"app://{d.app_id}", "calls") for d in m.depends_on]
    return edges
