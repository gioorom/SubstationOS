"""
Shared fixtures for the deterministic derivation chain
(Evidence -> Entities -> Facts -> Semantics).

Every stage runs through its **real service and real adapter** against a
real (in-memory) database. A fake at any stage could agree with the
domain and disagree with what the pipeline actually persists, which is
precisely the class of defect these tests exist to catch.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.infrastructure.engineering_entities.sqlalchemy_engineering_entity_repository import (  # noqa: E501
    SqlAlchemyEngineeringEntityRepository,
)
from app.infrastructure.engineering_evidence.sqlalchemy_engineering_evidence_repository import (  # noqa: E501
    SqlAlchemyEngineeringEvidenceRepository,
)
from app.infrastructure.engineering_facts.sqlalchemy_engineering_fact_repository import (  # noqa: E501
    SqlAlchemyEngineeringFactRepository,
)
from app.infrastructure.engineering_semantics.sqlalchemy_engineering_semantic_repository import (  # noqa: E501
    SqlAlchemyEngineeringSemanticRepository,
)
from app.services import (
    engineering_fact_service,
    engineering_semantic_service,
)
from tests.services._entity_support import prepared, resolve, store_evidence

# A line EPIC 32.E2 changed the reading of. Under extraction policy 1.0
# `+E01` was read only as part of the compound designation; under 2.0 it
# is also a location aspect, which the governed 32.P1 rule turns into a
# location fact and an IS_LOCATED_IN statement. The line also carries a
# quantity, so a stale reuse loses one fact while keeping another -
# which is what makes the loss visible rather than total.
LOCATION_LINE = "Interruttore +E01-QA1 630 kVA"

__all__ = [
    "LOCATION_LINE",
    "construct_facts",
    "interpret_semantics",
    "prepared",
    "resolve",
    "run_pipeline",
    "store_evidence",
]


def construct_facts(db: Session, document_id: int, **kwargs):
    return engineering_fact_service.construct_document_facts(
        SqlAlchemyEngineeringEntityRepository(db),
        SqlAlchemyEngineeringEvidenceRepository(db),
        kwargs.pop(
            "fact_repository", SqlAlchemyEngineeringFactRepository(db)
        ),
        document_id=document_id,
        **kwargs,
    )


def interpret_semantics(db: Session, document_id: int, **kwargs):
    return engineering_semantic_service.interpret_document_facts(
        SqlAlchemyEngineeringFactRepository(db),
        kwargs.pop(
            "semantic_repository",
            SqlAlchemyEngineeringSemanticRepository(db),
        ),
        document_id=document_id,
        **kwargs,
    )


def run_pipeline(db: Session, document_id: int, **kwargs):
    """
    Entities, then facts, then semantics - each through its own service,
    in the order the pipeline runs them.

    **Stops at the first stage that fails**, as an orchestrator must: a
    refusal upstream means the stage below it has no current input, and
    running it anyway would read the previous stage's stored result and
    report a reuse that says nothing about the run.

    Returns the three results - ``None`` for stages not reached - so a
    test can assert what was reused and what was recomputed at each one.
    """

    entities = resolve(db, document_id, **kwargs.pop("entities", {}))

    if not entities.succeeded:
        return entities, None, None

    facts = construct_facts(db, document_id, **kwargs.pop("facts", {}))

    if not facts.succeeded:
        return entities, facts, None

    semantics = interpret_semantics(
        db, document_id, **kwargs.pop("semantics", {})
    )

    return entities, facts, semantics
