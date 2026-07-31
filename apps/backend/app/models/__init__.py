"""
The persistence models this package re-exports for convenience.

``ProjectEntity`` and ``EntityRelation`` were removed by EPIC 31.1 along
with the rest of the legacy Knowledge Graph. They held LLM-extracted
entities written straight from upload with no review gate - the
ADR-0004 violation ADR-0009 tracked and this milestone ended. The
governed replacement is ``app.models.governed_knowledge_graph``, which
holds only knowledge an engineer approved and can always be rebuilt from
the pipeline and the reviews.
"""

from .project import Project
from .document import Document
