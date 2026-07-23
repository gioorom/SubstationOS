from __future__ import annotations

from enum import Enum


class DocumentScope(str, Enum):
    """
    The ownership scope of an uploaded document, per ADR-0005
    (docs/architecture/adr/0005-project-vs-canonical-library-document-scope.md).

    ``PROJECT`` - owned by exactly one Project; requires a project
    reference.
    ``CANONICAL_LIBRARY`` - a reusable reference (vendor manual, standard),
    owned by no single Project; never has a project reference.

    This scope must never be inferred from a nullable project reference
    being empty - ADR-0005 exists specifically because that inference is
    ambiguous (it cannot distinguish "not yet assigned" from "deliberately
    global"). Every document's scope is this explicit, named value.

    Placement note: this enum lives here, in the Project bounded context,
    as the minimal support Project Lifecycle needs to enforce "every
    document belongs to exactly one Project, or to the Canonical Library."
    A full Document bounded context (covering the Engineering Index and
    the rest of the Document Repository) is future work, out of scope for
    this milestone - see docs/architecture/ARCHITECTURE_FREEZE_V1_CHECKLIST.md.
    """

    PROJECT = "project"
    CANONICAL_LIBRARY = "canonical_library"
