from __future__ import annotations

from dataclasses import replace
from datetime import datetime

import pytest

from app.domain.engineering_index.document_lookup import (
    DocumentIndexContext,
    DocumentLookupPort,
)
from app.domain.engineering_index.engineering_index_entry_kind import (
    EngineeringIndexEntryKind,
)
from app.domain.engineering_index.engineering_index_locator import (
    IndexEntryLocator,
    IndexEntryLocatorKind,
)
from app.domain.engineering_index.engineering_index_models import IndexEntry
from app.domain.engineering_index.engineering_index_repository import (
    EngineeringIndexRepository,
)
from app.domain.project.project_document_scope import DocumentScope
from app.domain.project.project_lifecycle import ProjectLifecycleState
from app.domain.proposed_claims.claim_type import ClaimType
from app.domain.proposed_claims.proposed_claim_exceptions import (
    ClaimPredicateRequiredError,
    CrossDocumentEvidenceNotAllowedError,
    CrossProjectEvidenceError,
    DocumentNotClaimableError,
    DuplicateProposedClaimError,
    EvidenceEntryNotFoundError,
    ProjectNotClaimableError,
    ProposedClaimNotFoundError,
)
from app.domain.proposed_claims.proposed_claim_models import (
    ClaimObject,
    ClaimPredicate,
    ClaimSubject,
    EvidenceReference,
    ProposedClaim,
)
from app.domain.proposed_claims.proposed_claim_repository import (
    ProposedClaimRepository,
)
from app.services import proposed_claim_service

CREATED_AT = datetime(2026, 1, 1, 10, 0, 0)
_LOCATOR = IndexEntryLocator(kind=IndexEntryLocatorKind.PAGE, value=None)


class FakeEngineeringIndexRepository(EngineeringIndexRepository):
    def __init__(self) -> None:
        self._entries: dict[int, IndexEntry] = {}
        self._next_id = 1

    def register(
        self,
        *,
        document_id: int,
        project_id: int,
        identifier: str,
    ) -> IndexEntry:
        entry = IndexEntry(
            id=self._next_id,
            project_id=project_id,
            document_id=document_id,
            kind=EngineeringIndexEntryKind.EQUIPMENT,
            identifier=identifier,
            locator=_LOCATOR,
            label=None,
            created_at=CREATED_AT,
        )
        self._entries[self._next_id] = entry
        self._next_id += 1

        return entry

    def save(self, entry: IndexEntry) -> IndexEntry:
        raise NotImplementedError

    def get_by_id(self, entry_id: int) -> IndexEntry | None:
        return self._entries.get(entry_id)

    def list_by_document(self, document_id: int) -> list[IndexEntry]:
        raise NotImplementedError

    def list_by_project(
        self,
        project_id: int,
        *,
        kind: EngineeringIndexEntryKind | None = None,
    ) -> list[IndexEntry]:
        raise NotImplementedError

    def search_by_identifier(
        self,
        project_id: int,
        identifier: str,
    ) -> list[IndexEntry]:
        raise NotImplementedError

    def replace_for_document(
        self,
        document_id: int,
        project_id: int,
        entries: list[IndexEntry],
    ) -> list[IndexEntry]:
        raise NotImplementedError

    def delete_by_document(self, document_id: int) -> None:
        raise NotImplementedError


class FakeDocumentLookup(DocumentLookupPort):
    def __init__(self) -> None:
        self._documents: dict[int, DocumentIndexContext] = {}

    def register(self, context: DocumentIndexContext) -> None:
        self._documents[context.document_id] = context

    def find(self, document_id: int) -> DocumentIndexContext | None:
        return self._documents.get(document_id)


