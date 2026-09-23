"""
The test suite writes its files somewhere it is allowed to.

``app.services.storage.BASE_STORAGE`` is a relative path to the
deployment's storage root, and every upload writes beneath it. Nothing
redirected it, so for as long as there have been upload tests, each one
left a real file in the developer's real document store - around 78,000
of them had collected there, mixed in with the engineering corpus the
product is meant to search.

These tests hold the isolation in place. They assert on the filesystem
rather than on intentions: what matters is not that the code *means* to
write elsewhere but that nothing lands in the real store.

The real store's **contents** are never read. They are somebody's
proprietary drawings, and a test's business with them ends at counting.
"""

from __future__ import annotations

import io
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.services import storage as storage_service
from tests._pdf_builder import single_page_pdf
from tests._search_corpus import make_project
from tests.conftest import (
    DEFAULT_STORAGE_ROOT,
    REAL_STORAGE_ROOT,
)


def _population(root: Path) -> dict[str, int]:
    """How many entries each subdirectory of ``root`` holds."""

    if not root.is_dir():
        return {}

    return {
        child.name: sum(1 for _ in os.scandir(child))
        for child in root.iterdir()
        if child.is_dir()
    }


class TestTheStorageATestWritesTo:
    def test_it_is_not_the_real_storage_root(
        self, isolated_storage: Path
    ) -> None:
        """A. The redirected root is outside the real one."""

        resolved = isolated_storage.resolve()

        assert not resolved.is_relative_to(REAL_STORAGE_ROOT.resolve())

    def test_it_is_not_the_real_document_store(
        self, isolated_storage: Path
    ) -> None:
        documents = (REAL_STORAGE_ROOT / "documents").resolve()

        assert not (isolated_storage / "documents").resolve().is_relative_to(
            documents
        )

    def test_the_application_is_actually_pointed_at_it(
        self, isolated_storage: Path
    ) -> None:
        """
        The fixture is worthless if it redirects something the code does
        not read.
        """

        assert storage_service.BASE_STORAGE == isolated_storage

    def test_pytest_owns_the_directory_and_will_clear_it(
        self, isolated_storage: Path, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        """
        D. Cleanup is pytest's, on its own retention schedule - which is
        why nothing here deletes anything: a failed test's files are
        worth keeping until the next runs need the space.
        """

        base = tmp_path_factory.getbasetemp().resolve()

        assert isolated_storage.resolve().is_relative_to(base)


class TestProductionStorageIsUnchanged:
    """
    B. Redirecting the root for tests must not move it for anybody else.
    """

    def test_the_default_root_is_still_the_deployment_one(self) -> None:
        assert DEFAULT_STORAGE_ROOT == Path("../../storage")

    def test_documents_still_land_in_the_same_place(self) -> None:
        assert (
            DEFAULT_STORAGE_ROOT / "documents"
            == Path("../../storage/documents")
        )

    def test_the_only_redirected_root_is_the_storage_service(self) -> None:
        """
        Isolation works by redirecting one constant, so nothing that
        writes documents may name the path independently of it.

        ``/health`` does name its own path, and that is recorded rather
        than changed: it is declared on the application in ``main``, not
        on a router, so the test client assembled in ``conftest`` never
        serves it and it cannot contribute to what accumulates. Routing
        it through the storage service would also put ``app/main.py``
        on the closed list of modules permitted to reach stored bytes
        (``test_document_pipeline_boundaries``), which is a real
        architectural boundary and not worth spending on a probe no
        test reaches.
        """

        import inspect

        import app.main as main

        assert (
            'Path("../../storage/documents")'
            in inspect.getsource(main.health_check)
        )
        assert "app.services.storage" not in inspect.getsource(main)


class TestAnUploadedDocumentGoesOnlyToTestStorage:
    """C. The bytes land under the isolated root and nowhere else."""

    def test_the_file_is_written_beneath_the_isolated_root(
        self, api_client: TestClient, db_session, isolated_storage: Path
    ) -> None:
        project = make_project(db_session, name="Stazione", code="ISO-1")

        response = api_client.post(
            "/documents/upload",
            files={
                "file": (
                    "schema.pdf",
                    io.BytesIO(single_page_pdf("Trasformatore TR1")),
                    "application/pdf",
                )
            },
            data={"scope": "project", "project_id": str(project.id)},
        )

        assert response.status_code == 200

        written = list((isolated_storage / "documents").iterdir())

        assert len(written) == 1
        assert written[0].read_bytes().startswith(b"%PDF")

    def test_the_recorded_path_points_inside_the_isolated_root(
        self, api_client: TestClient, db_session, isolated_storage: Path
    ) -> None:
        from app.models.document import Document

        project = make_project(db_session, name="Stazione", code="ISO-2")

        response = api_client.post(
            "/documents/upload",
            files={
                "file": (
                    "schema.pdf",
                    io.BytesIO(single_page_pdf("Quadro MT")),
                    "application/pdf",
                )
            },
            data={"scope": "project", "project_id": str(project.id)},
        )

        document = db_session.get(
            Document, response.json()["document"]["id"]
        )

        assert (
            Path(document.file_path)
            .resolve()
            .is_relative_to(isolated_storage.resolve())
        )


@pytest.mark.skipif(
    not REAL_STORAGE_ROOT.is_dir(),
    reason="no real storage root on this machine",
)
class TestTheRealStoreIsUntouched:
    """
    E. The claim, checked against the filesystem itself.

    The session-wide guard in ``conftest`` makes the same assertion for
    every test at once. This one makes it for the operation that used to
    break it, so a failure names the cause rather than the session.
    """

    def test_uploading_leaves_the_real_store_exactly_as_it_was(
        self, api_client: TestClient, db_session
    ) -> None:
        before = _population(REAL_STORAGE_ROOT)

        project = make_project(db_session, name="Stazione", code="ISO-3")

        for index in range(3):
            response = api_client.post(
                "/documents/upload",
                files={
                    "file": (
                        f"schema-{index}.pdf",
                        io.BytesIO(single_page_pdf(f"Sezionatore -Q{index}")),
                        "application/pdf",
                    )
                },
                data={"scope": "project", "project_id": str(project.id)},
            )

            assert response.status_code == 200

        assert _population(REAL_STORAGE_ROOT) == before

    def test_no_other_write_path_reaches_the_real_store(
        self, api_client: TestClient, db_session, isolated_storage: Path
    ) -> None:
        """
        Whatever a request touches on the way through - ingestion,
        canonicalisation, indexing - none of it may land outside the
        redirected root.
        """

        before = _population(REAL_STORAGE_ROOT)

        project = make_project(db_session, name="Stazione", code="ISO-4")

        api_client.post(
            "/documents/upload",
            files={
                "file": (
                    "schema.pdf",
                    io.BytesIO(single_page_pdf("Morsettiera E1")),
                    "application/pdf",
                )
            },
            data={"scope": "project", "project_id": str(project.id)},
        )
        api_client.get(
            f"/projects/{project.id}/search", params={"q": "Morsettiera"}
        )

        assert _population(REAL_STORAGE_ROOT) == before
        assert any((isolated_storage / "documents").iterdir())
