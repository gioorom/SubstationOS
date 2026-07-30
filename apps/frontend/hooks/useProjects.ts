"use client";

import { useCallback, useState } from "react";

import type { ErrorCopy } from "@/lib/api";
import type {
  CreateProjectRequest,
  Project,
  ProjectListResponse,
  ProjectQuery,
  UpdateProjectRequest,
} from "@/lib/contracts";
import { EMPTY_PAGE } from "@/lib/contracts";
import {
  archiveProject,
  createProject,
  deleteProject,
  getProject,
  listProjects,
  restoreProject,
  updateProject,
} from "@/lib/resources/projects";

import { useMutation, useResource } from "./useResource";

// Module constants: `useResource` and `useMutation` take these as
// dependencies, so they must be referentially stable.
const LIST_COPY: ErrorCopy = {
  network:
    "Impossibile caricare i progetti: il backend SubstationOS non risponde.",
};

const CREATE_COPY: ErrorCopy = {
  conflict: "Esiste già un progetto con questo codice.",
  validation: "I dati del progetto non sono validi.",
};

const READ_COPY: ErrorCopy = {
  notFound: "Il progetto richiesto non esiste.",
};

const UPDATE_COPY: ErrorCopy = {
  conflict: "Il progetto è archiviato o eliminato e non è modificabile.",
};

const TRANSITION_COPY: ErrorCopy = {
  conflict:
    "La transizione richiesta non è ammessa dallo stato attuale del progetto.",
};

/**
 * A page of the project registry.
 *
 * **The query goes to the server.** Filtering, search, sorting and paging
 * are backend concerns since Milestone 30.1.3; this hook sends the query
 * and renders the page it gets back.
 */
export function useProjects(query: ProjectQuery = {}) {
  const {
    page,
    page_size,
    status,
    lifecycle_state,
    search,
    include_deleted,
    sort_by,
    direction,
  } = query;

  const read = useCallback(
    (signal: AbortSignal) =>
      listProjects(
        {
          page,
          page_size,
          status,
          lifecycle_state,
          search,
          include_deleted,
          sort_by,
          direction,
        },
        signal,
      ),
    [
      page,
      page_size,
      status,
      lifecycle_state,
      search,
      include_deleted,
      sort_by,
      direction,
    ],
  );

  const resource = useResource<ProjectListResponse>(read, {
    copy: LIST_COPY,
  });

  const perform = useCallback(
    (payload: CreateProjectRequest, signal: AbortSignal) =>
      createProject(payload, signal),
    [],
  );

  const creation = useMutation<CreateProjectRequest, Project>(perform, {
    copy: CREATE_COPY,
  });

  const { reload } = resource;
  const { run: runCreate } = creation;

  const create = useCallback(
    async (payload: CreateProjectRequest) => {
      const project = await runCreate(payload);

      // Re-read rather than splice: where the new project lands depends
      // on the active sort and filters, which only the server knows.
      await reload();

      return project;
    },
    [runCreate, reload],
  );

  return {
    projects: resource.data?.items ?? [],
    pagination: resource.data?.pagination ?? EMPTY_PAGE,
    loading: resource.loading,
    refreshing: resource.refreshing,
    error: resource.error,
    reload: resource.reload,
    create,
    creating: creation.pending,
    createError: creation.error,
    createFailure: creation.failure,
    resetCreateError: creation.reset,
  };
}

/**
 * Page state for the project registry. Changing a filter resets to page
 * 1 - staying on page 4 of the previous result set would show an empty
 * page and read as "no matches".
 */
export function useProjectQuery(initial: ProjectQuery = {}) {
  const [query, setQuery] = useState<ProjectQuery>({ page: 1, ...initial });

  const setFilter = useCallback((patch: Partial<ProjectQuery>) => {
    setQuery((current) => ({ ...current, ...patch, page: 1 }));
  }, []);

  const setPage = useCallback((page: number) => {
    setQuery((current) => ({ ...current, page }));
  }, []);

  const reset = useCallback(() => {
    setQuery((current) => ({ page: 1, page_size: current.page_size }));
  }, []);

  return { query, setFilter, setPage, reset };
}

export type ProjectTransition = "archive" | "restore" | "delete";

export function useProject(projectId: number | undefined) {
  const read = useCallback(
    (signal: AbortSignal) => getProject(projectId as number, signal),
    [projectId],
  );

  const resource = useResource<Project>(read, {
    enabled: projectId !== undefined,
    copy: READ_COPY,
  });

  const performUpdate = useCallback(
    (payload: UpdateProjectRequest, signal: AbortSignal) =>
      updateProject(projectId as number, payload, signal),
    [projectId],
  );

  const update = useMutation<UpdateProjectRequest, Project>(performUpdate, {
    copy: UPDATE_COPY,
  });

  const performTransition = useCallback(
    (action: ProjectTransition, signal: AbortSignal) => {
      const id = projectId as number;

      if (action === "archive") {
        return archiveProject(id, signal);
      }

      if (action === "restore") {
        return restoreProject(id, signal);
      }

      return deleteProject(id, signal);
    },
    [projectId],
  );

  const transition = useMutation<ProjectTransition, Project>(
    performTransition,
    { copy: TRANSITION_COPY },
  );

  const { set: setProject } = resource;
  const { run: runUpdate } = update;
  const { run: runTransition } = transition;

  const applyUpdate = useCallback(
    async (payload: UpdateProjectRequest) => {
      const project = await runUpdate(payload);
      setProject(project);
      return project;
    },
    [runUpdate, setProject],
  );

  const applyTransition = useCallback(
    async (action: ProjectTransition) => {
      const project = await runTransition(action);
      setProject(project);
      return project;
    },
    [runTransition, setProject],
  );

  return {
    project: resource.data,
    loading: resource.loading,
    error: resource.error,
    failure: resource.failure,
    reload: resource.reload,
    update: applyUpdate,
    updating: update.pending,
    updateError: update.error,
    updateFailure: update.failure,
    resetUpdateError: update.reset,
    transition: applyTransition,
    transitioning: transition.pending,
    transitionError: transition.error,
  };
}
