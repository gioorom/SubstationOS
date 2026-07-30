"""
Exports the backend's OpenAPI document so the frontend can be checked
against it.

The frontend keeps a hand-written transcription of the API contract in
``apps/frontend/lib/contracts``. ``tests/contracts.test.ts`` compares
every enum in that transcription against the schema this script writes,
which is what turns "the frontend's types match the backend" from a
claim into an assertion.

The output is a **committed contract snapshot**, not a build artefact:
it is the version of the contract the frontend was written against, and
a diff on it is exactly the signal a reviewer wants when a backend enum
changes. Regenerate it whenever a router, schema or enum changes:

    python scripts/export_openapi.py

Writes to ``apps/backend/openapi.json``. Reads nothing, starts no
server, and touches no database.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = REPOSITORY_ROOT / "apps" / "backend"
OUTPUT_PATH = BACKEND_ROOT / "openapi.json"


def main() -> int:
    sys.path.insert(0, str(BACKEND_ROOT))

    from app.main import app  # noqa: PLC0415  (import after path setup)

    document = app.openapi()

    OUTPUT_PATH.write_text(
        json.dumps(document, indent=1, sort_keys=True, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )

    path_count = len(document["paths"])
    schema_count = len(document["components"]["schemas"])

    print(
        f"Wrote {OUTPUT_PATH.relative_to(REPOSITORY_ROOT)} "
        f"({path_count} paths, {schema_count} schemas)."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