class FakeProposedClaimRepository(ProposedClaimRepository):
    def __init__(self) -> None:
        self._claims: dict[int, ProposedClaim] = {}
        self._next_id = 1

    def create(self, claim: ProposedClaim) -> ProposedClaim:
        claim = replace(claim, id=self._next_id)
        self._claims[self._next_id] = claim
        self._next_id += 1

        return claim

    def get_by_id(self, claim_id: int) -> ProposedClaim | None:
        return self._claims.get(claim_id)

    def find_duplicate(
        self,
        project_id: int,
        claim_type: ClaimType,
        subject: ClaimSubject,
        predicate: ClaimPredicate | None,
        object_: ClaimObject | None,
    ) -> ProposedClaim | None:
        for claim in self._claims.values():
            if (
                claim.project_id == project_id
                and claim.claim_type is claim_type
                and claim.subject == subject
                and claim.predicate == predicate
                and claim.object == object_
            ):
                return claim

        return None

    def list_by_project(self, project_id: int) -> list[ProposedClaim]:
        return [
            claim
            for claim in self._claims.values()
            if claim.project_id == project_id
        ]

    def list_by_document(self, document_id: int) -> list[ProposedClaim]:
        return [
            claim
            for claim in self._claims.values()
            if any(
                reference.document_id == document_id
                for reference in claim.evidence
            )
        ]

    def replace_evidence(
        self,
        claim_id: int,
        evidence: list[EvidenceReference],
    ) -> ProposedClaim:
        claim = self._claims[claim_id]
        self._claims[claim_id] = replace(
            claim,
            evidence=tuple(evidence),
        )

        return self._claims[claim_id]

    def delete(self, claim_id: int) -> None:
        self._claims.pop(claim_id, None)


@pytest.fixture()
def document_lookup() -> FakeDocumentLookup:
    lookup = FakeDocumentLookup()
    lookup.register(
        DocumentIndexContext(
            document_id=1,
            project_id=10,
            scope=DocumentScope.PROJECT,
            project_lifecycle_state=ProjectLifecycleState.ACTIVE,
        )
    )
    lookup.register(
        DocumentIndexContext(
            document_id=2,
            project_id=10,
            scope=DocumentScope.PROJECT,
            project_lifecycle_state=ProjectLifecycleState.ACTIVE,
        )
    )
    lookup.register(
        DocumentIndexContext(
            document_id=3,
            project_id=20,
            scope=DocumentScope.PROJECT,
            project_lifecycle_state=ProjectLifecycleState.ACTIVE,
        )
    )
    lookup.register(
        DocumentIndexContext(
            document_id=4,
            project_id=None,
            scope=DocumentScope.CANONICAL_LIBRARY,
            project_lifecycle_state=None,
        )
    )
    lookup.register(
        DocumentIndexContext(
            document_id=5,
            project_id=30,
            scope=DocumentScope.PROJECT,
            project_lifecycle_state=ProjectLifecycleState.ARCHIVED,
        )
    )

    return lookup


@pytest.fixture()
def engineering_index_repository() -> FakeEngineeringIndexRepository:
    repository = FakeEngineeringIndexRepository()
    repository.register(document_id=1, project_id=10, identifier="C-295")
    repository.register(document_id=1, project_id=10, identifier="TR-02")
    repository.register(document_id=2, project_id=10, identifier="TR-03")
    repository.register(document_id=3, project_id=20, identifier="TR-04")
    repository.register(document_id=4, project_id=99, identifier="TR-05")
    repository.register(document_id=5, project_id=30, identifier="TR-06")

    return repository


@pytest.fixture()
def claim_repository() -> FakeProposedClaimRepository:
    return FakeProposedClaimRepository()


def test_create_proposed_claim_succeeds_for_reviewable_evidence(
    claim_repository: FakeProposedClaimRepository,
    engineering_index_repository: FakeEngineeringIndexRepository,
    document_lookup: FakeDocumentLookup,
) -> None:
    claim = proposed_claim_service.create_proposed_claim(
        claim_repository,
        engineering_index_repository,
        document_lookup,
        claim_type=ClaimType.RELATIONSHIP,
        subject="Cable C-295",
        predicate="FEEDS",
        object_="Transformer TR-02",
        engineering_index_entry_ids=[1, 2],
        now=CREATED_AT,
    )

    assert claim.id is not None
    assert claim.project_id == 10
    assert len(claim.evidence) == 2


