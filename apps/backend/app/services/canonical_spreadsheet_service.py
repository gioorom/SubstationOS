"""
Application service for the Canonical Spreadsheet Representation
(ADR-0034).

    READY_FOR_EXTRACTION      (an ingestion job said so - Milestone 25.1)
        -> Read bytes         (through DocumentContentPort - 25.2)
        -> Read the workbook  (through WorkbookReaderPort)
        -> Worksheets, rows, cells
        -> Canonical workbook
        -> Persist            (through CanonicalWorkbookRepository)

Every stage is an existing capability behind an existing port. This
service adds orchestration and one decision of its own - whether the
document may be read at all - and nothing else.

**It starts at READY_FOR_EXTRACTION on purpose.** Reading a document that
no ingestion job ever accepted would bypass the governed flow: the
checksum, the classified format and the accessibility check are precisely
what make the resulting representation trustworthy, and re-deriving them
here would create a second, quieter path into the same artefact.

It reads bytes only through Milestone 25.2's content port and never opens
a file. It imports no spreadsheet library - the one module that does is
the reader adapter behind the port. It invokes no LLM, computes no
embeddings, and writes no Engineering Index record, no graph node, no
graph edge and no entity. It interprets nothing: what it stores is what
the reader observed.

It is the **mirror** of ``canonical_pdf_service``, not a widening of it.
The two lineages fork at the bytes and meet nowhere above: this module
imports nothing from ``canonical_pdf`` or ``canonical_text``, and neither
imports anything from here.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from app.domain.artifact_identity.artifact_identity_builder import (
    source_identity,
)
from app.domain.canonical_spreadsheet.canonical_spreadsheet_failures import (
    WorkbookCanonicalizationFailureCode,
)
from app.domain.canonical_spreadsheet.canonical_spreadsheet_identity import (
    workbook_identity,
)
from app.domain.canonical_spreadsheet.canonical_spreadsheet_models import (
    CanonicalWorkbook,
)
from app.domain.canonical_spreadsheet.canonical_spreadsheet_policy import (
    CANONICAL_WORKBOOK_VERSION,
    MAX_COMPRESSED_BYTES,
    SUPPORTED_SPREADSHEET_FORMATS,
    is_readable_spreadsheet_format,
)
from app.domain.canonical_spreadsheet.canonical_workbook_repository import (
    CanonicalWorkbookRepository,
)
from app.domain.canonical_spreadsheet.workbook_reader_port import (
    WorkbookReaderPort,
)
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
    ContentIdentityFailureReason, WorkbookCanonicalizationFailureCode
] = {
    ContentIdentityFailureReason.CONTENT_NOT_FOUND: (
        WorkbookCanonicalizationFailureCode.CONTENT_NOT_FOUND
    ),
    ContentIdentityFailureReason.CONTENT_INACCESSIBLE: (
        WorkbookCanonicalizationFailureCode.CONTENT_INACCESSIBLE
    ),
    ContentIdentityFailureReason.EMPTY_CONTENT: (
        WorkbookCanonicalizationFailureCode.EMPTY_CONTENT
    ),
    ContentIdentityFailureReason.CHECKSUM_FAILURE: (
        WorkbookCanonicalizationFailureCode.CONTENT_INACCESSIBLE
    ),
}

_READ_CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True, slots=True)
class WorkbookCanonicalizationFailure:
    """``detail`` is a safe, already-composed explanation - never a raw
    exception object and never a stack trace."""

    code: WorkbookCanonicalizationFailureCode
    message: str
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class WorkbookCanonicalizationResult:
    """
    What one workbook reading concluded.

    ``reused`` distinguishes "these bytes already had a representation"
    from "one was built now". Both are successes and both return the same
    representation - but an operator watching a re-run deserves to know
    that nothing was re-read, and a test can prove idempotency from it.
    """

    succeeded: bool
    representation: CanonicalWorkbook | None = None
    reused: bool = False
    failure: WorkbookCanonicalizationFailure | None = None


def canonicalize_workbook(
    reader: WorkbookReaderPort,
    repository: CanonicalWorkbookRepository,
    content_port: DocumentContentPort,
    storage_location_port: DocumentStorageLocationPort,
    document_metadata_port: DocumentMetadataPort,
    ingestion_repository: IngestionJobRepository,
    *,
    document_id: int,
) -> WorkbookCanonicalizationResult:
    """
    Build - or re-use - the canonical representation of one workbook.

    Checks run in order, and the first failure is returned: there is no
    point reporting an unreadable workbook for a document that does not
    exist, or a format complaint about bytes nobody can read.
    """

    metadata = _find_document(document_metadata_port, document_id)

    if metadata is None:
        return _failed(
            WorkbookCanonicalizationFailureCode.DOCUMENT_NOT_FOUND,
            f"Document '{document_id}' does not exist; there is nothing "
            "to read.",
        )

    if not is_readable_spreadsheet_format(metadata.document_format):
        return _failed(
            WorkbookCanonicalizationFailureCode.UNSUPPORTED_FORMAT,
            f"Document '{document_id}' is recorded as "
            f"'{metadata.document_format}', which this milestone does "
            "not read as a workbook.",
            detail=(
                "Readable spreadsheet formats: "
                + ", ".join(sorted(SUPPORTED_SPREADSHEET_FORMATS))
                + ". A legacy BIFF '.xls', an '.xlsb', a CSV and an ODS "
                "are four different problems, not four dialects of this "
                "one; reading any of them here would be a silent "
                "partial reading rather than a milestone."
            ),
        )

    if not _is_ready_for_extraction(ingestion_repository, document_id):
        return _failed(
            WorkbookCanonicalizationFailureCode.NOT_READY_FOR_EXTRACTION,
            f"Document '{document_id}' has no ingestion job that "
            "concluded READY_FOR_EXTRACTION.",
            detail="Reading is the step after ingestion. The checksum, "
            "classified format and accessibility checks ingestion "
            "performs are what make a representation trustworthy; "
            "reading without them would be a second, quieter path to "
            "the same artefact.",
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
    # representation: the reader and the shape it produces are versioned
    # separately from the document, so the contract is part of what is
    # being asked for.
    source = source_identity(
        document_id=document_id,
        content_checksum=identity.identity.checksum,
        checksum_algorithm=identity.identity.checksum_algorithm,
    )
    expected_identity = workbook_identity(
        document_id=document_id,
        content_checksum=identity.identity.checksum,
        checksum_algorithm=identity.identity.checksum_algorithm,
        representation_version=CANONICAL_WORKBOOK_VERSION,
        reader_name=reader.reader_name,
        reader_version=reader.reader_version,
    )

    existing = repository.find_by_identity(
        document_id, expected_identity.value
    )

    if existing is not None:
        # The same bytes under the same contract already have a
        # representation. Re-reading would produce an equal value and a
        # second row saying the same thing; the stored one is returned
        # instead, which is what makes re-running this safe.
        return WorkbookCanonicalizationResult(
            succeeded=True, representation=existing, reused=True
        )

    load = _read_bounded(
        content_port, identity.identity.storage_reference
    )

    if load.exceeded_bound:
        return _failed(
            WorkbookCanonicalizationFailureCode.WORKBOOK_TOO_LARGE,
            f"Document '{document_id}' exceeds the "
            f"{MAX_COMPRESSED_BYTES} byte bound on a workbook "
            "container.",
            detail="Reading stopped at the bound rather than at the "
            "end of the file, so the exact size is not reported here - "
            "discovering it would have required holding the whole "
            "document in memory, which is the cost the bound exists to "
            "refuse.",
        )

    if load.content is None:
        return _failed(
            WorkbookCanonicalizationFailureCode.CONTENT_INACCESSIBLE,
            f"Document '{document_id}' became unreadable while its "
            "content was being loaded.",
        )

    content = load.content

    read = reader.read(
        content,
        document_id=document_id,
        content_checksum=identity.identity.checksum,
        checksum_algorithm=identity.identity.checksum_algorithm,
    )

    if not read.was_read:
        return _failed(read.failure_code, read.detail or "", detail=None)

    representation = read.workbook

    if not representation.worksheets:
        # A valid container carrying no worksheet at all.
        return _failed(
            WorkbookCanonicalizationFailureCode.EMPTY_WORKBOOK,
            f"Document '{document_id}' is a valid workbook with no "
            "worksheet.",
        )

    if not representation.has_populated_cell:
        # Worksheets, and not one populated cell anywhere. Persisting
        # this would give every future consumer a register that appears
        # to say nothing, which is indistinguishable from one that
        # genuinely does. It names the observation and stops - it does
        # not claim the file is a template or a macro container, and
        # nothing here could support that.
        return _failed(
            WorkbookCanonicalizationFailureCode.NO_POPULATED_CELL,
            f"Document '{document_id}' has "
            f"{representation.worksheet_count} worksheet(s) and no "
            "populated cell.",
            detail="This names an observation, not a diagnosis: nothing "
            "in this context reads what the file is for.",
        )

    # Every component the identity was composed from, compared against
    # what the reader actually produced. Stamping an identity onto a
    # representation it does not describe would record a false claim,
    # and everything below would inherit it.
    if (
        representation.document_id != document_id
        or representation.content_checksum != identity.identity.checksum
        or representation.checksum_algorithm
        != identity.identity.checksum_algorithm
        or representation.representation_version
        != CANONICAL_WORKBOOK_VERSION
        or representation.reader_name != reader.reader_name
        or representation.reader_version != reader.reader_version
    ):
        return _failed(
            WorkbookCanonicalizationFailureCode.READER_FAILURE,
            "The reader produced a representation this service did not "
            "look one up for: contract "
            f"'{representation.representation_version}' via "
            f"{representation.reader_name} "
            f"{representation.reader_version}, where "
            f"'{CANONICAL_WORKBOOK_VERSION}' via {reader.reader_name} "
            f"{reader.reader_version} was expected.",
            detail="The representation's identity could not be "
            "established, and an artifact whose provenance is unknown "
            "cannot be stored.",
        )

    representation = replace(
        representation,
        artifact_identity=expected_identity.value,
        # The chain's first link, recorded rather than implied: the
        # immutable source content this representation was read from.
        # This lineage hangs on the bytes exactly as the PDF one does,
        # which is the whole shape of the fork ADR-0034 describes.
        upstream_identity=source.value,
    )

    try:
        repository.save(representation)
    except Exception as error:  # noqa: BLE001 - see below
        # Deliberately broad, and the only broad catch in this service.
        # A storage adapter can fail in ways this context cannot
        # enumerate (constraint, connection, disk), and the caller needs
        # one honest answer - "the representation was built and could
        # not be stored" - rather than an adapter exception crossing the
        # boundary. The cause is carried in ``detail``, never swallowed.
        return _failed(
            WorkbookCanonicalizationFailureCode
            .REPRESENTATION_PERSISTENCE_FAILURE,
            f"The canonical workbook of document '{document_id}' was "
            "built but could not be stored.",
            detail=f"{type(error).__name__}: {error}",
        )

    return WorkbookCanonicalizationResult(
        succeeded=True, representation=representation, reused=False
    )


def get_workbook(
    repository: CanonicalWorkbookRepository, document_id: int
) -> CanonicalWorkbook | None:
    """
    The current canonical workbook of one document - the **only** way a
    consumer should read a workbook's cells.

    ``None`` means it has never been read. Not an error: most documents
    have not been, and inventing an empty representation would be
    indistinguishable from a register that genuinely says nothing.
    """

    return repository.find_latest_for_document(document_id)


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


@dataclass(frozen=True, slots=True)
class _BoundedContent:
    """
    The document's bytes, or the reason there are none to give.

    ``exceeded_bound`` is not a failure of the storage: the bytes are
    there and readable, and there are simply more of them than the
    policy admits.
    """

    content: bytes | None = None
    exceeded_bound: bool = False


def _read_bounded(
    content_port: DocumentContentPort, storage_reference: str
) -> _BoundedContent:
    """
    Loads the document through the governed content port, **stopping at
    the governed bound rather than at the end of the file.**

    A workbook is a compressed container whose central directory lives at
    the end, so streaming past the reader is not available here: the
    reader needs the whole container. What is available is refusing to
    accumulate an unbounded amount before discovering that it is
    unbounded, and that is what this does - the port already yields
    chunks, so the loop simply stops once one byte more than the policy
    admits has arrived.

    Reading one byte past the bound rather than exactly to it is what
    distinguishes "exactly at the limit" from "over it" without a second
    request or a trusted declared size. Nothing here consults
    ``Content-Length`` or any other claim the file makes about itself.

    The port remains the only route to the bytes: this service never
    opens a file, and the reader receives content rather than a path so
    it cannot open one either.
    """

    chunks: list[bytes] = []
    accumulated = 0

    try:
        for chunk in content_port.iter_chunks(
            storage_reference, _READ_CHUNK_SIZE
        ):
            chunks.append(chunk)
            accumulated += len(chunk)

            if accumulated > MAX_COMPRESSED_BYTES:
                return _BoundedContent(exceeded_bound=True)
    except OSError:
        return _BoundedContent()

    return _BoundedContent(content=b"".join(chunks))


def _failed(
    code: WorkbookCanonicalizationFailureCode,
    message: str,
    *,
    detail: str | None = None,
) -> WorkbookCanonicalizationResult:
    return WorkbookCanonicalizationResult(
        succeeded=False,
        failure=WorkbookCanonicalizationFailure(
            code=code, message=message, detail=detail
        ),
    )
