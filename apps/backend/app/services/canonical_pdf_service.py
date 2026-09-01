"""
Application service for the Canonical PDF Representation (EPIC 2,
Milestone 26.1).

    READY_FOR_EXTRACTION      (an ingestion job said so - Milestone 25.1)
        -> Read PDF           (through DocumentContentPort - 25.2)
        -> Parse pages        (through PdfParserPort)
        -> Parse blocks
        -> Parse spans
        -> Canonical representation
        -> Persist            (through CanonicalRepresentationRepository)

Every stage is an existing capability behind an existing port. This
service adds orchestration and one decision of its own - whether the
document may be canonicalised at all - and nothing else.

**It starts at READY_FOR_EXTRACTION on purpose.** Parsing a document that
no ingestion job ever accepted would bypass the governed flow: the
checksum, the classified format and the accessibility check are precisely
what make the resulting representation trustworthy, and re-deriving them
here would create a second, quieter path into the same artefact.

It reads bytes only through Milestone 25.2's content port, invokes no
LLM, computes no embeddings, and writes neither the Engineering Index nor
the Project Knowledge Graph. It interprets nothing: what it stores is
what the parser observed.
"""

from __future__ import annotations

from dataclasses import replace

from dataclasses import dataclass

from app.domain.artifact_identity.artifact_identity_builder import (
    derive_identity,
    source_identity,
)
from app.domain.artifact_identity.artifact_identity_models import (
    ArtifactKind,
)
from app.domain.canonical_pdf.canonical_pdf_policy import (
    CANONICAL_REPRESENTATION_VERSION,
)
from app.domain.canonical_pdf.canonical_pdf_failures import (
    CanonicalizationFailure,
    CanonicalizationFailureCode,
)
from app.domain.canonical_pdf.canonical_pdf_models import (
    CanonicalPdfDocument,
    CanonicalPdfPage,
)
from app.domain.canonical_pdf.canonical_pdf_policy import (
    SUPPORTED_CANONICALIZATION_FORMATS,
    is_canonicalizable_format,
)
from app.domain.canonical_pdf.canonical_representation_repository import (
    CanonicalRepresentationRepository,
)
from app.domain.canonical_pdf.pdf_parser_port import PdfParserPort
from app.domain.document_identity.content_identity import (
    ContentIdentityFailureReason,
    ContentIdentityResult,
    resolve_content_identity,
)
from app.domain.document_identity.document_content_port import (
    DocumentContentPort,
)
from app.domain.document_identity.document_storage_location import (
    DocumentStorageLocationPort,
)
from app.domain.document_ingestion.ingestion_repository import (
    IngestionJobRepository,
)
from app.domain.engineering_index.document_metadata import (
    DocumentMetadata,
    DocumentMetadataPort,
)

# Content-identity failures map one-for-one onto this context's own
# taxonomy. A table rather than a branch chain, and one-for-one rather
# than collapsed: the record points nowhere, the file cannot be opened,
# or it is empty - three different places to look.
_CONTENT_FAILURE_CODES: dict[
    ContentIdentityFailureReason, CanonicalizationFailureCode
] = {
    ContentIdentityFailureReason.CONTENT_NOT_FOUND: (
        CanonicalizationFailureCode.CONTENT_NOT_FOUND
    ),
    ContentIdentityFailureReason.CONTENT_INACCESSIBLE: (
        CanonicalizationFailureCode.CONTENT_INACCESSIBLE
    ),
    ContentIdentityFailureReason.EMPTY_CONTENT: (
        CanonicalizationFailureCode.EMPTY_CONTENT
    ),
    ContentIdentityFailureReason.CHECKSUM_FAILURE: (
        CanonicalizationFailureCode.CONTENT_INACCESSIBLE
    ),
}


@dataclass(frozen=True, slots=True)
class CanonicalizationResult:
    """
    What one canonicalisation concluded.

    ``reused`` distinguishes "these bytes already had a representation"
    from "one was built now". Both are successes and both return the same
    representation - but an operator watching a re-run deserves to know
    that nothing was re-parsed, and a test can prove idempotency from it.
    """

    succeeded: bool
    representation: CanonicalPdfDocument | None = None
    reused: bool = False
    failure: CanonicalizationFailure | None = None


