"""
The one rule for committing a session an adapter was handed.

A repository adapter in this system does not own its ``Session``: it is
constructed with the one the request is already using, and every
adapter that writes calls ``commit()`` on it directly. That is a
deliberate arrangement - there is no unit-of-work layer, and each
adapter's write is its own transaction.

It has one consequence that has to be handled in exactly one place.
**A failed commit does not leave the session where it found it.**
SQLAlchemy rolls the transaction back internally and then requires an
explicit ``rollback()`` before the session will do anything else; until
that happens every later statement raises ``PendingRollbackError``.

Nothing above the adapter performs that rollback. The services here
convert an adapter failure into a *typed value* rather than re-raising
- deliberately, so a storage fault is reported rather than escaping as
an exception - so no caller ever learns that a commit was attempted at
all. And ``get_db`` closes the session without rolling it back.

The result, before this existed, was that a *reported* failure became a
crash somewhere unrelated: the upload endpoint returned a typed
"could not store" result, then raised ``PendingRollbackError`` on the
next query it made for its own response - failing an upload whose
document was already stored and committed, which is the one thing that
endpoint promises never to do.

So: the component that issued the commit is the component that repairs
the session, and it repairs it without deciding what the failure means.
The exception is re-raised unchanged, because *what a storage failure
means* belongs to the service above, not here.
"""

from __future__ import annotations

from sqlalchemy.orm import Session


def commit_or_restore(session: Session) -> None:
    """
    Commit, and leave the session usable whether or not that succeeded.

    Raises whatever the commit raised, unchanged. Callers that wish to
    report a storage failure rather than propagate it may catch it as
    they always have - the difference is that the session they share
    with the rest of the request still works afterwards.
    """

    try:
        session.commit()
    except Exception:
        session.rollback()
        raise
