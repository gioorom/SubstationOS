"""
The fixed, documented ingestion policy (Milestone 25.1) - explicit
immutable data, never a branch chain. The same "policy table" convention
every other bounded context in this codebase establishes.

Bump ``INGESTION_PIPELINE_VERSION`` whenever a pipeline step or a rule
below changes, so a persisted ``IngestionJob`` records which pipeline
produced its outcome. A job stamped ``1.0`` stays reproducible even after
the pipeline grows.
"""

from __future__ import annotations

from app.domain.document_identity.document_format import ClassifiedFormat

# 1.1 since Milestone 25.2: the pipeline now resolves content identity and
# classifies the format, so a job stamped 1.0 was produced by a shallower
# pipeline and is recognisably so.
INGESTION_PIPELINE_VERSION = "1.1"

# **Every format the document repository can hold is ingestible**, and all
# are treated identically - no drawing-specific behaviour. A DWG goes
# through exactly the same steps as a PDF, because this pipeline
# orchestrates and does not read.
#
# ``other`` is included deliberately, and the reasoning matters. It is the
# value a document takes when nothing classified it - today's upload
# endpoint sets no format at all, so in practice every uploaded document
# carries it. Treating ``other`` as "unsupported" would mean refusing a
# document on the strength of a field nobody ever filled in: absence of a
# classification is not evidence that the file is unusable, and this
# system does not confuse the two anywhere else either.
#
# What this check does catch is a format value that is not a recognised
# ``DocumentFormat`` at all - a row written by a different schema version,
# or corrupted. That is a data-integrity condition worth failing on
# loudly, and it is the only thing ``UNSUPPORTED_FORMAT`` claims.
#
# The vocabulary is ``ClassifiedFormat``'s, which is the domain's own
# restatement of the persistence enum (the domain does not import the ORM
# - CLAUDE.md's Dependency Rule). A test asserts the two value sets agree,
# so a format added to one cannot silently go missing from the other.
# Derived from ``ClassifiedFormat`` rather than restated, since Milestone
# 25.2: there is one format vocabulary in this system, and a second copy
# here could drift from it.
SUPPORTED_INGESTION_FORMATS: frozenset[str] = frozenset(
    member.value for member in ClassifiedFormat
)


def is_supported_format(document_format: str) -> bool:
    """True for every format the document repository recognises. False
    only for a value this system has no definition of - never for a
    document that merely went unclassified."""

    return document_format in SUPPORTED_INGESTION_FORMATS
