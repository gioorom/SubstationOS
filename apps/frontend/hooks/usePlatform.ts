"use client";

import { useCallback } from "react";

import type { ErrorCopy } from "@/lib/api";
import type {
  HealthResponse,
  ProjectIntelligence,
} from "@/lib/contracts";
import {
  getHealth,
  getProjectIntelligence,
} from "@/lib/resources/platform";

import { useResource } from "./useResource";

const HEALTH_COPY: ErrorCopy = {
  network:
    "Impossibile verificare lo stato dei servizi: il backend non risponde.",
};

const PROJECT_COPY: ErrorCopy = {
  notFound: "Il progetto richiesto non esiste.",
};

/**
 * Service health.
 *
 * A failed health check is reported as an error, **not** silently
 * rewritten into an "everything offline" payload as the previous hook
 * did - fabricating a backend answer to a request the backend never
 * answered is the same defect as a mock, in the place where it matters
 * most.
 */
export function useHealth() {
  const read = useCallback((signal: AbortSignal) => getHealth(signal), []);

  const resource = useResource<HealthResponse>(read, { copy: HEALTH_COPY });

  return {
    health: resource.data,
    loading: resource.loading,
    error: resource.error,
    reload: resource.reload,
  };
}

export function useProjectIntelligence(projectId: number | undefined) {
  const read = useCallback(
    (signal: AbortSignal) =>
      getProjectIntelligence(projectId as number, signal),
    [projectId],
  );

  const resource = useResource<ProjectIntelligence>(read, {
    enabled: projectId !== undefined,
    copy: PROJECT_COPY,
  });

  return {
    intelligence: resource.data,
    loading: resource.loading,
    error: resource.error,
    reload: resource.reload,
  };
}
