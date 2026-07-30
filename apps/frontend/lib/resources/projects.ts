/**
 * `POST|GET|PATCH|DELETE /projects` and the lifecycle transitions.
 *
 * One function per backend endpoint, named after what the backend calls
 * it. No function here invents a capability the API does not have.
 */

import { apiClient } from "@/lib/api";
import type {
  CreateProjectRequest,
  Project,
  ProjectListResponse,
  ProjectQuery,
  UpdateProjectRequest,
} from "@/lib/contracts";

/**
 * One page of the project registry. Since Milestone 30.1.3 the server
 * owns paging, filtering, search and sorting.
 */
export function listProjects(
  query: ProjectQuery = {},
  signal?: AbortSignal,
): Promise<ProjectListResponse> {
  return apiClient.get<ProjectListResponse>("/projects/", {
    query: {
      page: query.page,
      page_size: query.page_size,
      status: query.status,
      lifecycle_state: query.lifecycle_state,
      search: query.search?.trim() || undefined,
      include_deleted: query.include_deleted,
      sort_by: query.sort_by,
      direction: query.direction,
    },
    signal,
    retries: 1,
  });
}

export function getProject(
  projectId: number,
  signal?: AbortSignal,
): Promise<Project> {
  return apiClient.get<Project>(`/projects/${projectId}`, {
    signal,
    retries: 1,
  });
}

/** 201 on success, 409 on a duplicate code, 422 on invalid name or code. */
export function createProject(
  payload: CreateProjectRequest,
  signal?: AbortSignal,
): Promise<Project> {
  return apiClient.post<Project>("/projects/", { json: payload, signal });
}

/**
 * Partial metadata update. `code`, `status` and `voltage_level` are not
 * accepted by this endpoint and are absent from the request type.
 *
 * 409 when the project's lifecycle state makes it read-only.
 */
export function updateProject(
  projectId: number,
  payload: UpdateProjectRequest,
  signal?: AbortSignal,
): Promise<Project> {
  return apiClient.patch<Project>(`/projects/${projectId}`, {
    json: payload,
    signal,
  });
}

export function activateProject(
  projectId: number,
  signal?: AbortSignal,
): Promise<Project> {
  return apiClient.post<Project>(`/projects/${projectId}/activate`, {
    signal,
  });
}

export function archiveProject(
  projectId: number,
  signal?: AbortSignal,
): Promise<Project> {
  return apiClient.post<Project>(`/projects/${projectId}/archive`, {
    signal,
  });
}

export function restoreProject(
  projectId: number,
  signal?: AbortSignal,
): Promise<Project> {
  return apiClient.post<Project>(`/projects/${projectId}/restore`, {
    signal,
  });
}

/**
 * Soft delete. No row is removed; the project moves to lifecycle state
 * `deleted` and the updated project is returned.
 */
export function deleteProject(
  projectId: number,
  signal?: AbortSignal,
): Promise<Project> {
  return apiClient.delete<Project>(`/projects/${projectId}`, { signal });
}
