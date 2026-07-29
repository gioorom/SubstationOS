"""
The pagination contract as it appears on the wire.

One shape, used by every list endpoint, so a client writes its paging
logic once. Shared *metadata*, not a shared generic envelope: each
resource declares its own typed list response with its own ``items``, so
OpenAPI can name what is inside it.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.shared_kernel.pagination import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    Page,
)


class PageMetadata(BaseModel):
    """Where this page sits in the whole result set."""

    page: int = Field(description="1-based index of this page.")

    page_size: int = Field(
        description="How many items one page holds at most."
    )

    total: int = Field(
        description=(
            "Total items matching the query, across all pages - not the "
            "number returned here."
        )
    )

    total_pages: int = Field(
        description="How many pages the result set spans."
    )

    has_next: bool
    has_previous: bool

    @classmethod
    def of(cls, page: Page) -> "PageMetadata":
        return cls(
            page=page.page,
            page_size=page.page_size,
            total=page.total,
            total_pages=page.total_pages,
            has_next=page.has_next,
            has_previous=page.has_previous,
        )


#: Re-exported so the router's query parameters and the API documentation
#: cite the same numbers the domain enforces.
__all__ = ["PageMetadata", "DEFAULT_PAGE_SIZE", "MAX_PAGE_SIZE"]