def test_create_proposed_claim_raises_for_an_unknown_entry(
    claim_repository: FakeProposedClaimRepository,
    engineering_index_repository: FakeEngineeringIndexRepository,
    document_lookup: FakeDocumentLookup,
) -> None:
    with pytest.raises(EvidenceEntryNotFoundError):
        proposed_claim_service.create_proposed_claim(
            claim_repository,
            engineering_index_repository,
            document_lookup,
            claim_type=ClaimType.EXISTENCE,
            subject="Cable C-295",
            predicate=None,
            object_=None,
            engineering_index_entry_ids=[999],
            now=CREATED_AT,
        )


def test_create_proposed_claim_rejects_a_canonical_library_document(
    claim_repository: FakeProposedClaimRepository,
    engineering_index_repository: FakeEngineeringIndexRepository,
    document_lookup: FakeDocumentLookup,
) -> None:
    with pytest.raises(DocumentNotClaimableError):
        proposed_claim_service.create_proposed_claim(
            claim_repository,
            engineering_index_repository,
            document_lookup,
            claim_type=ClaimType.EXISTENCE,
            subject="TR-05",
            predicate=None,
            object_=None,
            engineering_index_entry_ids=[5],
            now=CREATED_AT,
        )


def test_create_proposed_claim_rejects_an_archived_project(
    claim_repository: FakeProposedClaimRepository,
    engineering_index_repository: FakeEngineeringIndexRepository,
    document_lookup: FakeDocumentLookup,
) -> None:
    with pytest.raises(ProjectNotClaimableError):
        proposed_claim_service.create_proposed_claim(
            claim_repository,
            engineering_index_repository,
            document_lookup,
            claim_type=ClaimType.EXISTENCE,
            subject="TR-06",
            predicate=None,
            object_=None,
            engineering_index_entry_ids=[6],
            now=CREATED_AT,
        )


def test_create_proposed_claim_rejects_evidence_spanning_projects(
    claim_repository: FakeProposedClaimRepository,
    engineering_index_repository: FakeEngineeringIndexRepository,
    document_lookup: FakeDocumentLookup,
) -> None:
    with pytest.raises(CrossProjectEvidenceError):
        proposed_claim_service.create_proposed_claim(
            claim_repository,
            engineering_index_repository,
            document_lookup,
            claim_type=ClaimType.RELATIONSHIP,
            subject="Cable C-295",
            predicate="FEEDS",
            object_="TR-04",
            engineering_index_entry_ids=[1, 4],
            now=CREATED_AT,
        )


def test_create_proposed_claim_rejects_evidence_spanning_documents_by_default(
    claim_repository: FakeProposedClaimRepository,
    engineering_index_repository: FakeEngineeringIndexRepository,
    document_lookup: FakeDocumentLookup,
) -> None:
    with pytest.raises(CrossDocumentEvidenceNotAllowedError):
        proposed_claim_service.create_proposed_claim(
            claim_repository,
            engineering_index_repository,
            document_lookup,
            claim_type=ClaimType.RELATIONSHIP,
            subject="Cable C-295",
            predicate="FEEDS",
            object_="TR-03",
            engineering_index_entry_ids=[1, 3],
            now=CREATED_AT,
        )


def test_create_proposed_claim_accepts_evidence_spanning_documents_when_allowed(
    claim_repository: FakeProposedClaimRepository,
    engineering_index_repository: FakeEngineeringIndexRepository,
    document_lookup: FakeDocumentLookup,
) -> None:
    claim = proposed_claim_service.create_proposed_claim(
        claim_repository,
        engineering_index_repository,
        document_lookup,
        claim_type=ClaimType.RELATIONSHIP,
        subject="Cable C-295",
        predicate="FEEDS",
        object_="TR-03",
        engineering_index_entry_ids=[1, 3],
        now=CREATED_AT,
        allow_cross_document_evidence=True,
    )

    assert {reference.document_id for reference in claim.evidence} == {
        1,
        2,
    }


