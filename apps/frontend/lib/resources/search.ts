/** `GET /projects/{id}/search` — searching one project's documents. */

import { apiClient } from "@/lib/api";
import type {
  ProjectSearchQuery,
  ProjectSearchResponse,
} from "@/lib/contracts";

/**
 * What this project's documents say that matches the query.
 *
 * The project is part of the path rather than a parameter, so there is
 * no call this module can make that searches more than one project.
 */
export function searchProjectDocuments(
  projectId: number,
  query: ProjectSearchQuery,
  signal?: AbortSignal,
): Promise<ProjectSearchResponse> {
  return apiClient.get<ProjectSearchResponse>(
    `/projects/${projectId}/search`,
    {
      query: {
        q: query.q,
        limit: query.limit,
        offset: query.offset,
      },
      signal,
      retries: 1,
    },
  );
}
