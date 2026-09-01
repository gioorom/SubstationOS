"""
Application service for Canonical Text Segmentation (EPIC 2,
Milestone 27.1).

    Canonical Representation   (Milestone 26.1, through its own port)
        -> Check the version    this segmenter understands it
        -> Segment              a pure domain function
        -> Persist              through CanonicalTextRepository

**Its only input is the Canonical Representation.** It has no content
port, no storage-location port and no parser: it could not reopen the
original PDF if it wanted to, which is the point. By this stage of the
pipeline the PDF has been decoded exactly once, and everything after it
reads what that decoding produced.

It invokes no LLM, computes no embeddings, and writes neither the
Engineering Index nor the Project Knowledge Graph. It assigns no
engineering meaning: what it stores is document *structure* - pages,
blocks, lines, tokens - and nothing about what any of it means.
"""

from __future__ import annotations

from dataclasses import replace

from dataclasses import dataclass

from app.domain.canonical_pdf.canonical_pdf_exceptions import (
    InvalidCanonicalRepresentationError,
)
from app.domain.canonical_pdf.canonical_representation_repository import (
    CanonicalRepresentationRepository,
)
from app.domain.artifact_identity.artifact_identity_exceptions import (  # noqa: E501
    InvalidArtifactIdentityError,
)
from app.domain.canonical_pdf.canonical_pdf_identity import (
    representation_identity,
)
from app.domain.canonical_text.canonical_text_identity import (
    segmentation_identity,
)
from app.domain.canonical_text.canonical_text_failures import (
    SegmentationFailure,
    SegmentationFailureCode,
)
from app.domain.canonical_text.canonical_text_models import (
    CanonicalTextDocument,
)
from app.domain.canonical_text.canonical_text_policy import (
    CANONICAL_SEGMENTATION_VERSION,
    SUPPORTED_REPRESENTATION_VERSIONS,
    is_supported_representation_version,
)
from app.domain.canonical_text.canonical_text_repository import (
    CanonicalTextRepository,
)
from app.domain.canonical_text.canonical_text_segmenter import (
    segment_canonical_document,
)


@dataclass(frozen=True, slots=True)
class SegmentationResult:
    """
    What one segmentation concluded.

    ``reused`` distinguishes "this representation was already segmented
    under these rules" from "it was segmented now". Both are successes
    returning the same value - but an operator watching a re-run deserves
    to know nothing was recomputed, and a test can prove idempotency from
    it.
    """

    succeeded: bool
    segmentation: CanonicalTextDocument | None = None
    reused: bool = False
    failure: SegmentationFailure | None = None


def segment_document(
    representation_repository: CanonicalRepresentationRepository,
    text_repository: CanonicalTextRepository,
    *,
    document_id: int,
    segmentation_version: str = CANONICAL_SEGMENTATION_VERSION,
) -> SegmentationResult:
    """
    Build - or re-use - the canonical text segmentation of one document.

    Checks run in order and the first failure is returned: there is no
    point complaining about a representation's version when there is no
    representation.
    """

    try:
        representation = (
            representation_repository.find_latest_for_document(document_id)
        )
    except InvalidCanonicalRepresentationError as error:
        # The stored representation no longer satisfies its own
        # invariants - it is rebuilt through the domain factory on read,
        # so this is caught here rather than discovered halfway through
        # segmenting. Distinct from a segmenter fault: the input was
        # already wrong.
        return _failed(
            SegmentationFailureCode.INVALID_CANONICAL_REPRESENTATION,
            f"The canonical representation of document '{document_id}' "
            "does not hold together.",
            detail=error.detail,
        )

    if representation is None:
        return _failed(
            SegmentationFailureCode.CANONICAL_REPRESENTATION_MISSING,
            f"Document '{document_id}' has no canonical representation; "
            "there is nothing to segment.",
            detail="Segmentation is the step after canonicalisation. The "
            "representation is its only input - segmentation never reads "
            "the original PDF.",
        )

    if not is_supported_representation_version(
        representation.representation_version
    ):
        return _failed(
            SegmentationFailureCode.UNSUPPORTED_REPRESENTATION_VERSION,
            f"The canonical representation of document '{document_id}' "
            f"is version "
            f"'{representation.representation_version}', which this "
            "segmenter does not understand.",
            detail=(
                "Supported: "
                + ", ".join(sorted(SUPPORTED_REPRESENTATION_VERSIONS))
                + ". A representation built under a newer contract may "
                "carry fields whose meaning this code would silently "
                "misinterpret, and a wrong structure is worse than a "
                "visible refusal."
            ),
        )

    # A representation's identity is a pure function of provenance the
    # representation itself carries, so it is recomputed here rather
    # than trusted blindly. A row stored before the identity chain
    # existed therefore needs no refusal and no guess: its identity is
    # *proven* from immutable persisted fields, not assumed.
    try:
        upstream_identity = representation_identity(
            document_id=representation.document_id,
            content_checksum=representation.content_checksum,
            checksum_algorithm=representation.checksum_algorithm,
            representation_version=representation.representation_version,
            parser_name=representation.parser_name,
            parser_version=representation.parser_version,
        )
    except InvalidArtifactIdentityError as error:
        # NOT NULL still permits an empty string, so a row can carry
        # provenance that cannot identify anything. A typed refusal, not
        # an exception crossing the boundary.
        return _failed(
            SegmentationFailureCode.INVALID_CANONICAL_REPRESENTATION,
            f"The canonical representation of document '{document_id}' "
            "carries provenance that cannot identify it.",
            detail=f"{type(error).__name__}: {error}",
        )

    if (
        representation.artifact_identity is not None
        and representation.artifact_identity != upstream_identity.value
    ):
        # The stored identity disagrees with the provenance stored
        # beside it. One of them is a lie, and nothing derived from a
        # corrupt artifact could be trusted.
        return _failed(
            SegmentationFailureCode.INVALID_CANONICAL_REPRESENTATION,
            f"The canonical representation of document '{document_id}' "
            "carries an identity its own provenance does not produce.",
            detail="Recorded "
            f"'{representation.artifact_identity}', provenance yields "
            f"'{upstream_identity.value}'. This is corruption rather "
            "than ambiguity, and segmenting it would propagate a false "
            "claim.",
        )

    # What this stage produces from *that* representation under its own
    # segmentation contract. A representation rebuilt under a raised
    # representation version is a different artifact with a different
    # identity, so its segmentation is a different artifact too - and
    # this layer never had to learn what a representation version is.
    expected_identity = segmentation_identity(
        representation=upstream_identity,
        segmentation_version=segmentation_version,
    )

    existing = text_repository.find_by_identity(
        document_id, expected_identity.value
    )

    if existing is not None:
        # The same representation under the same rules already has a
        # segmentation. Re-segmenting would produce an equal value and a
        # second row saying the same thing.
        return SegmentationResult(
            succeeded=True, segmentation=existing, reused=True
        )

    try:
        segmentation = segment_canonical_document(
            representation, segmentation_version=segmentation_version
        )
    except Exception as error:  # noqa: BLE001 - see below
        # The segmenter is pure and total by design, so reaching here
        # means a defect rather than a data condition. Caught anyway:
        # a caller needs one honest answer instead of an exception
        # crossing the boundary, and the cause is carried in ``detail``
        # rather than swallowed.
        return _failed(
            SegmentationFailureCode.SEGMENTATION_FAILURE,
            f"Segmenting document '{document_id}' failed.",
            detail=f"{type(error).__name__}: {error}",
        )

    if segmentation.is_empty:
        # A representation whose spans carry no tokenisable characters -
        # whitespace and formatting marks only. Persisting it would give
        # every future extractor a document that appears to say nothing,
        # indistinguishable from one that genuinely does.
        return _failed(
            SegmentationFailureCode.SEGMENTATION_FAILURE,
            f"Document '{document_id}' segmented to no tokens at all.",
            detail="Its canonical representation carries text spans, and "
            "none of them contain characters that survive tokenisation.",
        )

    segmentation = replace(
        segmentation,
        artifact_identity=expected_identity.value,
        upstream_identity=upstream_identity.value,
    )

    try:
        text_repository.save(segmentation)
    except Exception as error:  # noqa: BLE001 - see above
        return _failed(
            SegmentationFailureCode.REPRESENTATION_PERSISTENCE_FAILURE,
            f"The segmentation of document '{document_id}' was built and "
            "could not be stored.",
            detail=f"{type(error).__name__}: {error}",
        )

    return SegmentationResult(
        succeeded=True, segmentation=segmentation, reused=False
    )


def get_segmentation(
    text_repository: CanonicalTextRepository, document_id: int
) -> CanonicalTextDocument | None:
    """
    The current segmentation of one document - the **only** structure a
    future extractor should consume.

    ``None`` means it has never been segmented. Not an error: most
    documents have not been, and an empty segmentation would be
    indistinguishable from a document that genuinely says nothing.
    """

    return text_repository.find_latest_for_document(document_id)


def _failed(
    code: SegmentationFailureCode,
    message: str,
    *,
    detail: str | None = None,
) -> SegmentationResult:
    return SegmentationResult(
        succeeded=False,
        failure=SegmentationFailure(
            code=code, message=message, detail=detail
        ),
    )
