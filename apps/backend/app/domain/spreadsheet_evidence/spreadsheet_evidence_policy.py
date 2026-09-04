"""
The fixed policy of spreadsheet evidence extraction (ADR-0034).

Everything here must be recorded alongside a stored evidence set for it
to stay explainable, and none of it is a knob to tune. A bound that
varied by caller would make the same workbook yield one set in one code
path and another set elsewhere, which is exactly the machine-dependence
this platform forbids.
"""

from __future__ import annotations

from app.domain.canonical_spreadsheet.canonical_spreadsheet_policy import (
    CANONICAL_WORKBOOK_VERSION,
)

# This context's own policy version. Bumped when the *catalogue* this
# extractor applies changes - a rule added, a rule version raised, a unit
# declared - so a stored evidence set always says which body of rules
# produced it, and a re-extraction is a deliberate, visible event rather
# than a silent reinterpretation.
#
# 1.0 is the first version, and it is deliberately **not** tied to the
# PDF family's extraction policy version even though both stages apply
# the same catalogue today. The two are separate reuse keys: this stage
# also owns *which cell text is read* - a literal, or a formula's cached
# result - and changing that decision must invalidate spreadsheet
# evidence without pretending the PDF lineage changed.
SPREADSHEET_EXTRACTION_POLICY_VERSION = "1.0"

# Workbook representation contracts this extractor understands. A
# workbook recorded under a newer contract is refused rather than read on
# a best-effort basis: a later contract may record a cell's text
# differently, and character offsets taken against the wrong recording
# would point at the wrong characters - which is worse than no evidence
# at all.
SUPPORTED_WORKBOOK_VERSIONS: frozenset[str] = frozenset(
    {CANONICAL_WORKBOOK_VERSION}
)


def is_supported_workbook_version(version: str) -> bool:
    return version in SUPPORTED_WORKBOOK_VERSIONS
