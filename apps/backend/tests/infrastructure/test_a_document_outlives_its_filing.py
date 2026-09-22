"""
A document outlives the project it is filed against.

Twelve tables reference ``documents.id``, none of them cascades, and the
database does not enforce the references - so a destroyed document row
leaves twelve tables of derived artefacts pointing at a row that is not
there, silently. The document is therefore the wrong thing to make
disposable, and these tests pin the ways it used to be: two through the
cascade, one through an id SQLite was free to hand out twice.

``Project.documents`` carried ``cascade="all, delete-orphan"``. That
meant deleting a project deleted every document filed against it, and -
less obviously and more dangerously - that *detaching* a document from
the collection deleted its row. Re-filing a document into another
project is the most natural way somebody would write that.

Neither is reachable through the application today: no route deletes a
project row and nothing traverses the collection. That is exactly why
these tests exist. An invariant nothing currently exercises is one a
future change breaks without noticing.
"""

from __future__ import annotations

import importlib
import pkgutil

from sqlalchemy import func, select
from sqlalchemy.orm import Session, configure_mappers

import app.models  # noqa: F401  (populate the mapper registry)
from app.database.database import Base
from app.models.document import Document as DocumentRecord
from app.models.project import Project as ProjectRecord


def _import_every_model_module() -> None:
    """Register every mapped class, so the scan below sees all of them
    rather than the ones an earlier import happened to pull in."""

    for module in pkgutil.iter_modules(app.models.__path__):
        importlib.import_module(f"app.models.{module.name}")


def _project(db_session: Session, code: str = "ALFA-01") -> ProjectRecord:
    project = ProjectRecord(
        name="Cabina Primaria Alfa",
        code=code,
        customer="Distributore Nazionale",
    )

    db_session.add(project)
    db_session.flush()

    return project


def _document(
    db_session: Session, project: ProjectRecord | None
) -> DocumentRecord:
    document = DocumentRecord(
        filename="schema_unifilare.pdf",
        file_path="/storage/documents/schema_unifilare_a1b2c3d4.pdf",
        project_id=project.id if project else None,
        project_name=project.name if project else "Unknown",
    )

    db_session.add(document)
    db_session.commit()

    return document


def _documents(db_session: Session) -> int:
    return db_session.execute(
        select(func.count()).select_from(DocumentRecord)
    ).scalar_one()


def test_deleting_a_project_leaves_its_documents(
    db_session: Session,
) -> None:
    """
    The case the cascade made worst.

    A project is only ever *soft* deleted, precisely so that the project
    and everything referencing it stay readable for audit and eventual
    restore. A hard delete that took the documents with it would empty
    the thing the soft delete exists to preserve.
    """

    project = _project(db_session)
    _document(db_session, project)

    db_session.delete(project)
    db_session.commit()

    assert _documents(db_session) == 1


def test_detaching_a_document_from_a_project_leaves_it(
    db_session: Session,
) -> None:
    """
    The case that would have been written by accident.

    Moving a document to another project, or to the Canonical Library,
    reads as removing it from one collection and adding it to another.
    Under ``delete-orphan`` the first half destroyed it.
    """

    project = _project(db_session)
    document = _document(db_session, project)

    project.documents.remove(document)
    db_session.commit()

    assert _documents(db_session) == 1


def test_clearing_a_documents_project_leaves_it(
    db_session: Session,
) -> None:
    """
    The same act spelled the other way round.

    ``list(project.documents)`` is not decoration. A many-to-one does
    not load its old value before replacing it, so clearing
    ``document.project`` on an unloaded collection fires no removal
    event and orphans nothing - and this test passed with the cascade
    restored until the collection was loaded first. It pinned nothing.

    Loading the collection is also what real code does: anything that
    re-files a document has read the project's documents to find it.
    """

    project = _project(db_session)
    document = _document(db_session, project)

    assert document in list(project.documents)

    document.project = None
    db_session.commit()

    assert _documents(db_session) == 1


def test_a_document_id_is_never_reused(db_session: Session) -> None:
    """
    What the id has to survive.

    Without ``AUTOINCREMENT`` SQLite hands ``max(id) + 1`` to the next
    insert, so removing the highest-numbered document gives its id to
    the next upload - which then inherits that document's ingestion jobs
    and every artefact keyed to the old id. A different file acquires
    another document's provenance and nothing reports it.
    """

    first = _document(db_session, None)
    second = _document(db_session, None)

    db_session.delete(second)
    db_session.commit()

    third = _document(db_session, None)

    assert third.id not in {first.id, second.id}


def test_no_mapped_relationship_can_delete_a_document() -> None:
    """
    The invariant, rather than the four behaviours above.

    A cascade is one keyword argument. It arrived once without a test,
    an ADR or a line of documentation, and stayed until something went
    looking.

    This asks the mappers rather than the source. A source scan has to
    guess which class a ``relationship()`` points at, and the target can
    be written as a positional string, an ``argument=`` keyword, a bare
    class, an inference from the ``Mapped[]`` annotation, or a
    ``backref()`` from the other side. The scan this replaced read the
    positional string, which is the one form the single relationship in
    the tree happens to use - so it passed because of how today's code
    is written rather than because of what it forbids.

    Three things this has to get right that the obvious version does
    not.

    It matches on the **table**, not on the class. A second mapper over
    ``documents`` - a subclass, single-table or joined - is a different
    class whose cascade deletes the same rows, and a check for
    ``is DocumentRecord`` waves it through.

    It checks ``secondary`` separately and unconditionally. A
    relationship whose association table *is* ``documents`` deletes rows
    on ordinary collection removal, with no cascade keyword anywhere to
    notice - and ``relation.mapper.tables`` names the target's tables,
    never the secondary, so the table check alone misses it entirely.

    And it **imports every model module first**, rather than inspecting
    whichever mappers some earlier import happened to register. Bare
    ``import app.models`` registers two; the package re-exports only
    ``Project`` and ``Document``. Left implicit, this test's coverage
    would depend on which unrelated module ran before it - which is the
    same "coverage it does not have" that the scan it replaced was
    retired for.
    """

    _import_every_model_module()
    configure_mappers()

    offenders: list[str] = []

    for mapper in Base.registry.mappers:
        for relation in mapper.relationships:
            # An association table is deleted from on ordinary collection
            # removal, with no cascade keyword anywhere - so this one is
            # checked first and unconditionally. `relation.mapper.tables`
            # holds the *target's* tables and never the secondary, which
            # is how a reviewer destroyed a real row while this scan
            # reported nothing.
            if relation.secondary is DocumentRecord.__table__:
                offenders.append(
                    f"{mapper.class_.__name__}.{relation.key} "
                    f"uses documents as an association table"
                )
                continue

            if DocumentRecord.__table__ not in relation.mapper.tables:
                continue

            if relation.cascade.delete or relation.cascade.delete_orphan:
                offenders.append(
                    f"{mapper.class_.__name__}.{relation.key} -> "
                    f"{relation.mapper.class_.__name__} "
                    f"cascade={sorted(relation.cascade)}"
                )

    assert offenders == [], (
        "a mapped relationship can delete document rows: "
        f"{offenders}"
    )
