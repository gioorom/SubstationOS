/** `GET /health`, `GET /projects/{id}/intelligence` and the graph reads. */

import { apiClient } from "@/lib/api";
import type {
  HealthResponse,
  KnowledgeGraph,
  GraphEntityType,
  ProjectIntelligence,
} from "@/lib/contracts";

export function getHealth(
  signal?: AbortSignal,
): Promise<HealthResponse> {
  return apiClient.get<HealthResponse>("/health", {
    signal,
    timeoutMs: 5_000,
  });
}

export function getProjectIntelligence(
  projectId: number,
  signal?: AbortSignal,
): Promise<ProjectIntelligence> {
  return apiClient.get<ProjectIntelligence>(
    `/projects/${projectId}/intelligence`,
    { signal, retries: 1 },
  );
}

export interface KnowledgeGraphQuery {
  search?: string;
  entityType?: GraphEntityType;
  signal?: AbortSignal;
}

export function getKnowledgeGraph(
  projectId: number,
  query: KnowledgeGraphQuery = {},
): Promise<KnowledgeGraph> {
  return apiClient.get<KnowledgeGraph>(
    `/projects/${projectId}/knowledge-graph`,
    {
      query: {
        search: query.search?.trim() || undefined,
        entity_type: query.entityType,
      },
      signal: query.signal,
      retries: 1,
    },
  );
}
