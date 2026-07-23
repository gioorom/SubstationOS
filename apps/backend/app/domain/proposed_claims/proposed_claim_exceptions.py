from __future__ import annotations

from app.domain.project.project_document_scope import DocumentScope
from app.domain.project.project_lifecycle import ProjectLifecycleState
from app.domain.proposed_claims.claim_type import ClaimType


class ProposedClaimError(Exception):
    """
    Base class for every exception raised by the Proposed Claims
    bounded context.
    """


class InvalidClaimSubjectError(ProposedClaimError):
    def __init__(self, value: str) -> None:
        self.value = value

        super().__init__(
            f"Invalid claim subject: '{value}'. A subject is required."
        )


class InvalidClaimPredicateError(ProposedClaimError):
    def __init__(self, value: str) -> None:
        self.value = value

        super().__init__(
            f"Invalid claim predicate: '{value}'. A predicate, when "
            "given, must not be blank."
        )


class InvalidClaimObjectError(ProposedClaimError):
    def __init__(self, value: str) -> None:
        self.value = value

        super().__init__(
            f"Invalid claim object: '{value}'. An object, when given, "
            "must not be blank."
        )


class ClaimPredicateRequiredError(ProposedClaimError):
    def __init__(self, claim_type: ClaimType) -> None:
        self.claim_type = claim_type

        super().__init__(
            f"A predicate is required for a '{claim_type.value}' claim."
        )


class ClaimObjectRequiredError(ProposedClaimError):
    def __init__(self, claim_type: ClaimType) -> None:
        self.claim_type = claim_type

        super().__init__(
            f"An object is required for a '{claim_type.value}' claim."
        )


class EmptyEvidenceError(ProposedClaimError):
    """A claim with no supporting Engineering Index entries is not a
    claim - it is an unsupported assertion."""

    def __init__(self) -> None:
        super().__init__(
            "A claim must cite at least one Engineering Index entry as "
            "evidence."
        )


class DuplicateEvidenceError(ProposedClaimError):
    def __init__(self, engineering_index_entry_id: int) -> None:
        self.engineering_index_entry_id = engineering_index_entry_id

        super().__init__(
            "Engineering Index entry "
            f"'{engineering_index_entry_id}' is cited more than once as "
            "evidence for the same claim."
        )


class EvidenceEntryNotFoundError(ProposedClaimError):
    def __init__(self, engineering_index_entry_id: int) -> None:
        self.engineering_index_entry_id = engineering_index_entry_id

        super().__init__(
            f"Engineering Index entry '{engineering_index_entry_id}' "
            "not found."
        )


class CrossProjectEvidenceError(ProposedClaimError):
    """
    Every evidence entry cited by one claim must belong to the same
    Project (ADR-0001) - a claim can never assert something spanning two
    installations.
    """

    def __init__(self, project_ids: frozenset[int]) -> None:
        self.project_ids = project_ids

        super().__init__(
            "Evidence for one claim must all belong to the same "
            f"project; found: {sorted(project_ids)}."
        )


class CrossDocumentEvidenceNotAllowedError(ProposedClaimError):
    """
    Evidence spanning more than one document is a real, expected case
    (a relationship's subject and object are often described in two
    different documents) but must be explicit, not incidental -
    ``allow_cross_document_evidence`` must be set.
    """

    def __init__(self, document_ids: frozenset[int]) -> None:
        self.document_ids = document_ids

        super().__init__(
            "Evidence spans more than one document "
            f"({sorted(document_ids)}); pass "
            "allow_cross_document_evidence=True if that is intended."
        )


class DocumentNotClaimableError(ProposedClaimError):
    """
    Mirrors ``engineering_index.DocumentNotIndexableError`` as an
    independent check: only PROJECT-scoped documents can back a claim.
    """

    def __init__(self, document_id: int, scope: DocumentScope) -> None:
        self.document_id = document_id
        self.scope = scope

        super().__init__(
            f"Document '{document_id}' has scope '{scope.value}' and "
            "cannot back a claim. Only PROJECT-scoped documents are "
            "usable as evidence."
        )


class ProjectNotClaimableError(ProposedClaimError):
    """
    Proposing (or replacing evidence for) a claim is a write against a
    Project's data; Archived and Deleted projects are read-only, per the
    Project Lifecycle.
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
            "is read-only; no claim can be proposed or changed against "
            "it."
        )


class DuplicateProposedClaimError(ProposedClaimError):
    """
    A claim asserting the same subject/predicate/object, of the same
    type, in the same project, has already been proposed.
    """

    def __init__(
        self,
        project_id: int,
        claim_type: ClaimType,
        subject: str,
    ) -> None:
        self.project_id = project_id
        self.claim_type = claim_type
        self.subject = subject

        super().__init__(
            f"A '{claim_type.value}' claim about '{subject}' has "
            f"already been proposed in project '{project_id}'."
        )


class ProposedClaimNotFoundError(ProposedClaimError):
    def __init__(self, claim_id: int) -> None:
        self.claim_id = claim_id

        super().__init__(f"Proposed claim '{claim_id}' not found.")
