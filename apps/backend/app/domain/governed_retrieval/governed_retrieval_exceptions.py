"""
Typed failures for Governed Structured Retrieval (EPIC 31.2).

Every error here describes something about the **query**. None describes
a database, a provider, or a network, because this context executes no
provider call and its domain performs no I/O.

There is deliberately no "not found" error. A query that matches no
governed knowledge is a **successful result** whose outcome is
``NO_MATCH``: retrieval reports what the governed graph holds, and
"nothing" is an answer an engineer needs to be able to read, not an
exception to catch.
"""

from __future__ import annotations


class GovernedRetrievalError(Exception):
    """Base class for every Governed Structured Retrieval failure."""


class InvalidRetrievalQueryError(GovernedRetrievalError):
    """The supplied query is structurally invalid and was not executed."""


class BlankDesignationError(InvalidRetrievalQueryError):
    def __init__(self) -> None:
        super().__init__(
            "A designation query must name a designation; a blank one "
            "would match every governed asset and answer a question "
            "nobody asked."
        )


class DesignationTooLongError(InvalidRetrievalQueryError):
    def __init__(self, length: int, maximum: int) -> None:
        self.length = length
        self.maximum = maximum
        super().__init__(
            f"A designation may be at most {maximum} characters; "
            f"received {length}."
        )


class InvalidResultLimitError(InvalidRetrievalQueryError):
    def __init__(self, limit: int, minimum: int, maximum: int) -> None:
        self.limit = limit
        super().__init__(
            f"A result limit must be between {minimum} and {maximum}; "
            f"received {limit}."
        )


class InvalidProjectScopeError(InvalidRetrievalQueryError):
    def __init__(self, project_id: int) -> None:
        self.project_id = project_id
        super().__init__(
            f"A project scope must be a positive project id; received "
            f"'{project_id}'."
        )


class InvalidDocumentScopeError(InvalidRetrievalQueryError):
    def __init__(self, document_id: int) -> None:
        self.document_id = document_id
        super().__init__(
            f"A document scope must be a positive document id; received "
            f"'{document_id}'."
        )


class BlankGovernedIdentityError(InvalidRetrievalQueryError):
    def __init__(self) -> None:
        super().__init__(
            "An identity query must name a governed node id or a governed "
            "edge id."
        )


class AmbiguousGovernedIdentityError(InvalidRetrievalQueryError):
    def __init__(self) -> None:
        super().__init__(
            "An identity query names either a node or an edge, never "
            "both: one query, one governed object."
        )


class UnresolvableAssetSubjectError(InvalidRetrievalQueryError):
    def __init__(self) -> None:
        super().__init__(
            "A quantity query must name the asset it asks about, either "
            "by designation or by governed node id."
        )
