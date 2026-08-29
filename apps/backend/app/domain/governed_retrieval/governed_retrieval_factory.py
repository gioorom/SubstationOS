"""
The only way a governed retrieval query is built.

Every query type has one factory function, and each enforces its own
invariants before returning - so a ``GovernedRetrievalQuery`` that
exists is a query that may be executed. The service never re-validates,
because there is no path by which an invalid one reaches it.

``scope`` always defaults to ``CURRENT_ONLY``. Asking a governed graph
what it *used* to assert is a deliberate act and reads as one at every
call site.
"""

from __future__ import annotations

from app.domain.governed_knowledge_graph.graph_vocabulary import (
    GraphEdgeKind,
)
from app.domain.governed_retrieval import governed_retrieval_validator
from app.domain.governed_retrieval.governed_retrieval_models import (
    AssetDesignationQuery,
    AssetQuantityQuery,
    DocumentKnowledgeQuery,
    GovernedIdentityQuery,
    RelationshipQuery,
)
from app.domain.governed_retrieval.governed_retrieval_validator import (
    DEFAULT_RESULT_LIMIT,
)
from app.domain.governed_retrieval.governed_retrieval_vocabulary import (
    RetrievalScope,
)


class GovernedRetrievalQueryFactory:
    """Builds validated queries. Stateless; every method is a
    ``staticmethod`` because none of them needs anything but its
    arguments."""

    @staticmethod
    def asset_by_designation(
        *,
        designation: str,
        scope: RetrievalScope = RetrievalScope.CURRENT_ONLY,
        limit: int = DEFAULT_RESULT_LIMIT,
        project_id: int | None = None,
        document_id: int | None = None,
    ) -> AssetDesignationQuery:
        governed_retrieval_validator.validate_designation(designation)
        governed_retrieval_validator.validate_limit(limit)
        governed_retrieval_validator.validate_project_scope(project_id)
        governed_retrieval_validator.validate_document_scope(document_id)

        return AssetDesignationQuery(
            designation=designation,
            scope=scope,
            limit=limit,
            project_id=project_id,
            document_id=document_id,
        )

    @staticmethod
    def quantity_for_asset(
        *,
        designation: str | None = None,
        subject_node_id: str | None = None,
        edge_kind: GraphEdgeKind | None = None,
        scope: RetrievalScope = RetrievalScope.CURRENT_ONLY,
        limit: int = DEFAULT_RESULT_LIMIT,
        project_id: int | None = None,
        document_id: int | None = None,
    ) -> AssetQuantityQuery:
        governed_retrieval_validator.validate_asset_subject(
            designation, subject_node_id
        )
        governed_retrieval_validator.validate_limit(limit)
        governed_retrieval_validator.validate_project_scope(project_id)
        governed_retrieval_validator.validate_document_scope(document_id)

        return AssetQuantityQuery(
            scope=scope,
            limit=limit,
            designation=designation,
            subject_node_id=subject_node_id,
            edge_kind=edge_kind,
            project_id=project_id,
            document_id=document_id,
        )

    @staticmethod
    def relationships(
        *,
        edge_kind: GraphEdgeKind | None = None,
        scope: RetrievalScope = RetrievalScope.CURRENT_ONLY,
        limit: int = DEFAULT_RESULT_LIMIT,
        project_id: int | None = None,
        document_id: int | None = None,
    ) -> RelationshipQuery:
        governed_retrieval_validator.validate_limit(limit)
        governed_retrieval_validator.validate_project_scope(project_id)
        governed_retrieval_validator.validate_document_scope(document_id)

        return RelationshipQuery(
            scope=scope,
            limit=limit,
            edge_kind=edge_kind,
            project_id=project_id,
            document_id=document_id,
        )

    @staticmethod
    def document_knowledge(
        *,
        document_id: int,
        scope: RetrievalScope = RetrievalScope.CURRENT_ONLY,
        limit: int = DEFAULT_RESULT_LIMIT,
        project_id: int | None = None,
    ) -> DocumentKnowledgeQuery:
        governed_retrieval_validator.validate_required_document_scope(
            document_id
        )
        governed_retrieval_validator.validate_limit(limit)
        governed_retrieval_validator.validate_project_scope(project_id)

        return DocumentKnowledgeQuery(
            document_id=document_id,
            scope=scope,
            limit=limit,
            project_id=project_id,
        )

    @staticmethod
    def governed_identity(
        *,
        node_id: str | None = None,
        edge_id: str | None = None,
        scope: RetrievalScope = RetrievalScope.CURRENT_AND_HISTORICAL,
    ) -> GovernedIdentityQuery:
        """
        One governed object, by identity.

        The only query whose scope defaults to including historical
        knowledge, and deliberately so: a caller who names an id already
        knows the object exists, and answering "no such object" for one
        that is merely retired would be a lie about the graph's
        contents. The result still reports its ``state``, so the caller
        can tell current knowledge from a record of it.
        """

        governed_retrieval_validator.validate_governed_identity(
            node_id, edge_id
        )

        return GovernedIdentityQuery(
            scope=scope,
            node_id=node_id or None,
            edge_id=edge_id or None,
        )
