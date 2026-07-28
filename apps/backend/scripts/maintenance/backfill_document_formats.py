"""
Backfill the classified format of documents stored as ``other``
(Milestone 25.2).

Every document uploaded before Milestone 25.2 was recorded as ``other``,
because the upload endpoint never set a format. Those rows remain
readable exactly as they are; this command offers to name the ones whose
bytes can be classified.

Usage (from ``apps/backend``):

    python -m scripts.maintenance.backfill_document_formats            # report only
    python -m scripts.maintenance.backfill_document_formats --apply    # write

**Dry run by default.** Without ``--apply`` nothing is written: the
command reads bytes, prints what it would do, and exits. This is the
same code path ``--apply`` uses to decide, so the report is not an
approximation of the run - it *is* the run, minus the write.

**Deterministic.** Documents are examined in ascending id order and
classified by the one classifier upload and ingestion also use, so two
runs over unchanged data print the same report. It reads at most a
32-byte signature per document: no parsing, no OCR, no LLM, no
embeddings, and no writes to the Engineering Index or Knowledge Graph.

Never invents a format. A document whose bytes are missing, unreadable,
unrecognised or contradictory is left as ``other`` and reported under the
reason it was left.
"""

from __future__ import annotations

import argparse
import sys

from app.database.database import SessionLocal
from app.infrastructure.document_identity.filesystem_document_content import (
    FilesystemDocumentContentAdapter,
)
from app.infrastructure.document_identity.sqlalchemy_document_format_registry import (  # noqa: E501
    SqlAlchemyDocumentFormatRegistry,
)
from app.services.document_format_backfill_service import (
    UNCLASSIFIED_FORMAT,
    BackfillPlan,
    apply_format_backfill,
    plan_format_backfill,
)


def _parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Report - and optionally record - the classified format of "
            "documents currently stored as unclassified."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Write the reclassified formats. Without this flag the "
            "command only reports what it would do."
        ),
    )
    parser.add_argument(
        "--stored-format",
        default=UNCLASSIFIED_FORMAT,
        help=(
            "Examine documents recorded under this format value "
            f"(default: '{UNCLASSIFIED_FORMAT}')."
        ),
    )

    return parser.parse_args(argv)


def _print_plan(plan: BackfillPlan, *, applied: bool) -> None:
    for decision in plan.decisions:
        detected = decision.detected_format or "-"
        decided_by = decision.decided_by or "-"

        print(
            f"  #{decision.document_id:<6} {decision.action.value:<22} "
            f"{detected:<10} {decided_by:<20} {decision.filename}"
        )

    print()

    for action, count in sorted(plan.count_by_action().items()):
        print(f"  {action:<22} {count}")

    print()
    print(
        f"  {'written' if applied else 'would write'}: "
        f"{len(plan.actionable)} document(s)"
    )


def main(argv: list[str] | None = None) -> int:
    arguments = _parse_arguments(argv)
    session = SessionLocal()

    try:
        registry = SqlAlchemyDocumentFormatRegistry(session)
        plan = plan_format_backfill(
            registry,
            FilesystemDocumentContentAdapter(),
            stored_format=arguments.stored_format,
        )

        print(
            f"Documents recorded as '{arguments.stored_format}': "
            f"{len(plan.decisions)}"
        )
        print()

        if arguments.apply:
            apply_format_backfill(registry, plan)

        _print_plan(plan, applied=arguments.apply)

        if not arguments.apply and plan.actionable:
            print()
            print("  Dry run - nothing was written. Re-run with --apply.")
    finally:
        session.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
