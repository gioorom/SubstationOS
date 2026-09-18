"""
Typed failures of the Document Identity context.

This context distinguishes two kinds of bad news, and keeps them apart
deliberately.

A **failure reason** (``ContentIdentityFailureReason``) describes
something true about a document: it could not be found, it was empty, it
broke partway through being read. Those are outcomes a caller reports
and a reader needs to see, so they travel as values rather than
exceptions.

An **exception** here describes a caller that asked for something
incoherent - a digest in a spelling this context does not record. That
is not a fact about any document, and returning it as a failure reason
would invite the caller to persist it as though a document were at
fault.
"""

from __future__ import annotations


class DocumentIdentityError(Exception):
    """Base class for every error this context raises."""