def test_create_proposed_claim_rejects_a_relationship_with_no_predicate(
    claim_repository: FakeProposedClaimRepository,
    engineering_index_repository: FakeEngineeringIndexRepository,
    document_lookup: FakeDocumentLookup,
) -> None:
    with pytest.raises(ClaimPredicateRequiredError):
        proposed_claim_service.create_proposed_claim(
            claim_repository,
            engineering_index_repository,
            document_lookup,
            claim_type=ClaimType.RELATIONSHIP,
            subject="Cable C-295",
            predicate=None,
            object_="Transformer TR-02",
            engineering_index_entry_ids=[1],
            now=CREATED_AT,
        )


def test_create_proposed_claim_rejects_a_duplicate_claim(
    claim_repository: FakeProposedClaimRepository,
    engineering_index_repository: FakeEngineeringIndexRepository,
    document_lookup: FakeDocumentLookup,
) -> None:
    proposed_claim_service.create_proposed_claim(
        claim_repository,
        engineering_index_repository,
        document_lookup,
        claim_type=ClaimType.EXISTENCE,
        subject="Cable C-295",
        predicate=None,
        object_=None,
        engineering_index_entry_ids=[1],
        now=CREATED_AT,
    )

    with pytest.raises(DuplicateProposedClaimError):
        proposed_claim_service.create_proposed_claim(
            claim_repository,
            engineering_index_repository,
            document_lookup,
            claim_type=ClaimType.EXISTENCE,
            subject="Cable C-295",
            predicate=None,
            object_=None,
            engineering_index_entry_ids=[2],
            now=CREATED_AT,
        )


def test_get_proposed_claim_raises_for_an_unknown_claim(
    claim_repository: FakeProposedClaimRepository,
) -> None:
    with pytest.raises(ProposedClaimNotFoundError):
        proposed_claim_service.get_proposed_claim(claim_repository, 999)


def test_list_proposed_claims_for_project_does_not_leak_across_projects(
    claim_repository: FakeProposedClaimRepository,
    engineering_index_repository: FakeEngineeringIndexRepository,
    document_lookup: FakeDocumentLookup,
) -> None:
    proposed_claim_service.create_proposed_claim(
        claim_repository,
        engineering_index_repository,
        document_lookup,
        claim_type=ClaimType.EXISTENCE,
        subject="Cable C-295",
        predicate=None,
        object_=None,
        engineering_index_entry_ids=[1],
        now=CREATED_AT,
    )
    proposed_claim_service.create_proposed_claim(
        claim_repository,
        engineering_index_repository,
        document_lookup,
        claim_type=ClaimType.EXISTENCE,
        subject="TR-04",
        predicate=None,
        object_=None,
        engineering_index_entry_ids=[4],
        now=CREATED_AT,
    )

    project_10 = proposed_claim_service.list_proposed_claims_for_project(
        claim_repository,
        10,
    )
    project_20 = proposed_claim_service.list_proposed_claims_for_project(
        claim_repository,
        20,
    )

    assert len(project_10) == 1
    assert len(project_20) == 1


def test_list_proposed_claims_for_document_does_not_leak_across_documents(
    claim_repository: FakeProposedClaimRepository,
    engineering_index_repository: FakeEngineeringIndexRepository,
    document_lookup: FakeDocumentLookup,
) -> None:
    proposed_claim_service.create_proposed_claim(
        claim_repository,
        engineering_index_repository,
        document_lookup,
        claim_type=ClaimType.EXISTENCE,
        subject="Cable C-295",
        predicate=None,
        object_=None,
        engineering_index_entry_ids=[1],
        now=CREATED_AT,
    )
    proposed_claim_service.create_proposed_claim(
        claim_repository,
        engineering_index_repository,
        document_lookup,
        claim_type=ClaimType.EXISTENCE,
        subject="TR-03",
        predicate=None,
        object_=None,
        engineering_index_entry_ids=[3],  # document 2
        now=CREATED_AT,
    )

    document_1 = proposed_claim_service.list_proposed_claims_for_document(
        claim_repository,
        1,
    )
    document_2 = proposed_claim_service.list_proposed_claims_for_document(
        claim_repository,
        2,
    )

    assert len(document_1) == 1
    assert len(document_2) == 1