def canonicalize_document(
    parser: PdfParserPort,
    repository: CanonicalRepresentationRepository,
    content_port: DocumentContentPort,
    storage_location_port: DocumentStorageLocationPort,
    document_metadata_port: DocumentMetadataPort,
    ingestion_repository: IngestionJobRepository,
    *,
    document_id: int,
) -> CanonicalizationResult:
    """
    Build - or re-use - the canonical representation of one document.

    Checks run in order, and the first failure is returned: there is no
    point reporting an unparseable PDF for a document that does not
    exist, or a format complaint about bytes nobody can read.
    """

    metadata = _find_document(document_metadata_port, document_id)

    if metadata is None:
        return _failed(
            CanonicalizationFailureCode.DOCUMENT_NOT_FOUND,
            f"Document '{document_id}' does not exist; there is nothing "
            "to canonicalise.",
        )

    if not is_canonicalizable_format(metadata.document_format):
        return _failed(
            CanonicalizationFailureCode.UNSUPPORTED_FORMAT,
            f"Document '{document_id}' is recorded as "
            f"'{metadata.document_format}', which this milestone does "
            "not canonicalise.",
            detail=(
                "Canonicalisable formats: "
                + ", ".join(sorted(SUPPORTED_CANONICALIZATION_FORMATS))
                + ". A drawing is not badly-formed text; it is a "
                "different problem, and representing it as text would "
                "put nonsense into the artefact every future extraction "
                "trusts."
            ),
        )

    if not _is_ready_for_extraction(ingestion_repository, document_id):
        return _failed(
            CanonicalizationFailureCode.NOT_READY_FOR_EXTRACTION,
            f"Document '{document_id}' has no ingestion job that "
            "concluded READY_FOR_EXTRACTION.",
            detail="Canonicalisation is the step after ingestion. The "
            "checksum, classified format and accessibility checks "
            "ingestion performs are what make a representation "
            "trustworthy; parsing without them would be a second, "
            "quieter path to the same artefact.",
        )

    identity = resolve_content_identity(
        content_port,
        storage_location_port.find_storage_reference(document_id) or "",
    )

    if not identity.resolved:
        return _failed(
            _CONTENT_FAILURE_CODES[identity.failure_reason],
            f"Document '{document_id}' has no usable stored content.",
            detail=identity.detail,
        )

    # The identity of the representation these bytes produce under the
    # current representation contract. Same bytes is not the same
    # representation: the parser and the normalisation it applies are
    # versioned separately from the document, so the contract is part of
    # what is being asked for.
    source = source_identity(
        document_id=document_id,
        content_checksum=identity.identity.checksum,
        checksum_algorithm=identity.identity.checksum_algorithm,
    )
    expected_identity = derive_identity(
        ArtifactKind.CANONICAL_PDF,
        upstream=source,
        local=(
            ("representation_version", CANONICAL_REPRESENTATION_VERSION),
            ("parser_name", parser.parser_name),
            ("parser_version", parser.parser_version),
        ),
    )

    existing = repository.find_by_identity(
        document_id, expected_identity.value
    )

    if existing is not None:
        # The same bytes under the same contract already have a
        # representation. Re-parsing would produce an equal value and a
        # second row saying the same thing; the stored one is returned
        # instead, which is what makes re-running this safe.
        return CanonicalizationResult(
            succeeded=True, representation=existing, reused=True
        )

    content = _read_all(content_port, identity)

    if content is None:
        return _failed(
            CanonicalizationFailureCode.CONTENT_INACCESSIBLE,
            f"Document '{document_id}' became unreadable while its "
            "content was being loaded for parsing.",
        )

    parse = parser.parse(
        content,
        document_id=document_id,
        content_checksum=identity.identity.checksum,
        checksum_algorithm=identity.identity.checksum_algorithm,
    )

    if not parse.parsed:
        return CanonicalizationResult(succeeded=False, failure=parse.failure)

    representation = parse.document

    if not representation.has_text:
        # Pages, but not one text span anywhere. Persisting this would
        # give every future extractor a document that appears to say
        # nothing, which is indistinguishable from one that genuinely
        # does. It names the observation and stops - it does not claim
        # the document is scanned, and nothing here could support that.
        return _failed(
            CanonicalizationFailureCode.NO_EXTRACTABLE_TEXT,
            f"Document '{document_id}' has "
            f"{representation.page_count} page(s) and no extractable "
            "text.",
            detail="No text was found. This says nothing about why - "
            "reading the pages as images would be OCR, which this "
            "milestone does not perform.",
        )

    # Every component the identity was composed from, compared against
    # what the parser actually produced. Stamping an identity onto a
    # representation it does not describe would record a false claim,
    # and everything below would inherit it.
    if (
        representation.document_id != document_id
        or representation.content_checksum != identity.identity.checksum
        or representation.checksum_algorithm
        != identity.identity.checksum_algorithm
        or representation.representation_version
        != CANONICAL_REPRESENTATION_VERSION
        or representation.parser_name != parser.parser_name
        or representation.parser_version != parser.parser_version
    ):
        # The parser produced a reading under a contract this service did
        # not look one up for, so the identity just computed does not
        # describe what was built. Storing it would record a false
        # provenance claim.
        return _failed(
            CanonicalizationFailureCode.PARSER_FAILURE,
            "The parser produced a representation this service did "
            "not look one up for: contract "
            f"'{representation.representation_version}' via "
            f"{representation.parser_name} "
            f"{representation.parser_version}, where "
            f"'{CANONICAL_REPRESENTATION_VERSION}' via "
            f"{parser.parser_name} {parser.parser_version} was "
            "expected.",
            detail="The representation's identity could not be "
            "established, and an artifact whose provenance is unknown "
            "cannot be stored.",
        )

    representation = replace(
        representation,
        artifact_identity=expected_identity.value,
        # The chain's first link, recorded rather than implied: the
        # immutable source content this representation was parsed from.
        upstream_identity=source.value,
    )

    try:
        repository.save(representation)
    except Exception as error:  # noqa: BLE001 - see below
        # Deliberately broad, and the only broad catch in this service.
        # A storage adapter can fail in ways this context cannot
        # enumerate (constraint, connection, disk), and the caller needs
        # one honest answer - "the representation was built and could not
        # be stored" - rather than an adapter exception crossing the
        # boundary. The cause is carried in ``detail``, never swallowed.
        return _failed(
            CanonicalizationFailureCode.REPRESENTATION_PERSISTENCE_FAILURE,
            f"The canonical representation of document '{document_id}' "
            "was built but could not be stored.",
            detail=f"{type(error).__name__}: {error}",
        )

    return CanonicalizationResult(
        succeeded=True, representation=representation, reused=False
    )


