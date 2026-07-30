/**
 * The Governed Knowledge Graph endpoints.
 *
 * Resource-oriented, like the API they call. There is no `approve()`, no
 * `promote()` verb and no query language: a promotion is a **run**
 * appended to a collection, and the queries are the ones an engineer
 * asks, as resources.
 *
 * Goes through the same `apiClient` as everything else; an architecture
 * test asserts no second HTTP path exists.
 */

import { apiClient } from "@/lib/api";
import type {
  GraphEdge,
  GraphEdgeListResponse,
  GraphNodeDetail,
  GraphNodeKind,
  GraphNodeListResponse,
  GraphStatus,
  PromotionResult,
  StatementPromotion,
} from "@/lib/contracts";

const readOptions = (signal?: AbortSignal) => ({ signal, retries: 1 });

export function readGraphStatus(
  signal?: AbortSignal,
): Promise<GraphStatus> {
  return apiClient.get<GraphStatus>(
    "/knowledge-graph/status",
    readOptions(signal),
  );
}

/**
 * Find governed assets and quantities.
 *
 * `search` matches the governed label or normalized value - a substring
 * match over stored pipeline output, never a similarity search, and it
 * never decides two nodes are the same thing.
 */
export function listGraphNodes(
  query: {
    kind?: GraphNodeKind;
    project_id?: number;
    document_id?: number;
    search?: string;
    include_historical?: boolean;
    page?: number;
    page_size?: number;
  } = {},
  signal?: AbortSignal,
): Promise<GraphNodeListResponse> {
  return apiClient.get<GraphNodeListResponse>("/knowledge-graph/nodes", {
    query: {
      kind: query.kind,
      project_id: query.project_id,
      document_id: query.document_id,
      search: query.search?.trim() || undefined,
      include_historical: query.include_historical,
      page: query.page,
      page_size: query.page_size,
    },
    ...readOptions(signal),
  });
}

/**
 * One node, and everything asserted about it.
 *
 * "Find rated power", "find upstream equipment" and "find downstream
 * equipment" are all this call: the relationships come back with the
 * node, each with its own provenance, so the explanation of an answer
 * arrives with the answer.
 */
export function readGraphNode(
  nodeId: string,
  query: { include_historical?: boolean } = {},
  signal?: AbortSignal,
): Promise<GraphNodeDetail> {
  return apiClient.get<GraphNodeDetail>(
    `/knowledge-graph/nodes/${encodeURIComponent(nodeId)}`,
    {
      query: { include_historical: query.include_historical },
      ...readOptions(signal),
    },
  );
}

export function listGraphEdges(
  query: {
    project_id?: number;
    document_id?: number;
    include_historical?: boolean;
    page?: number;
    page_size?: number;
  } = {},
  signal?: AbortSignal,
): Promise<GraphEdgeListResponse> {
  return apiClient.get<GraphEdgeListResponse>("/knowledge-graph/edges", {
    query: {
      project_id: query.project_id,
      document_id: query.document_id,
      include_historical: query.include_historical,
      page: query.page,
      page_size: query.page_size,
    },
    ...readOptions(signal),
  });
}

export function readGraphEdge(
  edgeId: string,
  signal?: AbortSignal,
): Promise<GraphEdge> {
  return apiClient.get<GraphEdge>(
    `/knowledge-graph/edges/${encodeURIComponent(edgeId)}`,
    readOptions(signal),
  );
}

/**
 * Whether one statement is in the graph, and why or why not.
 *
 * What the Workspace asks per statement. The refusal is the point: a
 * panel that only said "not in the graph" would leave the engineer to
 * guess whether that is because nobody approved it or because the
 * pipeline moved on.
 */
export function readStatementPromotion(
  documentId: number,
  statementKey: string,
  signal?: AbortSignal,
): Promise<StatementPromotion> {
  return apiClient.get<StatementPromotion>(
    `/documents/${documentId}/engineering-semantics/` +
      `${encodeURIComponent(statementKey)}/promotion`,
    readOptions(signal),
  );
}

/**
 * Reconciles one statement's, or one document's, knowledge.
 *
 * Incremental: it visits what could have changed rather than
 * recomputing the projection. The same rule decides promotability as a
 * full rebuild, so the two can never disagree.
 */
export function createPromotion(
  documentId: number,
  statementKey?: string,
  signal?: AbortSignal,
): Promise<PromotionResult> {
  return apiClient.post<PromotionResult>("/knowledge-graph/promotions", {
    query: { document_id: documentId, statement_key: statementKey },
    signal,
  });
}
