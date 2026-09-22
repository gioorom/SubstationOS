"""documents never reuse an id

A document id identifies a document for as long as anything remembers
it, and twelve tables remember it. Without ``AUTOINCREMENT`` SQLite
assigns ``max(id) + 1``, so removing the highest-numbered document hands
its id to the next upload - and that upload silently inherits the
removed document's ingestion jobs and every derived artefact keyed to
the old id. A different file acquires another document's provenance, and
nothing anywhere reports it.

No application code deletes a document. The relationship that could -
``Project.documents``, which carried ``cascade="all, delete-orphan"`` -
no longer does, so the path is closed in code. This closes the path that
code cannot reach: a row removed by hand, in a database, by someone
fixing something else.

**SQLite cannot alter a primary key**, so the table is rebuilt: Alembic
creates the new shape, copies the rows, drops the old table and renames.
No row is altered in transit and no value is computed - the copy is the
whole point, and the rebuild is what SQLite requires rather than a
choice made here.

**The rebuild runs on SQLite and nowhere else.** A backend with a real
sequence does not reuse an id, so there is nothing to fix; and dropping
and recreating a table that twelve others reference, to change nothing,
would be the most destructive no-op in the repository. The guard is on
the dialect rather than on a comment saying so.

**Two honest limits, and the second one is a live defect.**

The rebuild seeds SQLite's ``sqlite_sequence`` from the highest id that
survives it, so an id deleted *before* this migration ran can still be
handed out afterwards. Nothing can recover a high-water mark that was
never recorded.

And the mark does not survive a downgrade followed by a re-upgrade.
``downgrade`` rebuilds the table without ``AUTOINCREMENT``, which drops
the mark; ``upgrade`` then reseeds from the highest *surviving* row. An
id spent on a document that was removed while at this revision comes
back, and the next upload inherits that document's ingestion job - the
failure this migration exists to prevent, reintroduced by running it
twice. Reproduced, not theorised.

**It is not fixed here, deliberately.** Restoring the mark needs an
``UPDATE`` or an ``INSERT``, and
``test_no_migration_fabricates_an_identity`` forbids any data statement
in a migration. That rule is textual precisely so it cannot be argued
with, and weakening it - even for a counter that is not an identity, in
a table SQLite owns - is an AF-01 §22 decision requiring its own ADR,
not something to settle inside a migration that needed to go green.
Writing the same statement through a query builder to dodge the text
scan would route around the rule rather than satisfy it.

So the guarantee is narrower than it first reads: **an id is not reused
while the schema stays at or above this revision.** Reaching the defect
takes two manual operations in sequence - removing a row by hand, then
downgrading and re-upgrading - and no code path does either.

Revision ID: 8f21c04ab7de
Revises: 3ca7e14b90d2
Create Date: 2026-09-22

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "8f21c04ab7de"
down_revision: Union[str, Sequence[str], None] = "3ca7e14b90d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    if op.get_bind().dialect.name != "sqlite":
        return

    with op.batch_alter_table(
        "documents",
        recreate="always",
        table_kwargs={"sqlite_autoincrement": True},
    ):
        pass


def downgrade() -> None:
    """Downgrade schema."""

    if op.get_bind().dialect.name != "sqlite":
        return

    with op.batch_alter_table("documents", recreate="always"):
        pass
