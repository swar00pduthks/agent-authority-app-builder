"""Sticky data classes for a build session.

The tenant admin sets data classes per project (for example kyc-* projects are
client-data) and per approved connector. When a connector result enters a session, its
classes join the session's set and stay there. Every model call afterwards passes the
union, so Agent Authority's router keeps sensitive prompts on tenant-hosted models.
A builder can add a class but never remove one.
"""

from __future__ import annotations

from dataclasses import dataclass, field


class DowngradeRefused(PermissionError):
    pass


@dataclass
class SessionDataClasses:
    project_classes: frozenset[str]
    _seen: set[str] = field(default_factory=set)

    @property
    def current(self) -> frozenset[str]:
        return frozenset(self.project_classes | self._seen)

    def absorb(self, connector_classes: frozenset[str] | set[str]) -> frozenset[str]:
        """Call whenever a connector result enters the session."""
        self._seen |= set(connector_classes)
        return self.current

    def add(self, cls: str) -> frozenset[str]:
        """A builder may raise sensitivity."""
        self._seen.add(cls)
        return self.current

    def remove(self, cls: str) -> None:
        """A builder may never lower it, not even for classes they added."""
        raise DowngradeRefused(f"data class {cls!r} can't be removed from a session")


def project_classes_for(project_name: str, admin_classes: frozenset[str]) -> frozenset[str]:
    """Admin-set classes plus the naming rule agreed with Agent Authority (kyc-* is client-data)."""
    classes = set(admin_classes)
    if project_name.startswith("kyc-"):
        classes.add("client-data")
    return frozenset(classes)