def get_representation(
    repository: CanonicalRepresentationRepository, document_id: int
) -> CanonicalPdfDocument | None:
    """
    The current canonical representation of one document - the **only**
    way a consumer should read a document's text.

    ``None`` means it has never been canonicalised. Not an error: most
    documents have not been, and inventing an empty representation would
    be indistinguishable from a document that genuinely says nothing.
    """

    return repository.find_latest_for_document(document_id)


def get_page(
    repository: CanonicalRepresentationRepository,
    document_id: int,
    page_number: int,
) -> CanonicalPdfPage | None:
    """
    One page of a document's canonical representation.

    Exists so a reader that needs the spans of the page it is displaying
    does not have to load every page of the document to get them. It
    reads the same artefact ``get_representation`` returns and selects
    from it; nothing is recomputed, and a page absent from the
    representation is absent here.

    ``None`` covers both "never canonicalised" and "no such page". The
    caller distinguishes them if it needs to, by asking for the
    representation - this function does not invent a page either way.
    """

    representation = repository.find_latest_for_document(document_id)

    if representation is None:
        return None

    return representation.page(page_number)


def _find_document(
    document_metadata_port: DocumentMetadataPort, document_id: int
) -> DocumentMetadata | None:
    found = document_metadata_port.find_many((document_id,))

    return found[0] if found else None


def _is_ready_for_extraction(
    ingestion_repository: IngestionJobRepository, document_id: int
) -> bool:
    return any(
        job.is_ready_for_extraction
        for job in ingestion_repository.list_by_document(document_id)
    )


def _read_all(
    content_port: DocumentContentPort, identity: ContentIdentityResult
) -> bytes | None:
    """
    Loads the whole document through the governed content port.

    A PDF is parsed as a whole - its cross-reference table lives at the
    end - so streaming past the parser is not available here. The port is
    still the only route to the bytes: this service never opens a file.
    """

    reference = identity.identity.storage_reference

    try:
        return b"".join(
            content_port.iter_chunks(reference, _READ_CHUNK_SIZE)
        )
    except OSError:
        return None


_READ_CHUNK_SIZE = 1024 * 1024


def _failed(
    code: CanonicalizationFailureCode,
    message: str,
    *,
    detail: str | None = None,
) -> CanonicalizationResult:
    return CanonicalizationResult(
        succeeded=False,
        failure=CanonicalizationFailure(
            code=code, message=message, detail=detail
        ),
    )