def test_replace_claim_evidence_swaps_in_new_evidence(
    claim_repository: FakeProposedClaimRepository,
    engineering_index_repository: FakeEngineeringIndexRepository,
    document_lookup: FakeDocumentLookup,
) -> None:
    claim = proposed_claim_service.create_proposed_claim(
        claim_repository,
        engineering_index_repository,
        document_lookup,
        claim_type=ClaimType.EXISTENCE,
        subject="Cable C-295",
        predicate=None,
        object_=None,
        engineering_index_entry_ids=[1],
        now=CREATED_AT,
    )

    updated = proposed_claim_service.replace_claim_evidence(
        claim_repository,
        engineering_index_repository,
        document_lookup,
        claim_id=claim.id,  # type: ignore[arg-type]
        engineering_index_entry_ids=[2],
        now=CREATED_AT,
    )

    assert [
        reference.engineering_index_entry_id
        for reference in updated.evidence
    ] == [2]


def test_replace_claim_evidence_raises_for_an_unknown_claim(
    claim_repository: FakeProposedClaimRepository,
    engineering_index_repository: FakeEngineeringIndexRepository,
    document_lookup: FakeDocumentLookup,
) -> None:
    with pytest.raises(ProposedClaimNotFoundError):
        proposed_claim_service.replace_claim_evidence(
            claim_repository,
            engineering_index_repository,
            document_lookup,
            claim_id=999,
            engineering_index_entry_ids=[1],
            now=CREATED_AT,
        )


def test_replace_claim_evidence_rejects_evidence_from_a_different_project(
    claim_repository: FakeProposedClaimRepository,
    engineering_index_repository: FakeEngineeringIndexRepository,
    document_lookup: FakeDocumentLookup,
) -> None:
    claim = proposed_claim_service.create_proposed_claim(
        claim_repository,
        engineering_index_repository,
        document_lookup,
        claim_type=ClaimType.EXISTENCE,
        subject="Cable C-295",
        predicate=None,
        object_=None,
        engineering_index_entry_ids=[1],
        now=CREATED_AT,
    )

    with pytest.raises(CrossProjectEvidenceError):
        proposed_claim_service.replace_claim_evidence(
            claim_repository,
            engineering_index_repository,
            document_lookup,
            claim_id=claim.id,  # type: ignore[arg-type]
            engineering_index_entry_ids=[4],
            now=CREATED_AT,
        )


def test_delete_proposed_claim_removes_it(
    claim_repository: FakeProposedClaimRepository,
    engineering_index_repository: FakeEngineeringIndexRepository,
    document_lookup: FakeDocumentLookup,
) -> None:
    claim = proposed_claim_service.create_proposed_claim(
        claim_repository,
        engineering_index_repository,
        document_lookup,
        claim_type=ClaimType.EXISTENCE,
        subject="Cable C-295",
        predicate=None,
        object_=None,
        engineering_index_entry_ids=[1],
        now=CREATED_AT,
    )

    proposed_claim_service.delete_proposed_claim(
        claim_repository,
        claim.id,  # type: ignore[arg-type]
    )

    assert claim_repository.get_by_id(claim.id) is None  # type: ignore[arg-type]


def test_delete_proposed_claim_raises_for_an_unknown_claim(
    claim_repository: FakeProposedClaimRepository,
) -> None:
    with pytest.raises(ProposedClaimNotFoundError):
        proposed_claim_service.delete_proposed_claim(
            claim_repository,
            999,
        )
