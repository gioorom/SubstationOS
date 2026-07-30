/**
 * The Project contract, transcribed from the backend.
 *
 * Source of truth: `app/schemas/project.py` (`ProjectCreate`,
 * `ProjectUpdateMetadata`, `ProjectRead`), `app/models/project.py`
 * (`ProjectStatus`) and `app/domain/project/project_lifecycle.py`
 * (`ProjectLifecycleState`). Nothing here may be widened, narrowed or
 * renamed to suit the UI - when the backend changes, this file changes.
 *
 * Since Milestone 30.1.3 `ProjectStatus` lives in the domain
 * (`app/domain/project/project_status.py`) rather than the ORM module.
 */

import type {
  PagedResponse,
  PageRequest,
  SortDirection,
} from "./pagination";

/**
 * The delivery phase of a substation project.
 *
 * Orthogonal to {@link ProjectLifecycleState}: a project can be
 * `energized` and `archived` at the same time. The two answer different
 * questions - where the works are, and whether the record is editable.
 */
export const PROJECT_STATUSES = [
  "planning",
  "engineering",
  "construction",
  "commissioning",
  "energized",
  "closed",
] as const;

export type ProjectStatus = (typeof PROJECT_STATUSES)[number];

/** Whether the project record itself is a draft, live, archived or removed. */
export const PROJECT_LIFECYCLE_STATES = [
  "draft",
  "active",
  "archived",
  "deleted",
] as const;

export type ProjectLifecycleState =
  (typeof PROJECT_LIFECYCLE_STATES)[number];

/** The lifecycle states in which the backend accepts a mutation. */
export const MUTABLE_LIFECYCLE_STATES: readonly ProjectLifecycleState[] = [
  "draft",
  "active",
];

export function isMutable(project: Project): boolean {
  return MUTABLE_LIFECYCLE_STATES.includes(project.lifecycle_state);
}

export interface Project {
  id: number;
  name: string;
  code: string;
  customer: string;
  epc: string | null;
  country: string | null;
  location: string | null;
  voltage_level: string | null;
  status: ProjectStatus;
  description: string | null;
  lifecycle_state: ProjectLifecycleState;
  canonical_domain_version: string;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
  deleted_at: string | null;
}

/**
 * `name`, `code` and `customer` are required by the backend and are
 * required here. `customer` in particular was optional in the previous
 * frontend contract, which made every project created without one fail
 * validation.
 */
export interface CreateProjectRequest {
  name: string;
  code: string;
  customer: string;
  epc?: string | null;
  country?: string | null;
  location?: string | null;
  voltage_level?: string | null;
  status?: ProjectStatus;
  description?: string | null;
  canonical_domain_version?: string;
  created_by?: string | null;
}

/**
 * `code` is deliberately absent: once published it is a contract and is
 * never renamed through a metadata update.
 *
 * `lifecycle_state` is absent for a different reason - it moves only
 * through the explicit transitions (`/activate`, `/archive`, `/restore`,
 * `DELETE`), each of which validates the move. `status` and
 * `voltage_level` joined this request in Milestone 30.1.3, when the
 * backend's PATCH began accepting them.
 */
export interface UpdateProjectRequest {
  name?: string;
  customer?: string;
  epc?: string | null;
  country?: string | null;
  location?: string | null;
  description?: string | null;
  status?: ProjectStatus;
  voltage_level?: string | null;
}

export const PROJECT_SORT_FIELDS = [
  "created_at",
  "updated_at",
  "name",
  "code",
] as const;

export type ProjectSortField = (typeof PROJECT_SORT_FIELDS)[number];

export const PROJECT_SORT_LABELS: Record<ProjectSortField, string> = {
  created_at: "Data di creazione",
  updated_at: "Ultima modifica",
  name: "Nome",
  code: "Codice",
};

/**
 * The server-side query.
 *
 * `status` and `lifecycle_state` are separate filters on purpose: "show
 * me energized projects" and "show me archived projects" are different
 * questions, and a project can answer yes to both.
 */
export interface ProjectQuery extends PageRequest {
  status?: ProjectStatus;
  lifecycle_state?: ProjectLifecycleState;
  /**
   * Case-insensitive partial match over **name, code, customer and
   * location**, trimmed at both ends. `description` is deliberately not
   * searched: it is long prose, and including it would make a search for
   * "CP-01" match every project whose description mentions one.
   */
  search?: string;
  include_deleted?: boolean;
  sort_by?: ProjectSortField;
  direction?: SortDirection;
}

export type ProjectListResponse = PagedResponse<Project>;

/** Field length limits, mirrored from the Pydantic schema. */
export const PROJECT_FIELD_LIMITS = {
  name: { min: 2, max: 150 },
  code: { min: 2, max: 80 },
  customer: { min: 2, max: 150 },
  epc: { min: 0, max: 150 },
  country: { min: 0, max: 150 },
  location: { min: 0, max: 150 },
  voltage_level: { min: 0, max: 50 },
} as const;

export const PROJECT_STATUS_LABELS: Record<ProjectStatus, string> = {
  planning: "Pianificazione",
  engineering: "Ingegneria",
  construction: "Costruzione",
  commissioning: "Messa in servizio",
  energized: "In tensione",
  closed: "Chiuso",
};

export const PROJECT_LIFECYCLE_LABELS: Record<
  ProjectLifecycleState,
  string
> = {
  draft: "Bozza",
  active: "Attivo",
  archived: "Archiviato",
  deleted: "Eliminato",
};
