from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.engineering_index.engineering_index_entry_kind import (
    EngineeringIndexEntryKind,
)
from app.domain.engineering_index.engineering_index_locator import (
    IndexEntryLocatorKind,
)


class EngineeringIndexMention(BaseModel):
    kind: EngineeringIndexEntryKind

    identifier: str = Field(
        min_length=1,
        max_length=255,
    )

    page: int | None = Field(
        default=None,
        ge=1,
    )

    locator_kind: IndexEntryLocatorKind | None = Field(
        default=None,
    )

    locator_value: str | None = Field(
        default=None,
        max_length=255,
    )

    label: str | None = Field(
        default=None,
        max_length=500,
    )

    @model_validator(mode="after")
    def _check_page_and_locator_are_not_contradictory(
        self,
    ) -> "EngineeringIndexMention":
        if (
            self.page is not None
            and self.locator_kind is not None
            and self.locator_kind is not IndexEntryLocatorKind.PAGE
        ):
            raise ValueError(
                "page can only be combined with locator_kind='page'; "
                "use locator_value instead for a non-page locator."
            )

        return self


class EngineeringIndexEntryCreate(EngineeringIndexMention):
    document_id: int


class EngineeringIndexEntriesBulkCreate(BaseModel):
    document_id: int
    mentions: list[EngineeringIndexMention] = Field(min_length=1)


class EngineeringIndexDocumentIndexReplace(BaseModel):
    """
    Body for rebuilding a document's Engineering Index: every existing
    entry for the document is replaced by these mentions. An empty list
    is valid - it rebuilds the document's index to "nothing found".
    """

    mentions: list[EngineeringIndexMention] = Field(default_factory=list)


class EngineeringIndexEntryRead(BaseModel):
    id: int
    project_id: int
    document_id: int
    kind: EngineeringIndexEntryKind
    identifier: str
    page: int | None
    locator_kind: IndexEntryLocatorKind
    locator_value: str | None
    label: str | None
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )
