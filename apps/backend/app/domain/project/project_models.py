from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from app.domain.project.project_exceptions import (
    InvalidProjectTransitionError,
)
from app.domain.project.project_lifecycle import (
    MUTABLE_STATES,
    ProjectLifecycleState,
    is_transition_valid,
)

# The Canonical Domain (app/domain/ontology/**) has no version scheme yet
# (docs/architecture/ARCHITECTURE_FREEZE_V1_CHECKLIST.md, item 7). This is
# the documented extension point: every Project still records a
# ``canonical_domain_version``, defaulting to this sentinel, so the field
# and every downstream reference to it are ready the moment the ontology
# adopts a real scheme (semantic version, git tag, dated release, ...) -
# no schema change will be required, only a change in what value is
# supplied at Project creation.
UNVERSIONED_CANONICAL_DOMAIN = "unversioned"


@dataclass(frozen=True, slots=True)
class Project:
    """
    A Project: the primary runtime boundary of SubstationOS. Represents
    one real engineering installation and instantiates the Canonical
    Domain; it never modifies it (ADR-0003).

    Immutable by construction, per CLAUDE.md's domain conventions: every
    lifecycle transition and metadata change returns a new ``Project``
    instance rather than mutating this one in place. ``id`` is ``None``
    for a project that has not yet been persisted.
    """

    id: int | None
    name: str
    code: str
    customer: str
    epc: str | None
    country: str | None
    location: str | None
    description: str | None
    lifecycle_state: ProjectLifecycleState
    canonical_domain_version: str
    created_by: str | None
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None
    deleted_at: datetime | None = None

    @property
    def traceability_reference(self) -> str:
        """
        The stable identifier every downstream fact, document, and graph
        node cites back to this Project by, per
        docs/architecture/project_intelligence_architecture.md §9. Always
        the project code, never the numeric id, since the code is the
        human-meaningful, externally-stable identifier.
        """

        return self.code

    def is_mutable(self) -> bool:
        return self.lifecycle_state in MUTABLE_STATES

    def _transition_to(
        self,
        target_state: ProjectLifecycleState,
        *,
        now: datetime,
        **extra_fields: datetime | None,
    ) -> Project:
        if not is_transition_valid(self.lifecycle_state, target_state):
            raise InvalidProjectTransitionError(
                self.lifecycle_state,
                target_state,
            )

        return replace(
            self,
            lifecycle_state=target_state,
            updated_at=now,
            **extra_fields,
        )

    def activate(self, *, now: datetime) -> Project:
        return self._transition_to(
            ProjectLifecycleState.ACTIVE,
            now=now,
        )

    def archive(self, *, now: datetime) -> Project:
        return self._transition_to(
            ProjectLifecycleState.ARCHIVED,
            now=now,
            archived_at=now,
        )

    def restore(self, *, now: datetime) -> Project:
        """
        Undoes exactly one step of the lifecycle, matching the linear
        chain in reverse: a Deleted project is restored to Archived; an
        Archived project is restored to Active. Restoring a Deleted
        project all the way to Active therefore takes two calls - this
        keeps ``archived_at``/``deleted_at`` precise and each step
        independently auditable, rather than silently jumping two states
        at once.
        """

        if self.lifecycle_state is ProjectLifecycleState.DELETED:
            return self._transition_to(
                ProjectLifecycleState.ARCHIVED,
                now=now,
                deleted_at=None,
            )

        return self._transition_to(
            ProjectLifecycleState.ACTIVE,
            now=now,
            archived_at=None,
        )

    def mark_deleted(self, *, now: datetime) -> Project:
        """
        Soft delete only. Never removes the record - sets the lifecycle
        state to Deleted and records ``deleted_at``. Callers must never
        issue a hard DELETE against a Project row; the persistence layer
        does not expose one.
        """

        return self._transition_to(
            ProjectLifecycleState.DELETED,
            now=now,
            deleted_at=now,
        )

    def with_metadata(
        self,
        *,
        now: datetime,
        name: str | None = None,
        customer: str | None = None,
        epc: str | None = None,
        country: str | None = None,
        location: str | None = None,
        description: str | None = None,
    ) -> Project:
        """
        Returns a copy with the given fields overwritten. Fields left as
        ``None`` are unchanged - this is a partial update, not a
        replace-with-null. ``code`` is never accepted here: once
        published, a project's code is a contract (CLAUDE.md §16) and is
        not renamed through a metadata update.
        """

        return replace(
            self,
            name=name if name is not None else self.name,
            customer=(
                customer if customer is not None else self.customer
            ),
            epc=epc if epc is not None else self.epc,
            country=country if country is not None else self.country,
            location=(
                location if location is not None else self.location
            ),
            description=(
                description
                if description is not None
                else self.description
            ),
            updated_at=now,
        )
