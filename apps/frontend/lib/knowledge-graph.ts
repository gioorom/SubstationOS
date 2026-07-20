import { apiRequest } from "@/lib/api";
import type {
  EntityType,
  KnowledgeGraph,
} from "@/types/knowledge-graph";

interface GetKnowledgeGraphOptions {
  search?: string;
  entityType?: EntityType;
}

export function getKnowledgeGraph(
  projectId: number,
  options: GetKnowledgeGraphOptions = {}
): Promise<KnowledgeGraph> {
  const searchParams = new URLSearchParams();

  if (options.search?.trim()) {
    searchParams.set("search", options.search.trim());
  }

  if (options.entityType) {
    searchParams.set("entity_type", options.entityType);
  }

  const queryString = searchParams.toString();

  return apiRequest<KnowledgeGraph>(
    `/projects/${projectId}/knowledge-graph${
      queryString ? `?${queryString}` : ""
    }`
  );
}