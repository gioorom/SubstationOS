from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class IndexEntryLocatorKind(str, Enum):
    """
    The kind of position a source locator points to within a document.
    Deliberately not restricted to PDF pages (architecture doc §5 covers
    PDF, Excel, DWG, and Image document families) - a locator may point
    to a spreadsheet cell range or a CAD drawing's layout just as
    meaningfully as a page number.
    """

    PAGE = "page"
    SHEET = "sheet"
    CELL_RANGE = "cell_range"
    DRAWING_LAYOUT = "drawing_layout"
    REGION = "region"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class IndexEntryLocator:
    """
    Where, within its document, an Engineering Index entry's mention was
    found. ``value`` is a free-form string whose shape depends on
    ``kind`` (e.g. a page number as text for ``PAGE``, a range like
    "B12:C15" for ``CELL_RANGE``, a sheet name for ``SHEET``). This
    bounded context does not parse or interpret ``value`` - it is an
    opaque reference, not a fact.
    """

    kind: IndexEntryLocatorKind
    value: str | None = None

    @property
    def page(self) -> int | None:
        """
        Backward-compatible view for the common PDF case: the page
        number as an int, or ``None`` for any non-``PAGE`` locator (or a
        ``PAGE`` locator with no value).
        """

        if self.kind is IndexEntryLocatorKind.PAGE and self.value is not None:
            return int(self.value)

        return None
