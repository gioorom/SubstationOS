from __future__ import annotations

from app.domain.project.project_lifecycle import ProjectLifecycleState
from app.domain.proposed_claims.claim_type import ClaimType


class GraphBuilderError(Exception):
    """
    Base class for every exception raised by the Graph Builder bounded
    context.
    """


class UnsupportedClaimTypeError(GraphBuilderError):
    def __init__(self, claim_type: object) -> None:
        self.claim_type = claim_type

        super().__init__(
            f"'{claim_type}' is not a supported claim type. Supported "
            f"types: {', '.join(t.value for t in ClaimType)}."
        )


class InvalidCanonicalFactShapeError(GraphBuilderError):
    """
    An ``ATTRIBUTE`` Canonical Fact has no ``predicate_value``/
    ``object_value`` - a data-integrity anomaly Canonicalization's own
    factory should already prevent, checked defensively here rather
    than assumed.
    """

    def __init__(self, fact_id: int | None, claim_type: ClaimType) -> None:
        self.fact_id = fact_id
        self.claim_type = claim_type

        super().__init__(
            f"Canonical fact '{fact_id}' ('{claim_type.value}') is "
            "missing the predicate/value its claim type requires."
        )


class MissingEntityReferenceError(GraphBuilderError):
    """
    A ``RELATIONSHIP`` Canonical Fact has no ``object_entity`` - a
    data-integrity anomaly Canonicalization's own factory should
    already prevent.
    """

    def __init__(self, fact_id: int | None) -> None:
        self.fact_id = fact_id

        super().__init__(
            f"Canonical fact '{fact_id}' is missing the entity "
            "reference its claim type requires."
        )


class CrossProjectGraphOperationError(GraphBuilderError):
    """
    Every Canonical Fact folded into one batch must belong to the same
    project (ADR-0001) - a data-integrity anomaly, since
    ``CanonicalFactRepository.list_by_project``/``list_by_document``
    should never mix projects.
    """

    def __init__(
        self,
        expected_project_id: int,
        fact_project_id: int,
        fact_id: int | None,
    ) -> None:
        self.expected_project_id = expected_project_id
        self.fact_project_id = fact_project_id
        self.fact_id = fact_id

        super().__init__(
            f"Canonical fact '{fact_id}' belongs to project "
            f"'{fact_project_id}', not the batch's project "
            f"'{expected_project_id}'."
        )


class ConflictingAttributeOperationError(GraphBuilderError):
    """
    Two different Canonical Facts assert different values for the same
    canonical entity/attribute pair within one batch - a genuine
    conflict, not a duplicate, and is rejected rather than silently
    resolved by picking one.
    """

    def __init__(
        self,
        entity_id_value: str,
        attribute: str,
        existing_value: str,
        new_value: str,
    ) -> None:
        self.entity_id_value = entity_id_value
        self.attribute = attribute
        self.existing_value = existing_value
        self.new_value = new_value

        super().__init__(
            f"Conflicting values for '{entity_id_value}'.{attribute}: "
            f"'{existing_value}' and '{new_value}'."
        )


class GraphOperationBatchNotFoundError(GraphBuilderError):
    def __init__(self, batch_id: int) -> None:
        self.batch_id = batch_id

        super().__init__(f"Graph operation batch '{batch_id}' not found.")


class GraphBuilderProjectNotFoundError(GraphBuilderError):
    def __init__(self, project_id: int) -> None:
        self.project_id = project_id

        super().__init__(f"Project '{project_id}' not found.")


class ProjectNotGraphBuildableError(GraphBuilderError):
    """
    Building a graph operation batch persists a new record scoped to a
    Project; Archived and Deleted projects are read-only, per the
    Project Lifecycle - the same rule every other write path in this
    system enforces.
    """

    def __init__(
        self,
        project_id: int,
        lifecycle_state: ProjectLifecycleState,
    ) -> None:
        self.project_id = project_id
        self.lifecycle_state = lifecycle_state

        super().__init__(
            f"Project '{project_id}' is '{lifecycle_state.value}' and "
            "is read-only; no graph operation batch can be built for "
            "it."
        )
