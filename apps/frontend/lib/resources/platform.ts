/** `GET /health`, `GET /projects/{id}/intelligence` and the graph reads. */

import { apiClient } from "@/lib/api";
import type {
  HealthResponse,
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
